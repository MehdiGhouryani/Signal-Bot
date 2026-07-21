"""
تنظیمات مرکزی ربات — همه‌ی مقادیر قابل‌تغییر یک‌جا اینجا هستن.
⚠️ هیچ مقدار حساسی (توکن، کلید API) اینجا هاردکد نشه — همه از .env خونده می‌شه.
"""
import os
import sys
import logging

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass  # python-dotenv نصب نیست؛ باید متغیرهای محیطی رو خودت export کنی

# ══════════════════════════════════════════════════════════
#  مقادیر حساس — از فایل .env (هیچ‌وقت مستقیم اینجا ننویس)
# ══════════════════════════════════════════════════════════
TOKEN           = os.environ.get("BOT_TOKEN", "")
ADMIN_IDS       = [int(x) for x in os.environ.get("ADMIN_IDS", "").split(",") if x.strip().isdigit()]
NOWPAYMENTS_API = os.environ.get("NOWPAYMENTS_API_KEY", "")
SUCCESS_URL     = os.environ.get("SUCCESS_URL", "")
CHANNEL_ID      = os.environ.get("CHANNEL_ID", "")   # کانال برای پست خودکار (یا خالی بذار "")
DB_FILE         = os.environ.get("DB_FILE", "signals.db")

NOWPAYMENTS_BASE = "https://api.nowpayments.io/v1"
SEP  = "━━━━━━━━━━━━━━━━━━━━━━━━"
SEP2 = "▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰"

# ══════════════════════════════════════════════════════════
#  تنظیمات قابل‌تغییر بازی/امتیازدهی
#  (فاز بعدی: این‌ها به یک فایل/جدول تنظیمات جدا و ادیت‌پذیر
#   از پنل ادمین منتقل می‌شن — همون‌طور که در بند ۱۷ نیازمندی‌ها اومده)
# ══════════════════════════════════════════════════════════

# سطح‌بندی کاربران (بر اساس امتیاز خام — مجزا از «رول»ی که در فاز ۲ اضافه می‌شه)
LEVELS = [
    (0,    "🪨 مبتدی"),
    (50,   "⚔️ معامله‌گر"),
    (150,  "💫 حرفه‌ای"),
    (300,  "💎 الماس"),
    (500,  "👑 لجند"),
    (1000, "🔱 گرندماستر"),
]

# امتیازدهی نتیجه سیگنال
POINT_TABLE = {
    "win_10x": 10,
    "win_5x":   5,
    "win_2x":   3,
    "win_sl":   2,
    "loss":    -1,
}
RESULT_LABEL = {
    "win_10x": "🚀 بالای ۱۰ایکس",
    "win_5x":  "💎 ۵ تا ۱۰ایکس",
    "win_2x":  "✅ ۲ تا ۵ایکس",
    "win_sl":  "🎯 SL/TP عالی",
    "loss":    "❌ ضرر",
    "open":    "⏳ باز",
}

# استریک بونوس: {تعداد استریک متوالی: امتیاز بونوس}
STREAK_BONUS = {3: 2, 5: 5, 10: 15}

# محدودیت روزانه ثبت سیگنال — پیش‌فرض/fallback (وقتی رول کاربر در ROLE_DAILY_LIMITS نباشه)
DAILY_LIMIT = 5

# ══════════════════════════════════════════════════════════
#  رول‌های کاربری (Roles) — بند ۲ و ۳ نیازمندی‌ها
#  ⚠️ این‌ها کاملاً مجزا از «سطح» (LEVELS) بالا هستن:
#     سطح خودکار و بر اساس امتیازه، رول فقط دستی و توسط ادمین تغییر می‌کنه
#     و محدودیت ثبت سیگنال رو تعیین می‌کنه.
# ══════════════════════════════════════════════════════════
ROLES = [
    ("rookie",   "🐣 Memeland Rookie"),
    ("explorer", "🐸 Memeland Explorer"),
    ("guardian", "🦈 Memeland Guardian"),
    ("alpha",    "🚀 Memeland Alpha Master"),
    ("og",       "👑 Memeland OG"),
]
ROLE_LABELS = dict(ROLES)          # {"rookie": "🐣 Memeland Rookie", ...}
DEFAULT_ROLE = "rookie"

