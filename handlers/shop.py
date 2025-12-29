import random
import string
import io
from telegram import Update, InputFile, KeyboardButton, ReplyKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler
from database import (
    get_products, get_product, get_balance, update_balance,
    get_available_stock, mark_stock_sold, create_order,
    get_user_orders, create_deposit, get_or_create_user,
    get_bank_settings
)
from keyboards import (
    products_keyboard, confirm_buy_keyboard,
    back_keyboard, main_menu_keyboard, user_reply_keyboard
)
from config import MOMO_PHONE, MOMO_NAME, ADMIN_IDS

# Bank codes cho VietQR
BANK_CODES = {
    "VietinBank": "970415",
    "Vietcombank": "970436",
    "BIDV": "970418",
    "Agribank": "970405",
    "MBBank": "970422",
    "MB": "970422",
    "Techcombank": "970407",
    "ACB": "970416",
    "VPBank": "970432",
    "TPBank": "970423",
    "Sacombank": "970403",
    "HDBank": "970437",
    "VIB": "970441",
    "SHB": "970443",
    "Eximbank": "970431",
    "MSB": "970426",
    "OCB": "970448",
    "LienVietPostBank": "970449",
    "SeABank": "970440",
    "NamABank": "970428",
    "PVcomBank": "970412",
    "BacABank": "970409",
    "VietABank": "970427",
    "ABBank": "970425",
    "BaoVietBank": "970438",
    "NCB": "970419",
    "Kienlongbank": "970452",
    "VietBank": "970433",
    "MoMo": "MOMO",
    "Momo": "MOMO",
    "momo": "MOMO",
}

def generate_vietqr_url(bank_name: str, account_number: str, account_name: str, amount: int, content: str) -> str:
    """Tạo URL ảnh QR từ VietQR API"""
    bank_code = BANK_CODES.get(bank_name, "970415")  # Default VietinBank
    # VietQR API format
    qr_url = f"https://img.vietqr.io/image/{bank_code}-{account_number}-compact2.png?amount={amount}&addInfo={content}&accountName={account_name.replace(' ', '%20')}"
    return qr_url

def is_admin(user_id: int) -> bool:
    return user_id in ADMIN_IDS

# States
WAITING_DEPOSIT_AMOUNT = 1
WAITING_WITHDRAW_AMOUNT = 2
WAITING_WITHDRAW_BANK = 3
WAITING_WITHDRAW_ACCOUNT = 4

# Text handlers for reply keyboard
async def handle_shop_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    products = await get_products()
    text = "🛒 DANH MỤC SẢN PHẨM\n\n👉 Chọn sản phẩm bên dưới:"
    await update.message.reply_text(text, reply_markup=products_keyboard(products))

async def handle_deposit_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['waiting_deposit'] = True
    text = """
💰 NẠP TIỀN VÀO TÀI KHOẢN

Chọn mệnh giá hoặc nhập số tiền (VNĐ):

⚠️ Tối thiểu: 5,000đ
"""
    keyboard = [
        [KeyboardButton("20,000đ"), KeyboardButton("50,000đ")],
        [KeyboardButton("❌ Hủy")],
    ]
    await update.message.reply_text(text, reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True))
    return WAITING_DEPOSIT_AMOUNT

