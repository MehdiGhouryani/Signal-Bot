"""
دامنه سیگنال: منوی ثبت سیگنال (Full Signal / Fast Call)، سیگنال‌های من، فید عمومی
سیگنال‌های فعال (بند ۴ و ۶ نیازمندی‌ها)، و ثبت سیگنال گروهی از طریق دستور.

پترن ثبت‌نام (CallbackQueryHandler):
  signals_callback   → ^(menu_mysignals|mysig_open|mysig_approved|mysig_rejected|
                          menu_signal|sigtype_full|sigtype_fast|menu_activesignals|
                          fastcall_skipdir)$
  direction_callback → ^dir_        (فقط برای فینال‌کردن Fast Call از طریق دکمه در دایرکت)

MessageHandler/CommandHandler جدا (در main.py ثبت می‌شن، نه اینجا):
  photo_handler      → filters.PHOTO           (عکس در دایرکت؛ اگه کپشنش با
                                                 /fullsignal شروع بشه، به cmd_fullsignal
                                                 delegate می‌شه — چون CommandHandler
                                                 استاندارد کپشن رو چک نمی‌کنه، فقط text)
  cmd_fastcall       → CommandHandler("fastcall")    (ثبت Fast Call در گروه یا دایرکت)
  cmd_fullsignal     → CommandHandler("fullsignal")  (ثبت Full Signal متنی در گروه یا دایرکت)

⚠️ نکته معماری مهم: مراحل میانیِ فلوی مکالمه‌ای (منتظر عکس/متن هستیم) در
context.chat_data ذخیره می‌شن، نه context.user_data. چون user_data بین همه‌ی
چت‌های یک کاربر (دایرکت + هر گروهی) مشترکه، اگه اونجا ذخیره می‌شد، یک پیام کاملاً
بی‌ربط در یک گروه دیگه می‌تونست به‌عنوان ادامه‌ی یک فلوی نیمه‌کاره در دایرکت
اشتباهی پردازش بشه (این باگ واقعی بود، با تست پیدا شد). chat_data این مشکل رو
از ریشه حل می‌کنه چون مخصوص همون یک چته.
دستورهای گروهی (/fastcall و /fullsignal) اصلاً از این state استفاده نمی‌کنن —
هر پیام کاملاً مستقل و یک‌مرحله‌ایه، که برای محیط شلوغ گروه مقاوم‌تره.
"""
import logging

from telegram import Update, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from telegram.constants import ParseMode

from signal_bot.config.settings import SEP, ADMIN_IDS, SIGNAL_TYPE_LABELS, PUBLIC_FEED_LIMIT
from signal_bot.db import signals_repo, users_repo, staff_repo
from signal_bot.services import access, alpha_score
from signal_bot.services.notify import safe_send_message, safe_send_photo
from signal_bot.formatters.texts import my_signals_text
from signal_bot.keyboards.keyboards import (
    mysignals_filter_kb, signal_menu_kb, back_main_kb, cancel_kb, direction_kb,
    approve_reject_kb, btn
)
from signal_bot.utils import esc
from signal_bot.handlers.common import guard_callback


def _detect_direction(text: str):
    """تشخیص جهت از کلیدواژه‌های long/short یا خرید/فروش — برای متن آزاد یا آرگومان دستور."""
    if not text:
        return None
    low = text.lower()
    if "long" in low or "خرید" in text:
        return "LONG"
    if "short" in low or "فروش" in text:
        return "SHORT"
    return None


def _parse_signal_text(text: str):
    """
    استخراج heuristic و کاملاً اختیاری اسم کوین/جهت از متن آزاد (کپشن عکس یا
    تحلیل متنیِ Full Signal). اگه چیزی تشخیص داده نشه، مقادیر خالی/None برمی‌گردن —
    سیگنال بازم ثبت می‌شه، چون طبق بند ۴ نیازمندی‌ها، ارسال «فقط عکس» (یا فقط متن)
    باید کافی باشه.
    """
    coin, direction = "", None
    if not text:
        return coin, direction
    try:
        tokens = text.split()
        if tokens:
            first = tokens[0].strip("#$").upper()
            # isascii هم لازمه چون isalpha() برای حروف فارسی/یونیکد هم True برمی‌گردونه
            if first.isascii() and first.isalpha() and 2 <= len(first) <= 10:
                coin = first
        direction = _detect_direction(text)
    except Exception as e:
        # صرفاً یه heuristic روی رشته‌ست؛ اگه به هر دلیلی خطا داد، سیگنال بدون
        # coin/direction استخراج‌شده ثبت می‌شه — نباید کل ثبت سیگنال رو خراب کنه.
        logging.warning(f"خطا در تجزیه متن سیگنال: {e}")
    return coin, direction


