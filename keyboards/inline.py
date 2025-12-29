from telegram import InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton

def user_reply_keyboard():
    """Menu cố định ở dưới cho user"""
    keyboard = [
        [KeyboardButton("📜 Lịch sử"), KeyboardButton("💰 Số dư")],
        [KeyboardButton("🛒 Danh mục"), KeyboardButton("➕ Nạp tiền")],
        [KeyboardButton("💸 Rút tiền")],
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

def admin_reply_keyboard():
    """Menu cố định ở dưới cho admin"""
    keyboard = [
        [KeyboardButton("📦 Quản lý SP"), KeyboardButton("📥 Thêm stock")],
        [KeyboardButton("💳 Duyệt rút tiền"), KeyboardButton("🏦 Cài đặt NH")],
        [KeyboardButton("❌ Thoát Admin")],
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

def main_menu_keyboard():
    keyboard = [
        [InlineKeyboardButton("🛒 Mua hàng", callback_data="shop")],
        [InlineKeyboardButton("💰 Nạp tiền", callback_data="deposit")],
        [InlineKeyboardButton("👤 Tài khoản", callback_data="account")],
        [InlineKeyboardButton("📜 Lịch sử mua", callback_data="history")],
    ]
    return InlineKeyboardMarkup(keyboard)

def admin_menu_keyboard():
    keyboard = [
        [InlineKeyboardButton("📦 Quản lý sản phẩm", callback_data="admin_products")],
        [InlineKeyboardButton("📥 Thêm stock", callback_data="admin_add_stock")],
        [InlineKeyboardButton("💸 Duyệt rút tiền", callback_data="admin_withdraws")],
        [InlineKeyboardButton("🏦 Cài đặt ngân hàng", callback_data="admin_bank_settings")],
        [InlineKeyboardButton("🔙 Quay lại", callback_data="back_main")],
    ]
    return InlineKeyboardMarkup(keyboard)

def products_keyboard(products):
    keyboard = []
    for p in products:
        status = f"còn {p['stock']}" if p['stock'] > 0 else "hết hàng"
        keyboard.append([
            InlineKeyboardButton(
                f"{p['name']} — {p['price']:,}đ ({status})",
                callback_data=f"buy_{p['id']}"
            )
        ])
    keyboard.append([InlineKeyboardButton("🔄 Làm mới", callback_data="shop")])
    keyboard.append([InlineKeyboardButton("🔙 Quay lại", callback_data="back_main")])
    return InlineKeyboardMarkup(keyboard)

def confirm_buy_keyboard(product_id, stock=1, max_can_buy=1):
    """Keyboard xác nhận mua - user sẽ nhập số lượng"""
    keyboard = [
        [InlineKeyboardButton("❌ Hủy", callback_data="shop")],
    ]
    return InlineKeyboardMarkup(keyboard)

def deposit_amounts_keyboard():
    amounts = [10000, 20000, 50000, 100000, 200000, 500000]
    keyboard = []
    for i in range(0, len(amounts), 2):
        row = [InlineKeyboardButton(f"{amounts[i]:,}đ", callback_data=f"deposit_{amounts[i]}")]
        if i + 1 < len(amounts):
            row.append(InlineKeyboardButton(f"{amounts[i+1]:,}đ", callback_data=f"deposit_{amounts[i+1]}"))
        keyboard.append(row)
    keyboard.append([InlineKeyboardButton("🔙 Quay lại", callback_data="back_main")])
    return InlineKeyboardMarkup(keyboard)

def back_keyboard(callback_data="back_main"):
    return InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Quay lại", callback_data=callback_data)]])

def admin_products_keyboard(products):
    keyboard = []
    for p in products:
        keyboard.append([
            InlineKeyboardButton(f"❌ {p['name']}", callback_data=f"admin_del_{p['id']}")
        ])
    keyboard.append([InlineKeyboardButton("➕ Thêm sản phẩm", callback_data="admin_add_product")])
    keyboard.append([InlineKeyboardButton("🔙 Quay lại", callback_data="admin")])
    return InlineKeyboardMarkup(keyboard)

def admin_stock_keyboard(products):
    keyboard = []
    for p in products:
        keyboard.append([
            InlineKeyboardButton(f"{p['name']} (còn {p['stock']})", callback_data=f"admin_stock_{p['id']}")
        ])
    keyboard.append([InlineKeyboardButton("🔙 Quay lại", callback_data="admin")])
    return InlineKeyboardMarkup(keyboard)

def pending_deposits_keyboard(deposits):
    keyboard = []
    for d in deposits:
        keyboard.append([
            InlineKeyboardButton(f"✅ #{d[0]} - {d[2]:,}đ", callback_data=f"admin_confirm_{d[0]}"),
            InlineKeyboardButton("❌", callback_data=f"admin_cancel_{d[0]}")
        ])
    keyboard.append([InlineKeyboardButton("🔙 Quay lại", callback_data="admin")])
    return InlineKeyboardMarkup(keyboard)

def pending_withdrawals_keyboard(withdrawals):
    keyboard = []
    for w in withdrawals:
        # Nút xem chi tiết + QR
        keyboard.append([
            InlineKeyboardButton(f"👁 #{w[0]} - {w[2]:,}đ", callback_data=f"admin_view_{w[0]}")
        ])
    keyboard.append([InlineKeyboardButton("🔙 Quay lại", callback_data="admin")])
    return InlineKeyboardMarkup(keyboard)
