import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_IDS = [int(x.strip()) for x in os.getenv("ADMIN_IDS", "").split(",") if x.strip()]

# SePay settings
SEPAY_API_TOKEN = os.getenv("SEPAY_API_TOKEN", "")
SEPAY_BANK_NAME = os.getenv("SEPAY_BANK_NAME", "")
SEPAY_ACCOUNT_NUMBER = os.getenv("SEPAY_ACCOUNT_NUMBER", "")
SEPAY_ACCOUNT_NAME = os.getenv("SEPAY_ACCOUNT_NAME", "")

# Binance Pay settings
BINANCE_PAY_ID = os.getenv("BINANCE_PAY_ID", "")
USDT_RATE = int(os.getenv("USDT_RATE", "25000"))

# MoMo settings (optional)
MOMO_PHONE = os.getenv("MOMO_PHONE", "")
MOMO_NAME = os.getenv("MOMO_NAME", "")