async def _check_daily_limit(user):
    """فقط چک می‌کنه؛ خروجی (ok, message). فراخواننده تصمیم می‌گیره پیام رو چطور نشون بده
    (q.answer با alert برای دکمه‌ها، یا reply_text ساده برای دستورهای گروهی)."""
    role  = users_repo.get_role(user.id)
    limit = access.get_daily_limit(role)
    if signals_repo.daily_signal_count(user.id) >= limit:
        return False, f"⛔️ سقف روزانه رول شما ({access.get_role_label(role)}): {limit} سیگنال!"
    return True, ""


async def signals_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    guard = await guard_callback(update, context)
    if guard is None:
        return
    q, user, is_admin, is_vip_helper = guard
    data = q.data

    # ── سیگنال‌های من ─────────────────────────────────────
    if data == "menu_mysignals":
        await q.edit_message_text(
            "<b>📜  سیگنال‌های من</b>\n\nفیلتر رو انتخاب کن:",
            reply_markup=mysignals_filter_kb(), parse_mode=ParseMode.HTML
        )
    elif data == "mysig_open":
        await q.edit_message_text(my_signals_text(user.id, "pending"),
                                  reply_markup=mysignals_filter_kb(), parse_mode=ParseMode.HTML)
    elif data == "mysig_approved":
        await q.edit_message_text(my_signals_text(user.id, "approved"),
                                  reply_markup=mysignals_filter_kb(), parse_mode=ParseMode.HTML)
    elif data == "mysig_rejected":
        await q.edit_message_text(my_signals_text(user.id, "rejected"),
                                  reply_markup=mysignals_filter_kb(), parse_mode=ParseMode.HTML)

    # ── فید عمومی سیگنال‌های فعال (بند ۶) ──────────────────
    elif data == "menu_activesignals":
        await _show_active_signals(q, context)

    # ── منوی ثبت سیگنال: انتخاب نوع (بند ۴) ────────────────
    elif data == "menu_signal":
        await q.edit_message_text(
            f"<b>📡  ثبت سیگنال جدید</b>\n{SEP}\n\n"
            f"📸  <b>Full Signal</b> — عکس تحلیلت رو بفرست، یا اگه عکس نداری متنی بنویس\n"
            f"⚡  <b>Fast Call</b> — معرفی سریع یه کوین/توکن (بدون Entry/TP)\n\n"
            f"💡  توی گروه هم می‌تونی مستقیم با دستور /fastcall یا /fullsignal ثبت کنی.\n{SEP}",
            reply_markup=signal_menu_kb(), parse_mode=ParseMode.HTML
        )

    elif data == "sigtype_full":
        ok, msg = await _check_daily_limit(user)
        if not ok:
            await q.answer(msg, show_alert=True)
            return
        context.chat_data.clear()
        context.chat_data["signal_step"] = "full_content"
        await q.edit_message_text(
            f"<b>📸  Full Signal</b>\n{SEP}\n\n"
            f"عکس تحلیل/سیگنالت رو بفرست، یا اگه عکس نداری، همینجا متنی بنویسش.\n"
            f"می‌تونی اسم کوین و جهت (Long/Short) رو هم داخلش بنویسی — اختیاریه.",
            reply_markup=cancel_kb(), parse_mode=ParseMode.HTML
        )

    elif data == "sigtype_fast":
        ok, msg = await _check_daily_limit(user)
        if not ok:
            await q.answer(msg, show_alert=True)
            return
        context.chat_data.clear()
        context.chat_data["signal_step"] = "fast_coin"
        await q.edit_message_text(
            f"<b>⚡  Fast Call</b>\n{SEP}\n\n"
            f"🪙  اسم کوین/توکن (یا آدرس قرارداد) رو بنویس:\nمثال: <code>PEPE</code>",
            reply_markup=cancel_kb(), parse_mode=ParseMode.HTML
        )

    elif data == "fastcall_skipdir":
        context.chat_data["direction"] = None
        await _submit_signal(q, context, user, signal_type="fast")


