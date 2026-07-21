"""همه‌ی کیبوردهای inline ربات، یک‌جا."""
from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from signal_bot.config.settings import RESULT_LABEL, POINT_TABLE, ROLES


def btn(text, cb, style=None):
    # نکته: تلگرام از رنگی‌کردن دکمه‌های inline پشتیبانی نمی‌کنه.
    # پارامتر style قبلاً مستقیم به InlineKeyboardButton پاس داده می‌شد
    # که با TypeError کرش می‌کرد. امضای تابع رو نگه داشتیم (برای سازگاری با
    # همه‌ی call siteهای موجود)، ولی دیگه style به تلگرام پاس داده نمی‌شه.
    return InlineKeyboardButton(text, callback_data=cb)


def main_menu_kb(is_admin=False, is_vip_helper=False):
    kb = [
        [btn("📡  ثبت سیگنال", "menu_signal", "success"),
         btn("🏆  لیدربورد",   "menu_leader", "primary")],
        [btn("📶  سیگنال‌های فعال","menu_activesignals","success"),
         btn("📊  آمار من",    "menu_stats",  "primary")],
        [btn("💎  استخر جایزه","menu_prize",  "primary"),
         btn("💸  واریز جایزه","menu_donate", "success")],
        [btn("👤  پروفایل",    "menu_profile","primary"),
         btn("📜  سیگنال‌هام", "menu_mysignals", "primary")],
        [btn("🎖️  تابلوی افتخار","menu_halloffame","primary"),
         btn("🎁  پاداش‌های من","menu_myrewards","primary")],
    ]
    if is_admin:
        kb.append([btn("⚙️  پنل ادمین", "menu_admin", "danger")])
    elif is_vip_helper:
        kb.append([btn("📋  بررسی سیگنال‌ها (VIP Helper)", "adm_pending", "primary")])
    return InlineKeyboardMarkup(kb)


def back_main_kb():
    return InlineKeyboardMarkup([[btn("🔙  برگشت به منو", "back_main", "primary")]])


def cancel_kb():
    """برای مراحل میانی یک فلو (مثلاً منتظر عکس/متن) — بر خلاف back_main، state رو هم پاک می‌کنه."""
    return InlineKeyboardMarkup([[btn("🔙  لغو", "cancel", "primary")]])


def signal_menu_kb():
    return InlineKeyboardMarkup([
        [btn("📸  Full Signal", "sigtype_full", "success")],
        [btn("⚡  Fast Call",   "sigtype_fast", "primary")],
        [btn("🔙  برگشت",       "back_main",    "primary")],
    ])


def direction_kb():
    """انتخاب جهت برای Fast Call — اختیاری، قابل رد کردن."""
    return InlineKeyboardMarkup([
        [btn("🟢  LONG  (خرید)", "dir_LONG",  "success"),
         btn("🔴  SHORT (فروش)", "dir_SHORT", "danger")],
        [btn("⏭  رد کردن جهت", "fastcall_skipdir", "primary")],
        [btn("🔙  لغو", "cancel", "primary")],
    ])


def admin_kb():
    return InlineKeyboardMarkup([
        [btn("📋 سیگنال‌های در انتظار","adm_pending","primary"),
         btn("🎯 ثبت نتیجه",           "adm_result", "success")],
        [btn("💰 واریزهای اخیر",      "adm_donations","primary"),
         btn("📢 پیام همگانی",         "adm_broadcast","primary")],
        [btn("📊 آمار کلی",           "adm_stats",   "primary"),
         btn("👥 مدیریت کاربران",     "adm_users",   "primary")],
        [btn("🏆 پایان دوره و جایزه", "adm_endseason","danger"),
         btn("📤 خروجی اکسل",         "adm_export",  "primary")],
        [btn("🆕 شروع فصل جدید",      "adm_newseason","primary"),
         btn("❓ راهنما",              "adm_help",    "primary")],
        [btn("🔙 برگشت","back_main","primary")],
    ])


def approve_reject_kb(sid):
    return InlineKeyboardMarkup([[
        btn("✅  تأیید", f"approve_{sid}", "success"),
        btn("❌  رد",    f"reject_{sid}",  "danger"),
    ]])