async def process_deposit_amount(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Xử lý khi user nhập số tiền nạp"""
    text_input = update.message.text.strip()
    
    # Xử lý nút Hủy
    if text_input == "❌ Hủy":
        await update.message.reply_text("❌ Đã hủy nạp tiền.", reply_markup=user_reply_keyboard())
        return ConversationHandler.END
    
    try:
        # Parse số tiền (hỗ trợ cả "20,000đ" và "20000")
        amount_text = text_input.replace(",", "").replace(".", "").replace(" ", "").replace("đ", "")
        amount = int(amount_text)
        
        if amount < 5000:
            await update.message.reply_text("❌ Số tiền tối thiểu là 5,000đ. Vui lòng nhập lại:")
            return WAITING_DEPOSIT_AMOUNT
        
        user_id = update.effective_user.id
        
        # Generate unique code - SEVQR prefix required for VietinBank + SePay
        code = f"SEVQR NAP{user_id}{random.randint(1000, 9999)}"
        
        # Save deposit request
        await create_deposit(user_id, amount, code)
        
        # Lấy settings từ database
        bank_settings = await get_bank_settings()
        bank_name = bank_settings['bank_name']
        account_number = bank_settings['account_number']
        account_name = bank_settings['account_name']
        
        # Hiện thông tin chuyển khoản
        if account_number:
            # Tạo QR VietQR
            qr_url = generate_vietqr_url(
                bank_name, 
                account_number, 
                account_name, 
                amount, 
                code
            )
            
            text = f"""
💳 THÔNG TIN CHUYỂN KHOẢN

🏦 Ngân hàng: <code>{bank_name}</code>
🔢 Số TK: <code>{account_number}</code>
👤 Tên: <code>{account_name}</code>
💰 Số tiền: <code>{amount:,}đ</code>
📝 Nội dung: <code>{code}</code>

⚠️ Quét mã QR hoặc chuyển khoản thủ công
✅ Tiền sẽ được cộng TỰ ĐỘNG sau 1-2 phút
"""
            # Gửi ảnh QR kèm caption
            await update.message.reply_photo(
                photo=qr_url,
                caption=text,
                parse_mode="HTML",
                reply_markup=user_reply_keyboard()
            )
        else:
            text = f"""
💳 THÔNG TIN CHUYỂN KHOẢN MOMO

📱 Số điện thoại: <code>{MOMO_PHONE}</code>
👤 Tên: <code>{MOMO_NAME}</code>
💰 Số tiền: <code>{amount:,}đ</code>
📝 Nội dung: <code>{code}</code>

⚠️ Chuyển đúng số tiền và nội dung
✅ Tiền sẽ được cộng TỰ ĐỘNG sau 1-2 phút
"""
            await update.message.reply_text(text, parse_mode="HTML", reply_markup=user_reply_keyboard())
        
        context.user_data['waiting_deposit'] = False
        return ConversationHandler.END
        
    except ValueError:
        await update.message.reply_text("❌ Số tiền không hợp lệ. Vui lòng nhập số:")
        return WAITING_DEPOSIT_AMOUNT

async def handle_withdraw_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    balance = await get_balance(user_id)
    
    # Check xem có yêu cầu rút tiền đang pending không
    from database import get_user_pending_withdrawal
    pending = await get_user_pending_withdrawal(user_id)
    
    if pending:
        await update.message.reply_text(
            f"📋 Bạn đang có yêu cầu rút {pending:,}đ chưa được duyệt.\n\n"
            "Vui lòng đợi admin xử lý xong nhé!"
        )
        return ConversationHandler.END
    
    if balance < 10000:
        await update.message.reply_text(
            f"❌ Số dư không đủ để rút!\n\n💰 Số dư: {balance:,}đ\n⚠️ Tối thiểu: 10,000đ"
        )
        return ConversationHandler.END
    
    context.user_data['withdraw_balance'] = balance
    text = f"""
💸 RÚT TIỀN

💰 Số dư hiện tại: {balance:,}đ
⚠️ Tối thiểu: 10,000đ

Nhập số tiền muốn rút:
"""
    keyboard = [
        [KeyboardButton("❌ Hủy")],
    ]
    await update.message.reply_text(text, reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True))
    return WAITING_WITHDRAW_AMOUNT

async def process_withdraw_amount(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Xử lý khi user nhập số tiền rút"""
    text_input = update.message.text.strip()
    
    if text_input == "❌ Hủy":
        await update.message.reply_text("❌ Đã hủy rút tiền.", reply_markup=user_reply_keyboard())
        return ConversationHandler.END
    
    try:
        amount_text = text_input.replace(",", "").replace(".", "").replace(" ", "").replace("đ", "")
        amount = int(amount_text)
        
        balance = context.user_data.get('withdraw_balance', 0)
        
        if amount < 10000:
            await update.message.reply_text("❌ Số tiền tối thiểu là 10,000đ. Vui lòng nhập lại:")
            return WAITING_WITHDRAW_AMOUNT
        
        if amount > balance:
            await update.message.reply_text(f"❌ Số dư không đủ! Bạn chỉ có {balance:,}đ. Vui lòng nhập lại:")
            return WAITING_WITHDRAW_AMOUNT
        
        context.user_data['withdraw_amount'] = amount
        
        # Hiện các nút chọn ngân hàng
        keyboard = [
            [KeyboardButton("MoMo"), KeyboardButton("MBBank")],
            [KeyboardButton("Vietcombank"), KeyboardButton("VietinBank")],
            [KeyboardButton("BIDV"), KeyboardButton("Techcombank")],
            [KeyboardButton("ACB"), KeyboardButton("TPBank")],
            [KeyboardButton("❌ Hủy")],
        ]
        await update.message.reply_text(
            f"💰 Số tiền rút: {amount:,}đ\n\n🏦 Chọn ngân hàng nhận tiền:",
            reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
        )
        return WAITING_WITHDRAW_BANK
        
    except ValueError:
        await update.message.reply_text("❌ Số tiền không hợp lệ. Vui lòng nhập số:")
        return WAITING_WITHDRAW_AMOUNT

async def process_withdraw_bank(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Xử lý khi user chọn ngân hàng"""
    text_input = update.message.text.strip()
    
    if text_input == "❌ Hủy":
        await update.message.reply_text("❌ Đã hủy rút tiền.", reply_markup=user_reply_keyboard())
        return ConversationHandler.END
    
    # Validate ngân hàng
    valid_banks = ["MoMo", "MBBank", "Vietcombank", "VietinBank", "BIDV", "Techcombank", "ACB", "TPBank"]
    if text_input not in valid_banks:
        await update.message.reply_text("❌ Vui lòng chọn ngân hàng từ danh sách!")
        return WAITING_WITHDRAW_BANK
    
    context.user_data['withdraw_bank'] = text_input
    
    keyboard = [[KeyboardButton("❌ Hủy")]]
    
    if text_input == "MoMo":
        await update.message.reply_text(
            "📱 Nhập số điện thoại MoMo:",
            reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
        )
    else:
        await update.message.reply_text(
            "🔢 Nhập số tài khoản ngân hàng:",
            reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
        )
    return WAITING_WITHDRAW_ACCOUNT

async def process_withdraw_account(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Xử lý khi user nhập số tài khoản"""
    text_input = update.message.text.strip()
    
    if text_input == "❌ Hủy":
        await update.message.reply_text("❌ Đã hủy rút tiền.", reply_markup=user_reply_keyboard())
        return ConversationHandler.END
    
    account_number = text_input
    amount = context.user_data.get('withdraw_amount', 0)
    bank_name = context.user_data.get('withdraw_bank', '')
    user_id = update.effective_user.id
    
    # Tạo yêu cầu rút tiền (lưu bank + account vào trường momo_phone)
    from database import create_withdrawal
    bank_info = f"{bank_name} - {account_number}"
    await create_withdrawal(user_id, amount, bank_info)
    
    balance = await get_balance(user_id)
    
    text = f"""
✅ YÊU CẦU RÚT TIỀN ĐÃ GỬI!

💰 Số tiền yêu cầu: {amount:,}đ
🏦 Ngân hàng: {bank_name}
🔢 Số TK: {account_number}
💳 Số dư hiện tại: {balance:,}đ

⏳ Admin sẽ xử lý trong vòng 24h.
⚠️ Tiền sẽ được trừ khi admin duyệt.
"""
    await update.message.reply_text(text, reply_markup=user_reply_keyboard())
    return ConversationHandler.END

async def show_shop(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    products = await get_products()
    text = "👉 CHỌN SẢN PHẨM BÊN DƯỚI:"
    await query.edit_message_text(text, reply_markup=products_keyboard(products))

async def show_product(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    product_id = int(query.data.split("_")[1])
    product = await get_product(product_id)
    
    if not product:
        await query.edit_message_text("❌ Sản phẩm không tồn tại!", reply_markup=back_keyboard("shop"))
        return
    
    if product['stock'] <= 0:
        await query.edit_message_text(
            f"❌ {product['name']} đã hết hàng!\n\nVui lòng chọn sản phẩm khác.",
            reply_markup=back_keyboard("shop")
        )
        return
    
    user_balance = await get_balance(query.from_user.id)
    max_can_buy = min(product['stock'], user_balance // product['price']) if product['price'] > 0 else product['stock']
    
    text = f"""
📦 {product['name']}

💰 Giá: {product['price']:,}đ
📊 Còn lại: {product['stock']} sản phẩm
📝 Mô tả: {product['description'] or 'Không có mô tả'}

💳 Số dư của bạn: {user_balance:,}đ
🛒 Có thể mua tối đa: {max_can_buy} sản phẩm
"""
    await query.edit_message_text(text, reply_markup=confirm_buy_keyboard(product_id, product['stock'], max_can_buy))

async def confirm_buy(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    # Parse callback: confirm_buy_{product_id}_{quantity}
    parts = query.data.split("_")
    product_id = int(parts[2])
    quantity = int(parts[3]) if len(parts) > 3 else 1
    
    product = await get_product(product_id)
    user_id = query.from_user.id
    
    if not product:
        await query.edit_message_text("❌ Sản phẩm không tồn tại!", reply_markup=back_keyboard("shop"))
        return
    
    if product['stock'] < quantity:
        await query.edit_message_text(f"❌ Không đủ hàng! Chỉ còn {product['stock']} sản phẩm.", reply_markup=back_keyboard("shop"))
        return
    
    total_price = product['price'] * quantity
    balance = await get_balance(user_id)
    
    if balance < total_price:
        await query.edit_message_text(
            f"❌ Số dư không đủ!\n\n💰 Số dư: {balance:,}đ\n💵 Cần: {total_price:,}đ ({quantity}x {product['price']:,}đ)\n\nVui lòng nạp thêm tiền.",
            reply_markup=back_keyboard("deposit")
        )
        return
    
    # Mua nhiều sản phẩm
    purchased_items = []
    for _ in range(quantity):
        stock = await get_available_stock(product_id)
        if not stock:
            break
        await mark_stock_sold(stock[0])
        await create_order(user_id, product_id, stock[1], product['price'])
        purchased_items.append(stock[1])
    
    if not purchased_items:
        await query.edit_message_text("❌ Sản phẩm đã hết hàng!", reply_markup=back_keyboard("shop"))
        return
    
    # Trừ tiền theo số lượng thực tế mua được
    actual_total = product['price'] * len(purchased_items)
    await update_balance(user_id, -actual_total)
    new_balance = await get_balance(user_id)
    
    # Format danh sách sản phẩm
    items_text = "\n".join([f"<code>{item}</code>" for item in purchased_items])
    
    text = f"""
✅ MUA HÀNG THÀNH CÔNG!

📦 Sản phẩm: {product['name']}
🔢 Số lượng: {len(purchased_items)}
💰 Tổng tiền: {actual_total:,}đ
💳 Số dư còn lại: {new_balance:,}đ

📋 Thông tin sản phẩm:
{items_text}

⚠️ Lưu ý: Hãy lưu lại thông tin trên!
"""
    await query.edit_message_text(text, parse_mode="HTML", reply_markup=back_keyboard())

async def show_account(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    user = await get_or_create_user(query.from_user.id, query.from_user.username)
    
    text = f"""
👤 THÔNG TIN TÀI KHOẢN

🆔 ID: {user['user_id']}
👤 Username: @{user['username'] or 'Chưa có'}
💰 Số dư: {user['balance']:,}đ
"""
    await query.edit_message_text(text, reply_markup=back_keyboard())

async def show_history(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    orders = await get_user_orders(query.from_user.id)
    
    if not orders:
        await query.edit_message_text("📜 Bạn chưa có đơn hàng nào!", reply_markup=back_keyboard())
        return
    
    text = "📜 LỊCH SỬ MUA HÀNG:\n\n"
    for order in orders:
        text += f"#{order[0]} | {order[1]} | {order[3]:,}đ\n"
        text += f"📋 <code>{order[2]}</code>\n\n"
    
    await query.edit_message_text(text, parse_mode="HTML", reply_markup=back_keyboard())


# Deposit handlers
async def show_deposit(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    text = """
💰 NẠP TIỀN VÀO TÀI KHOẢN

Chọn số tiền muốn nạp:
"""
    await query.edit_message_text(text, reply_markup=deposit_amounts_keyboard())

async def process_deposit(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    amount = int(query.data.split("_")[1])
    user_id = query.from_user.id
    
    # Generate unique code - SEVQR prefix required for VietinBank + SePay
    code = f"SEVQR NAP{user_id}{''.join(random.choices(string.digits, k=4))}"
    
    # Save deposit request
    await create_deposit(user_id, amount, code)
    
    # Ưu tiên SePay nếu có config, không thì dùng MoMo
    if SEPAY_ACCOUNT_NUMBER:
        text = f"""
💳 THÔNG TIN CHUYỂN KHOẢN

🏦 Ngân hàng: <code>{SEPAY_BANK_NAME}</code>
🔢 Số TK: <code>{SEPAY_ACCOUNT_NUMBER}</code>
👤 Tên: <code>{SEPAY_ACCOUNT_NAME}</code>
💰 Số tiền: <code>{amount:,}đ</code>
📝 Nội dung: <code>{code}</code>

⚠️ LƯU Ý QUAN TRỌNG:
• Chuyển ĐÚNG số tiền và nội dung
• Tiền sẽ được cộng TỰ ĐỘNG sau 1-2 phút
• Sai nội dung = không nhận được tiền!

✅ Mã nạp tiền: {code}
"""
    else:
        text = f"""
💳 THÔNG TIN CHUYỂN KHOẢN MOMO

📱 Số điện thoại: <code>{MOMO_PHONE}</code>
👤 Tên: <code>{MOMO_NAME}</code>
💰 Số tiền: <code>{amount:,}đ</code>
📝 Nội dung: <code>{code}</code>

⚠️ LƯU Ý QUAN TRỌNG:
• Chuyển đúng số tiền và nội dung
• Tiền sẽ được cộng TỰ ĐỘNG sau 1-2 phút

✅ Mã nạp tiền: {code}
"""
    await query.edit_message_text(text, parse_mode="HTML", reply_markup=back_keyboard())
