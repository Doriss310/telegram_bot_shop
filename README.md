# 🤖 Telegram Shop Bot

Bot Telegram bán hàng tự động, tích hợp nạp tiền tự động qua SePay.

## ✨ Tính năng

### 👤 User
| Button | Chức năng |
|--------|-----------|
| 🆔 User ID | Xem ID Telegram |
| 💰 Số dư | Xem số dư tài khoản |
| 🛒 Danh mục | Xem và mua sản phẩm |
| ➕ Nạp tiền | Nạp tiền tự động qua SePay |
| 💸 Rút tiền | Gửi yêu cầu rút tiền |

### 🔐 Admin (`/admin`)
| Chức năng | Mô tả |
|-----------|-------|
| 📦 Quản lý sản phẩm | Thêm/Xóa sản phẩm |
| 📥 Thêm stock | Thêm nội dung sản phẩm |
| 💸 Duyệt rút tiền | Duyệt/Hủy yêu cầu rút |

## 💰 Hệ thống thanh toán

### Nạp tiền (Tự động qua SePay)
1. User chọn mệnh giá → Nhận mã nạp tiền
2. User chuyển khoản đúng nội dung
3. SePay gửi webhook → Bot tự động cộng tiền

### Rút tiền (Admin duyệt)
1. User gửi yêu cầu rút
2. Admin duyệt → Chuyển tiền thủ công

## 🛠️ Cài đặt

### 1. Cài dependencies
```bash
pip install -r requirements.txt
```

### 2. Cấu hình `.env`
```env
BOT_TOKEN=your_bot_token
ADMIN_IDS=123456789

# SePay (nạp tiền tự động)
SEPAY_API_KEY=your_sepay_api_key
SEPAY_BANK_NAME=MBBank
SEPAY_ACCOUNT_NUMBER=0123456789
SEPAY_ACCOUNT_NAME=NGUYEN VAN A

# Webhook port
WEBHOOK_PORT=8080
```

### 3. Cấu hình SePay
1. Đăng ký tại [sepay.vn](https://sepay.vn)
2. Thêm tài khoản ngân hàng/ví
3. Vào **Cài đặt** → **Webhook** → Thêm URL:
   ```
   https://your-domain.com/webhook/sepay
   ```
4. Copy API Key vào `.env`

### 4. Chạy bot
```bash
# Chạy cả bot + webhook server
python run.py

# Hoặc chạy riêng
python bot.py          # Chỉ bot (không có nạp tự động)
python webhook.py      # Chỉ webhook server
```

## 📁 Cấu trúc

```
├── run.py              # Chạy bot + webhook
├── bot.py              # Bot Telegram
├── webhook.py          # SePay webhook server
├── config.py           # Cấu hình
├── handlers/
│   ├── start.py        # Menu chính
│   ├── shop.py         # Mua hàng, nạp/rút tiền
│   └── admin.py        # Admin panel
├── database/
│   └── db.py           # SQLite database
└── keyboards/
    └── inline.py       # Keyboards
```

## 📝 License

MIT License