async def _show_active_signals(q, context):
    """فید عمومی — قابل مشاهده برای همه کاربران، شامل رول ثبت‌کننده (بند ۶)."""
    viewer_id = q.from_user.id
    try:
        rows = signals_repo.get_public_feed(limit=PUBLIC_FEED_LIMIT)
    except Exception as e:
        logging.error(f"خطا در خوندن فید عمومی سیگنال‌ها: {e}")
        await q.answer("⚠️  مشکلی پیش اومد، دوباره امتحان کن.", show_alert=True)
        return

    if not rows:
        await q.edit_message_text(
            f"<b>📶  سیگنال‌های فعال</b>\n{SEP}\n\n📭  فعلاً سیگنال بازی نیست",
            reply_markup=back_main_kb(), parse_mode=ParseMode.HTML
        )
        return

    await q.edit_message_text(f"<b>📶  سیگنال‌های فعال ({len(rows)})</b>", parse_mode=ParseMode.HTML)
    for (sid, uid, name, uname, role, coin, direction, entry, sl, tp,
         signal_type, photo_file_id, description, created) in rows:
        display_raw = name or (f"@{uname}" if uname else "کاربر")  # برای متن دکمه (plain text)
        display     = esc(display_raw)                            # برای متن HTML
        role_label = access.get_role_label(role)
        alpha_label = alpha_score.get_label(uid)
        type_label = SIGNAL_TYPE_LABELS.get(signal_type, signal_type)
        dir_part = ""
        if direction:
            emoji = "🟢" if direction == "LONG" else "🔴"
            dir_part = f"  {emoji} {direction}"
        price_part = ""
        if entry or sl or tp:
            price_part = f"💵{entry or '—'}  🛑{sl or '—'}  🎯{tp or '—'}\n"
        caption = (
            f"<b>#{sid}</b>  {type_label}  <b>{esc(coin) or '—'}</b>{dir_part}\n"
            f"👤  {display}  —  {role_label}  •  🎖 {alpha_label}\n"
            f"{price_part}"
            f"🕐  {created[:16]}"
        )
        if description:
            caption += f"\n📝  {esc(description[:200])}"

        # دکمه حمایت مستقیم از تحلیلگر (بند ۱۳) — به‌جز روی سیگنال خودِ بیننده
        support_kb = None
        if uid != viewer_id:
            support_kb = InlineKeyboardMarkup([[btn(f"💝  حمایت از {display_raw}", f"support_{uid}", "primary")]])

        if signal_type == "full" and photo_file_id:
            await safe_send_photo(context.bot, chat_id=q.message.chat_id, photo=photo_file_id,
                                  caption=caption, parse_mode=ParseMode.HTML, reply_markup=support_kb)
        else:
            await safe_send_message(context.bot, chat_id=q.message.chat_id, text=caption,
                                    parse_mode=ParseMode.HTML, reply_markup=support_kb)


async def direction_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """فقط برای فینال‌کردن Fast Call بعد از گرفتن اسم کوین (از طریق دکمه در دایرکت)."""
    q = update.callback_query
    await q.answer()
    user = q.from_user
    # این هندلر با pattern جدا (^dir_) ثبت می‌شه و از common.guard_callback رد نمی‌شه؛
    # پس چک بلاک‌بودن رو خودش صریحاً انجام می‌ده.
    if users_repo.is_blocked(user.id) and user.id not in ADMIN_IDS:
        await q.answer("⛔️ دسترسی شما مسدود شده!", show_alert=True)
        return
    direction = q.data.split("_", 1)[1]
    context.chat_data["direction"] = direction
    await _submit_signal(q, context, user, signal_type="fast")