# محدودیت روزانه ثبت سیگنال به‌ازای هر رول — رول‌های بالاتر محدودیت کمتر (آزادتر) دارن.
# قابل تغییره بدون دست‌زدن به منطق کد (فاز بعدی: قابل ادیت از پنل تنظیمات).
ROLE_DAILY_LIMITS = {
    "rookie":   3,
    "explorer": 5,
    "guardian": 8,
    "alpha":    15,
    "og":       50,
}

# رول‌های مدیریتی — Admin از ADMIN_IDS (env) میاد، VIP Helper از جدول staff در دیتابیس
# (تا ادمین بتونه بدون دست‌زدن به .env، هر وقت خواست کمک‌ادمین اضافه/حذف کنه).
ADMIN_ROLE_ADMIN      = "admin"
ADMIN_ROLE_VIP_HELPER = "vip_helper"
ADMIN_ROLE_LABELS = {
    ADMIN_ROLE_ADMIN:      "👑 Admin",
    ADMIN_ROLE_VIP_HELPER: "💎 VIP Helper",
}

# ══════════════════════════════════════════════════════════
#  انواع سیگنال — بند ۴ نیازمندی‌ها (فاز ۳)
# ══════════════════════════════════════════════════════════
SIGNAL_TYPE_LABELS = {
    "full": "📸 Full Signal",
    "fast": "⚡ Fast Call",
}

# تعداد سیگنال نمایش‌داده‌شده در فید عمومی «سیگنال‌های فعال»
PUBLIC_FEED_LIMIT = 10

# ══════════════════════════════════════════════════════════
#  Alpha Score — بند ۸ نیازمندی‌ها (فاز ۴)
#  z = 1.96 یعنی بازه اطمینان ۹۵٪ (استاندارد رایج آماری برای Wilson score).
#  اگه بعداً خواستی محافظه‌کارتر/آزادتر بشه، فقط همین عدد رو عوض کن.
# ══════════════════════════════════════════════════════════
ALPHA_SCORE_CONFIDENCE_Z = 1.96

# ══════════════════════════════════════════════════════════
#  Prize Pool Webhook (IPN) — فاز ۵
#  اگه IPN_SECRET خالی باشه، وب‌هوک اصلاً استارت نمی‌شه و فقط چک دستی کار می‌کنه
#  (برگشت امن به رفتار قبلی، بدون کرش).
# ══════════════════════════════════════════════════════════
NOWPAYMENTS_IPN_SECRET = os.environ.get("NOWPAYMENTS_IPN_SECRET", "")
IPN_CALLBACK_URL       = os.environ.get("IPN_CALLBACK_URL", "")   # آدرس عمومی HTTPS، مثل https://yourdomain.com/nowpayments-ipn
IPN_WEBHOOK_HOST       = os.environ.get("IPN_WEBHOOK_HOST", "0.0.0.0")
IPN_WEBHOOK_PORT       = int(os.environ.get("IPN_WEBHOOK_PORT", "8443"))
IPN_WEBHOOK_PATH       = "/nowpayments-ipn"


def setup_logging():
    """راه‌اندازی logging — فقط یک‌بار از main.py صدا زده می‌شه."""
    logging.basicConfig(
        format="%(asctime)s | %(levelname)s | %(message)s",
        level=logging.INFO,
        handlers=[
            logging.FileHandler("bot.log", encoding="utf-8"),
            logging.StreamHandler()
        ]
    )


def validate():
    """
    بررسی صحت تنظیمات ضروری قبل از استارت واقعی ربات.

    عمداً این چک در زمان import این فایل اجرا نمی‌شه (برخلاف نسخه فاز ۰)،
    چون import کردن این ماژول (مثلاً برای تست یا اسکریپت مهاجرت دیتابیس)
    نباید صرفاً به‌خاطر نبود .env با sys.exit متوقف بشه. این تابع رو
    main.py صراحتاً و فقط موقع اجرای واقعی ربات صدا می‌زنه.
    """
    if not TOKEN:
        sys.exit("❌  BOT_TOKEN تنظیم نشده! فایل .env رو بر اساس .env.example پر کن.")
    if not ADMIN_IDS:
        logging.warning("⚠️  ADMIN_IDS خالیه — هیچ‌کس دسترسی ادمین نداره تا وقتی تنظیمش کنی.")
