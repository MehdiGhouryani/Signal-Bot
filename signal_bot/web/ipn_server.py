"""
سرور وب‌هوک IPN نوپیمنتس (فاز ۵ — سخت‌سازی Prize Pool).

⚠️ محدودیت صادقانه: این کد بر اساس مستندات رسمی NOWPayments پیاده‌سازی شده،
ولی چون سندباکس من به سرورهای NOWPayments یا اینترنت عمومی (برای گرفتن یک IPN
واقعی) دسترسی نداره، نتونستم انتها-به-انتها تستش کنم — فقط منطق داخلی (تایید
امضا، routing، آپدیت دیتابیس، اطلاع‌رسانی) با داده‌ی شبیه‌سازی‌شده تست شده.
قبل از اعتماد کامل، با یک پرداخت واقعی کوچیک تستش کن. دکمه‌ی «چک وضعیت پرداخت»
دستی هم به‌عنوان fallback هنوز کار می‌کنه، مستقل از این وب‌هوک.

اگه NOWPAYMENTS_IPN_SECRET در .env خالی باشه، این سرور اصلاً استارت نمی‌شه —
ربات فقط با چک دستی کار می‌کنه (رفتار امن پیش‌فرض، بدون کرش).
"""
import json
import logging

from aiohttp import web

from signal_bot.config import settings
from signal_bot.db import prize_repo, caller_donations_repo
from signal_bot.services.ipn_signature import verify_signature
from signal_bot.services.notify import safe_send_message

STATUS_MAP = {"finished": "paid", "confirmed": "paid", "sending": "paid",
              "expired": "failed", "failed": "failed"}


async def _handle_pool_payment(bot, order_id, payment_id, new_status):
    row = prize_repo.get_donation_by_order_id(order_id)
    if not row:
        logging.warning(f"IPN: سفارش استخر جایزه با order_id={order_id} پیدا نشد")
        return False
    donate_id, user_id, current_status = row
    if payment_id:
        prize_repo.set_payment_id(donate_id, payment_id)
    if new_status == "paid" and current_status != "paid":
        prize_repo.set_donation_paid(donate_id)
        await safe_send_message(bot, chat_id=user_id,
            text="✅  <b>پرداخت شما به استخر جایزه تأیید شد!</b>\n\nممنون از حمایتت 🙏",
            parse_mode="HTML")
        for admin_id in settings.ADMIN_IDS:
            await safe_send_message(bot, chat_id=admin_id,
                text=f"💰  <b>پرداخت خودکار تأیید شد (وب‌هوک)!</b>\n👤 {user_id}\nسفارش: {order_id}",
                parse_mode="HTML")
    return True


async def _handle_support_payment(bot, order_id, payment_id, new_status):
    row = caller_donations_repo.get_donation_by_order_id(order_id)
    if not row:
        logging.warning(f"IPN: سفارش حمایت مستقیم با order_id={order_id} پیدا نشد")
        return False
    donate_id, donor_id, recipient_id, amount, current_status = row
    if payment_id:
        caller_donations_repo.set_payment_id(donate_id, payment_id)
    if new_status == "paid" and current_status != "paid":
        caller_donations_repo.set_donation_paid(donate_id)
        await safe_send_message(bot, chat_id=donor_id,
            text=f"✅  <b>حمایت {amount}$ شما تأیید شد!</b>\n\nممنون 🙏", parse_mode="HTML")
        await safe_send_message(bot, chat_id=recipient_id,
            text=f"💝  <b>یه نفر ازت حمایت کرد!</b>\n💵 {amount}$\n\nهمینطوری ادامه بده! 🚀",
            parse_mode="HTML")
        for admin_id in settings.ADMIN_IDS:
            await safe_send_message(bot, chat_id=admin_id,
                text=f"💝  <b>حمایت مستقیم تأیید شد (وب‌هوک)!</b>\nسفارش: {order_id}", parse_mode="HTML")
    return True


def create_ipn_app(bot) -> web.Application:
    """ساخت اپلیکیشن aiohttp. bot برای فرستادن پیام تلگرام بعد از تأیید پرداخت لازمه."""

    async def handle_ipn(request: web.Request) -> web.Response:
        raw_body = await request.read()
        signature = request.headers.get("x-nowpayments-sig", "")

        try:
            payload = json.loads(raw_body)
        except (json.JSONDecodeError, UnicodeDecodeError) as e:
            logging.warning(f"IPN: بدنه‌ی نامعتبر JSON دریافت شد: {e}")
            return web.Response(status=400, text="invalid json")

        if not verify_signature(payload, signature, settings.NOWPAYMENTS_IPN_SECRET):
            logging.warning("IPN: امضای نامعتبر — درخواست رد شد (شاید جعلی یا سکرت اشتباه)")
            return web.Response(status=401, text="invalid signature")

        order_id   = str(payload.get("order_id", ""))
        payment_id = str(payload.get("payment_id", "")) or None
        raw_status = payload.get("payment_status", "")
        new_status = STATUS_MAP.get(raw_status, "pending")

        try:
            if order_id.startswith("pool_"):
                found = await _handle_pool_payment(bot, order_id, payment_id, new_status)
            elif order_id.startswith("support_"):
                found = await _handle_support_payment(bot, order_id, payment_id, new_status)
            else:
                logging.warning(f"IPN: order_id با پیشوند ناشناخته: {order_id!r}")
                return web.Response(status=200, text="ignored: unknown order_id prefix")
        except Exception as e:
            # هر خطای غیرمنتظره‌ای (DB، تلگرام و...) رو لاگ می‌کنیم ولی همچنان 200
            # برمی‌گردونیم تا NOWPayments دوباره و دوباره retry نکنه برای چیزی که
            # از سمت ما قابل حل نیست بدون بررسی دستی؛ خطا از لاگ قابل پیگیریه.
            logging.error(f"IPN: خطای غیرمنتظره در پردازش order_id={order_id}: {e}")
            return web.Response(status=200, text="error logged")

        if not found:
            return web.Response(status=200, text="ignored: order not found locally")
        return web.Response(status=200, text="OK")

    app = web.Application()
    app.router.add_post(settings.IPN_WEBHOOK_PATH, handle_ipn)
    return app


async def start_ipn_server(bot):
    """
    اگه IPN تنظیم نشده باشه (سکرت خالی)، هیچ سروری استارت نمی‌شه — برمی‌گرده None.
    فراخواننده (main.py) باید runner رو نگه داره تا موقع خاموش‌شدن ربات cleanup کنه.
    """
    if not settings.NOWPAYMENTS_IPN_SECRET:
        logging.info("NOWPAYMENTS_IPN_SECRET تنظیم نشده — وب‌هوک IPN غیرفعال می‌مونه (فقط چک دستی).")
        return None

    app = create_ipn_app(bot)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, settings.IPN_WEBHOOK_HOST, settings.IPN_WEBHOOK_PORT)
    await site.start()
    logging.info(f"وب‌هوک IPN روی {settings.IPN_WEBHOOK_HOST}:{settings.IPN_WEBHOOK_PORT}{settings.IPN_WEBHOOK_PATH} استارت شد.")
    return runner