async def photo_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    دریافت عکس. دو حالت:
    ۱) کپشن با /fullsignal شروع بشه → مستقیم به cmd_fullsignal پاس داده می‌شه.
       (⚠️ CommandHandler استاندارد کتابخانه‌ی تلگرام فقط message.text رو برای
        تشخیص دستور چک می‌کنه، نه message.caption — این با بررسی مستقیم سورس
        کتابخانه تأیید شد. پس عکس‌هایی که کپشن‌شون با یه دستور شروع می‌شه، خودمون
        اینجا صریحاً تشخیص می‌دیم و به هندلر دستور مربوطه delegate می‌کنیم.)
    ۲) در غیر این صورت → فلوی معمول Full Signal در دایرکت (بر اساس chat_data).
    """
    caption = update.message.caption or ""
    first_token = caption.strip().split()[0].lower() if caption.strip() else ""
    if first_token.split("@")[0] == "/fullsignal":
        await cmd_fullsignal(update, context)
        return

    user = update.effective_user
    users_repo.register_user(user.id, user.username, user.full_name)
    if users_repo.is_blocked(user.id) and user.id not in ADMIN_IDS:
        return

    if context.chat_data.get("signal_step") != "full_content":
        await update.message.reply_text("برای ثبت سیگنال، اول از منو «📡 ثبت سیگنال» رو بزن.")
        return

    try:
        photo_file_id = update.message.photo[-1].file_id
    except (IndexError, AttributeError) as e:
        logging.warning(f"خطا در خوندن عکس ارسالی کاربر {user.id}: {e}")
        await update.message.reply_text("⚠️  مشکلی توی خوندن عکس پیش اومد، دوباره امتحان کن.")
        return

    coin, direction = _parse_signal_text(caption)
    context.chat_data["coin"]          = coin
    context.chat_data["direction"]     = direction
    context.chat_data["photo_file_id"] = photo_file_id
    context.chat_data["description"]   = caption
    await _submit_signal(update.message, context, user, signal_type="full")


async def _submit_signal(q_or_msg, context, user, signal_type: str):
    """ثبت نهایی سیگنال (Full یا Fast) در دیتابیس + اطلاع به کاربر و Admin/VIP Helper."""
    d     = context.chat_data
    is_cb = hasattr(q_or_msg, "edit_message_text")

    try:
        signal_id = signals_repo.insert_signal(
            user.id,
            coin=d.get("coin") or "—",
            signal_type=signal_type,
            direction=d.get("direction"),
            description=d.get("description", ""),
            photo_file_id=d.get("photo_file_id", ""),
        )
    except Exception as e:
        logging.error(f"خطا در ذخیره سیگنال کاربر {user.id}: {e}")
        err_text = "❌  مشکلی توی ثبت سیگنال پیش اومد. دوباره امتحان کن."
        if is_cb:
            await q_or_msg.edit_message_text(err_text, reply_markup=back_main_kb())
        else:
            await q_or_msg.reply_text(err_text)
        context.chat_data.clear()
        return

    type_label = SIGNAL_TYPE_LABELS.get(signal_type, signal_type)
    dir_part = ""
    if d.get("direction"):
        emoji = "🟢" if d["direction"] == "LONG" else "🔴"
        dir_part = f"  {emoji} {d['direction']}"

    text = (
        f"✅  <b>سیگنال #{signal_id} ثبت شد!</b>\n{SEP}\n\n"
        f"{type_label}  <b>{esc(d.get('coin')) or '—'}</b>{dir_part}\n"
        f"{SEP}\n\n⏳  منتظر تأیید ادمین/VIP Helper باش..."
    )
    kb = InlineKeyboardMarkup([[btn("🔙  منوی اصلی", "back_main", "primary")]])

    if is_cb:
        await q_or_msg.edit_message_text(text, reply_markup=kb, parse_mode=ParseMode.HTML)
    else:
        await q_or_msg.reply_html(text, reply_markup=kb)

    notify_ids = set(ADMIN_IDS) | {uid for uid, _, _ in staff_repo.list_vip_helpers()}
    admin_caption = (
        f"🔔  <b>سیگنال جدید #{signal_id}</b>  —  {type_label}\n{SEP}\n"
        f"👤  {esc(user.full_name)} (@{esc(user.username) or '—'})\n"
        f"{esc(d.get('coin')) or '—'}{dir_part}"
    )
    if d.get("description"):
        admin_caption += f"\n📝  {esc(d['description'][:300])}"

    for admin_id in notify_ids:
        if signal_type == "full" and d.get("photo_file_id"):
            await safe_send_photo(context.bot, chat_id=admin_id, photo=d["photo_file_id"],
                                  caption=admin_caption, reply_markup=approve_reject_kb(signal_id),
                                  parse_mode=ParseMode.HTML)
        else:
            await safe_send_message(context.bot, chat_id=admin_id, text=admin_caption,
                                    reply_markup=approve_reject_kb(signal_id), parse_mode=ParseMode.HTML)
    context.chat_data.clear()


# ══════════════════════════════════════════════════════════
#  مراحل ورودی متنی (صدا زده می‌شن از handlers/text_router.py)
# ══════════════════════════════════════════════════════════
async def handle_step_fast_coin(update: Update, context: ContextTypes.DEFAULT_TYPE, user, text):
    # عمداً upper/heuristic نمی‌کنیم — این یه فیلد مشخص و صریحه (نه متن آزاد)،
    # ممکنه آدرس قرارداد (حساس به بزرگی/کوچکی حروف) هم باشه.
    coin = text.strip()[:50]
    context.chat_data["coin"] = coin
    await update.message.reply_html(
        f"<b>⚡  Fast Call</b>\n{SEP}\n\n"
        f"🪙  کوین: <b>{esc(coin)}</b>\n\nجهت رو انتخاب کن (اختیاری):",
        reply_markup=direction_kb()
    )


async def handle_step_full_content(update: Update, context: ContextTypes.DEFAULT_TYPE, user, text):
    """Full Signal متنی — وقتی کاربر به‌جای عکس، تحلیلش رو تایپ می‌کنه."""
    coin, direction = _parse_signal_text(text)
    context.chat_data["coin"]          = coin
    context.chat_data["direction"]     = direction
    context.chat_data["description"]   = text
    context.chat_data["photo_file_id"] = ""
    await _submit_signal(update.message, context, user, signal_type="full")


# ══════════════════════════════════════════════════════════
#  دستورهای گروهی — یک‌پیامی و بدون نیاز به state (برای محیط شلوغ گروه)
# ══════════════════════════════════════════════════════════
async def cmd_fastcall(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/fastcall COIN [long|short] — قابل استفاده در گروه یا دایرکت."""
    user = update.effective_user
    users_repo.register_user(user.id, user.username, user.full_name)
    if users_repo.is_blocked(user.id) and user.id not in ADMIN_IDS:
        return

    ok, msg = await _check_daily_limit(user)
    if not ok:
        await update.message.reply_text(msg)
        return

    raw = (update.message.text or "").split(maxsplit=1)
    args_text = raw[1].strip() if len(raw) > 1 else ""
    if not args_text:
        await update.message.reply_text(
            "استفاده: /fastcall COIN [long/short]\nمثال: /fastcall PEPE long"
        )
        return

    tokens = args_text.split()
    coin = tokens[0][:50]
    direction = _detect_direction(args_text)

    context.chat_data.clear()
    context.chat_data["coin"] = coin
    context.chat_data["direction"] = direction
    context.chat_data["description"] = ""
    await _submit_signal(update.message, context, user, signal_type="fast")


