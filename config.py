import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_IDS = [int(x) for x in os.getenv("ADMIN_IDS", "").split(",") if x]

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
