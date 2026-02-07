from telegram import InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton

def user_reply_keyboard(lang: str = 'vi'):
    if lang == 'en':
        # English: Only Binance deposit (foreigners can't use SePay)
        keyboard = [
            [KeyboardButton("🛒 Shop"), KeyboardButton("💰 Balance")],
            [KeyboardButton("🔶 Deposit"), KeyboardButton("📜 History")],
            [KeyboardButton("🌐 Language")],
        ]
    else:
        # Vietnamese: Both SePay (VND) and Binance (USDT)
        keyboard = [
            [KeyboardButton("🛒 Danh mục"), KeyboardButton("💰 Số dư")],
            [KeyboardButton("➕ Nạp tiền"), KeyboardButton("💸 Rút tiền")],
            [KeyboardButton("💵 Nạp USDT"), KeyboardButton("📜 Lịch sử")],
            [KeyboardButton("🌐 Ngôn ngữ")],
        ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

def admin_reply_keyboard():
    keyboard = [
        [KeyboardButton("📦 Quản lý SP"), KeyboardButton("📥 Thêm stock")],
        [KeyboardButton("📋 Xem stock"), KeyboardButton("📜 Code đã bán")],
        [KeyboardButton("✅ Duyệt giao dịch"), KeyboardButton("🏦 Cài đặt NH")],
        [KeyboardButton("🚪 Thoát Admin")],
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

def main_menu_keyboard():
    keyboard = [
        [InlineKeyboardButton(" Mua hàng", callback_data="shop")],
        [InlineKeyboardButton(" Nạp tiền", callback_data="deposit")],
        [InlineKeyboardButton(" Tài khoản", callback_data="account")],
        [InlineKeyboardButton(" Lịch sử mua", callback_data="history")],
    ]
    return InlineKeyboardMarkup(keyboard)

def admin_menu_keyboard():
    keyboard = [
        [InlineKeyboardButton("📦 Quản lý sản phẩm", callback_data="admin_products")],
        [InlineKeyboardButton("📥 Thêm stock", callback_data="admin_add_stock")],
        [InlineKeyboardButton("📋 Xem stock", callback_data="admin_manage_stock")],
        [InlineKeyboardButton("📜 Xem code đã bán", callback_data="admin_sold_codes")],
        [InlineKeyboardButton("💸 Duyệt rút tiền", callback_data="admin_withdraws")],
        [InlineKeyboardButton("🏦 Cài đặt ngân hàng", callback_data="admin_bank_settings")],
        [InlineKeyboardButton("🔙 Quay lại", callback_data="back_main")],
    ]
    return InlineKeyboardMarkup(keyboard)

def admin_sold_codes_keyboard(products):
    """Keyboard chọn sản phẩm để xem code đã bán"""
    keyboard = []
    for p in products:
        keyboard.append([InlineKeyboardButton(f"📦 {p['name']}", callback_data=f"admin_soldby_product_{p['id']}")])
    keyboard.append([InlineKeyboardButton("🔍 Tìm theo User ID", callback_data="admin_soldby_user")])
    keyboard.append([InlineKeyboardButton("🔙 Quay lại", callback_data="admin")])
    return InlineKeyboardMarkup(keyboard)

def products_keyboard(products, lang: str = 'vi'):
    keyboard = []
    for p in products:
        if lang == 'en':
            # English: show USDT price only
            status = f"in stock {p['stock']}" if p['stock'] > 0 else "out of stock"
            if p.get('price_usdt') and p['price_usdt'] > 0:
                price_text = f"{p['price_usdt']} USDT"
            else:
                price_text = "N/A"
        else:
            # Vietnamese: show VND price (USDT option available when buying)
            status = f"còn {p['stock']}" if p['stock'] > 0 else "hết hàng"
            price_text = f"{p['price']:,}đ"
        keyboard.append([
            InlineKeyboardButton(f"{p['name']} - {price_text} ({status})", callback_data=f"buy_{p['id']}")
        ])
    refresh_text = "🔄 Refresh" if lang == 'en' else "🔄 Làm mới"
    back_text = "🔙 Back" if lang == 'en' else "🔙 Quay lại"
    keyboard.append([InlineKeyboardButton(refresh_text, callback_data="shop")])
    keyboard.append([InlineKeyboardButton(back_text, callback_data="back_main")])
    return InlineKeyboardMarkup(keyboard)

def confirm_buy_keyboard(product_id, stock=1, max_can_buy=1):
    keyboard = [[InlineKeyboardButton(" Hủy", callback_data="shop")]]
    return InlineKeyboardMarkup(keyboard)

def deposit_amounts_keyboard():
    amounts = [10000, 20000, 50000, 100000, 200000, 500000]
    keyboard = []
    for i in range(0, len(amounts), 2):
        row = [InlineKeyboardButton(f"{amounts[i]:,}đ", callback_data=f"deposit_{amounts[i]}")]
        if i + 1 < len(amounts):
            row.append(InlineKeyboardButton(f"{amounts[i+1]:,}đ", callback_data=f"deposit_{amounts[i+1]}"))
        keyboard.append(row)
    keyboard.append([InlineKeyboardButton(" Quay lại", callback_data="back_main")])
    return InlineKeyboardMarkup(keyboard)

def back_keyboard(callback_data="back_main"):
    return InlineKeyboardMarkup([[InlineKeyboardButton(" Quay lại", callback_data=callback_data)]])

def admin_products_keyboard(products):
    keyboard = []
    for p in products:
        keyboard.append([
            InlineKeyboardButton(f"📦 {p['name']} - {p['price']:,}đ", callback_data=f"admin_viewprod_{p['id']}"),
            InlineKeyboardButton("❌", callback_data=f"admin_del_{p['id']}")
        ])
    keyboard.append([InlineKeyboardButton("➕ Thêm sản phẩm", callback_data="admin_add_product")])
    keyboard.append([InlineKeyboardButton("🔙 Quay lại", callback_data="admin")])
    return InlineKeyboardMarkup(keyboard)

def admin_stock_keyboard(products):
    keyboard = []
    for p in products:
        keyboard.append([InlineKeyboardButton(f"{p['name']} (còn {p['stock']})", callback_data=f"admin_stock_{p['id']}")])
    keyboard.append([InlineKeyboardButton(" Quay lại", callback_data="admin")])
    return InlineKeyboardMarkup(keyboard)

def admin_view_stock_keyboard(products):
    keyboard = []
    for p in products:
        keyboard.append([InlineKeyboardButton(f" {p['name']} ({p['stock']} stock)", callback_data=f"admin_viewstock_{p['id']}")])
    keyboard.append([InlineKeyboardButton(" Quay lại", callback_data="admin")])
    return InlineKeyboardMarkup(keyboard)

def admin_stock_list_keyboard(stocks, product_id, page=0, per_page=10):
    keyboard = []
    start = page * per_page
    end = start + per_page
    page_stocks = stocks[start:end]
    for s in page_stocks:
        stock_id, content, sold = s
        status = "" if sold else ""
        short_content = content[:20] + "..." if len(content) > 20 else content
        keyboard.append([InlineKeyboardButton(f"{status} {short_content}", callback_data=f"admin_stockdetail_{stock_id}")])
    nav_row = []
    if page > 0:
        nav_row.append(InlineKeyboardButton(" Trước", callback_data=f"admin_stockpage_{product_id}_{page-1}"))
    if end < len(stocks):
        nav_row.append(InlineKeyboardButton("Sau ", callback_data=f"admin_stockpage_{product_id}_{page+1}"))
    if nav_row:
        keyboard.append(nav_row)
    keyboard.append([InlineKeyboardButton(" Quay lại", callback_data="admin_manage_stock")])
    return InlineKeyboardMarkup(keyboard)

def admin_stock_detail_keyboard(stock_id, product_id):
    keyboard = [
        [InlineKeyboardButton(" Sửa nội dung", callback_data=f"admin_editstock_{stock_id}")],
        [InlineKeyboardButton(" Xóa stock", callback_data=f"admin_delstock_{stock_id}_{product_id}")],
        [InlineKeyboardButton(" Quay lại", callback_data=f"admin_viewstock_{product_id}")],
    ]
    return InlineKeyboardMarkup(keyboard)

def pending_deposits_keyboard(deposits):
    keyboard = []
    for d in deposits:
        keyboard.append([
            InlineKeyboardButton(f" #{d[0]} - {d[2]:,}đ", callback_data=f"admin_confirm_{d[0]}"),
            InlineKeyboardButton("", callback_data=f"admin_cancel_{d[0]}")
        ])
    keyboard.append([InlineKeyboardButton(" Quay lại", callback_data="admin")])
    return InlineKeyboardMarkup(keyboard)

def pending_withdrawals_keyboard(withdrawals):
    keyboard = []
    for w in withdrawals:
        keyboard.append([InlineKeyboardButton(f" #{w[0]} - {w[2]:,}đ", callback_data=f"admin_view_{w[0]}")])
    keyboard.append([InlineKeyboardButton(" Quay lại", callback_data="admin")])
    return InlineKeyboardMarkup(keyboard)


def pending_binance_deposits_keyboard(deposits):
    """Keyboard cho danh sách yêu cầu nạp Binance"""
    keyboard = []
    for d in deposits:
        # d: (id, user_id, usdt_amount, vnd_amount, code, screenshot_file_id, created_at)
        keyboard.append([InlineKeyboardButton(f"🔶 #{d[0]} - {d[2]} USDT ({d[3]:,}đ)", callback_data=f"admin_viewbn_{d[0]}")])
    keyboard.append([InlineKeyboardButton("🔙 Quay lại", callback_data="admin")])
    return InlineKeyboardMarkup(keyboard)


def pending_usdt_withdrawals_keyboard(withdrawals):
    """Keyboard cho danh sách yêu cầu rút USDT"""
    keyboard = []
    for w in withdrawals:
        # w: (id, user_id, usdt_amount, wallet_address, network, created_at)
        keyboard.append([InlineKeyboardButton(f"💸 #{w[0]} - {w[2]} USDT", callback_data=f"admin_viewusdt_{w[0]}")])
    keyboard.append([InlineKeyboardButton("🔙 Quay lại", callback_data="admin")])
    return InlineKeyboardMarkup(keyboard)