async def cmd_fullsignal(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    /fullsignal [کوین] [long/short] [توضیح] — قابل استفاده در گروه یا دایرکت.
    هم به‌صورت متنی تنها، هم به‌صورت کپشنِ یک عکس قابل استفاده‌ست (بدون عکس هم کار می‌کنه).
    """
    user = update.effective_user
    users_repo.register_user(user.id, user.username, user.full_name)
    if users_repo.is_blocked(user.id) and user.id not in ADMIN_IDS:
        return

    ok, msg = await _check_daily_limit(user)
    if not ok:
        await update.message.reply_text(msg)
        return

    raw_text = update.message.text or update.message.caption or ""
    parts = raw_text.split(maxsplit=1)
    args_text = parts[1].strip() if len(parts) > 1 else ""

    photo_file_id = ""
    if update.message.photo:
        try:
            photo_file_id = update.message.photo[-1].file_id
        except (IndexError, AttributeError) as e:
            logging.warning(f"خطا در خوندن عکس /fullsignal کاربر {user.id}: {e}")

    if not photo_file_id and not args_text:
        await update.message.reply_text(
            "لطفاً عکس یا توضیح تحلیلت رو هم بفرست.\n"
            "استفاده: /fullsignal [کوین] [long/short] [توضیح]\n"
            "یا عکس رو با کپشن /fullsignal بفرست."
        )
        return

    coin, direction = _parse_signal_text(args_text)
    context.chat_data.clear()
    context.chat_data["coin"] = coin
    context.chat_data["direction"] = direction
    context.chat_data["description"] = args_text
    context.chat_data["photo_file_id"] = photo_file_id
    await _submit_signal(update.message, context, user, signal_type="full")