def signal_result_kb(signal_id):
    styles = {"win_10x":"success","win_5x":"success","win_2x":"success",
              "win_sl":"primary","loss":"danger"}
    rows = []
    for key, label in RESULT_LABEL.items():
        if key == "open":
            continue
        pt   = POINT_TABLE[key]
        sign = "+" if pt >= 0 else ""
        rows.append([btn(f"{label}  ({sign}{pt}pt)",
                         f"setresult_{signal_id}_{key}",
                         styles.get(key,"primary"))])
    rows.append([btn("🔙 لغو","cancel","primary")])
    return InlineKeyboardMarkup(rows)


def donate_amount_kb():
    return InlineKeyboardMarkup([
        [btn("5$","donate_5","primary"),   btn("10$","donate_10","primary"),
         btn("20$","donate_20","primary")],
        [btn("50$","donate_50","success"), btn("100$","donate_100","success"),
         btn("200$","donate_200","success")],
        [btn("✏️  مبلغ دلخواه","donate_custom","primary")],
        [btn("🔙  برگشت","back_main","primary")],
    ])


def payment_link_kb(invoice_url: str, donate_id: int):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("💳  پرداخت آنلاین", url=invoice_url)],
        [btn("🔄  چک وضعیت پرداخت",f"checkpay_{donate_id}","primary")],
        [btn("🔙  برگشت به منو","back_main","primary")],
    ])


def caller_support_amount_kb(recipient_id):
    amounts = [5, 10, 20, 50]
    rows = [[btn(f"{a}$", f"csupport_{recipient_id}_{a}", "primary") for a in amounts[:2]],
            [btn(f"{a}$", f"csupport_{recipient_id}_{a}", "success") for a in amounts[2:]],
            [btn("✏️  مبلغ دلخواه", f"csupport_{recipient_id}_custom", "primary")],
            [btn("🔙  لغو", "cancel", "primary")]]
    return InlineKeyboardMarkup(rows)


def caller_support_payment_link_kb(invoice_url: str, donate_id: int):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("💳  پرداخت آنلاین", url=invoice_url)],
        [btn("🔄  چک وضعیت پرداخت", f"checkcsupport_{donate_id}", "primary")],
        [btn("🔙  برگشت به منو", "back_main", "primary")],
    ])


def leader_kb(active="week"):
    return InlineKeyboardMarkup([
        [btn(f"📅 هفتگی{'✓' if active=='week' else ''}",  "leader_week",  "success" if active=="week"  else "primary"),
         btn(f"🗓 ماهانه{'✓' if active=='month' else ''}", "leader_month", "success" if active=="month" else "primary"),
         btn(f"🌟 همه وقت{'✓' if active=='all' else ''}",  "leader_all",   "success" if active=="all"   else "primary")],
        [btn("🔙  برگشت","back_main","primary")],
    ])


def mysignals_filter_kb():
    return InlineKeyboardMarkup([
        [btn("⏳ باز","mysig_open","primary"),
         btn("✅ تأیید","mysig_approved","success"),
         btn("❌ رد شده","mysig_rejected","danger")],
        [btn("🔙 برگشت","back_main","primary")],
    ])


def user_manage_kb(target_id, is_blocked_now, is_vip_helper_now=False):
    block_text = "🔓 آنبلاک" if is_blocked_now else "🔒 بلاک"
    block_cb   = f"unblock_{target_id}" if is_blocked_now else f"block_{target_id}"
    block_style= "success" if is_blocked_now else "danger"
    vip_text   = "🔻 حذف VIP Helper" if is_vip_helper_now else "💎 ارتقا به VIP Helper"
    vip_cb     = f"vip_remove_{target_id}" if is_vip_helper_now else f"vip_add_{target_id}"
    return InlineKeyboardMarkup([
        [btn(block_text, block_cb, block_style),
         btn("⭐ تنظیم امتیاز", f"setpts_{target_id}", "primary")],
        [btn("🎖 تغییر رول", f"setrole_{target_id}", "primary")],
        [btn("🎁 اعطای پاداش", f"grantreward_{target_id}", "success")],
        [btn(vip_text, vip_cb, "primary")],
        [btn("🔙 برگشت","adm_users","primary")],
    ])


def role_picker_kb(target_id):
    rows = [[btn(label, f"role_{target_id}_{key}", "primary")] for key, label in ROLES]
    rows.append([btn("🔙 لغو", "cancel", "primary")])
    return InlineKeyboardMarkup(rows)
