import random
import string
import io
from telegram import Update, InputFile, KeyboardButton, ReplyKeyboardMarkup, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler
from database import (
    get_products, get_product, get_balance, update_balance,
    get_available_stock, mark_stock_sold, create_order, create_order_bulk,
    get_user_orders, create_deposit, get_or_create_user,
    get_bank_settings, get_available_stock_batch, mark_stock_sold_batch,
    get_user_language, get_balance_usdt, update_balance_usdt
)
from keyboards import (
    products_keyboard, confirm_buy_keyboard,
    back_keyboard, main_menu_keyboard, user_reply_keyboard
)
from config import MOMO_PHONE, MOMO_NAME, ADMIN_IDS, SEPAY_ACCOUNT_NUMBER, SEPAY_BANK_NAME, SEPAY_ACCOUNT_NAME, BINANCE_PAY_ID, USDT_RATE
from locales import get_text

def make_file(items: list, header: str = "") -> io.BytesIO:
    """Tạo file nhanh từ list items"""
    if header:
        content = header + "\n" + "="*40 + "\n\n" + "\n".join(items)
    else:
        content = "\n".join(items)
    buf = io.BytesIO(content.encode('utf-8'))
    buf.seek(0)
    return buf

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
WAITING_BINANCE_AMOUNT = 5
WAITING_BINANCE_SCREENSHOT = 6
WAITING_USDT_WITHDRAW_AMOUNT = 7
WAITING_USDT_WITHDRAW_WALLET = 8

# Text handlers for reply keyboard
async def handle_shop_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    lang = await get_user_language(user_id)
    products = await get_products()
    text = get_text(lang, "select_product")
    await update.message.reply_text(text, reply_markup=products_keyboard(products, lang))

async def handle_buy_quantity(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Xử lý khi user nhập số lượng muốn mua"""
    product_id = context.user_data.get('buying_product_id')
    max_can_buy = context.user_data.get('buying_max', 0)
    currency = context.user_data.get('buying_currency', 'vnd')
    
    if not product_id:
        return  # Không trong trạng thái mua hàng
    
    user_id = update.effective_user.id
    lang = await get_user_language(user_id)
    
    try:
        quantity = int(update.message.text.strip())
    except ValueError:
        await update.message.reply_text(get_text(lang, "invalid_quantity"))
        return
    
    if quantity < 1:
        await update.message.reply_text(get_text(lang, "invalid_quantity"))
        return
    
    if quantity > max_can_buy:
        await update.message.reply_text(get_text(lang, "max_quantity").format(max=max_can_buy))
        return
    
    # Xử lý mua hàng
    product = await get_product(product_id)
    
    if not product:
        await update.message.reply_text(get_text(lang, "product_not_found"))
        context.user_data.pop('buying_product_id', None)
        return
    
    if product['stock'] < quantity:
        await update.message.reply_text(get_text(lang, "out_of_stock").format(name=product['name']))
        return
    
    # Tính giá theo loại tiền
    if currency == 'usdt':
        unit_price = product['price_usdt']
        total_price = unit_price * quantity
        balance = await get_balance_usdt(user_id)
        currency_symbol = "USDT"
    else:
        unit_price = product['price']
        total_price = unit_price * quantity
        balance = await get_balance(user_id)
        currency_symbol = "đ"
    
    if balance < total_price:
        if currency == 'usdt':
            await update.message.reply_text(
                get_text(lang, "not_enough_balance").format(balance=f"{balance:.2f} USDT", need=f"{total_price} USDT")
            )
        else:
            await update.message.reply_text(
                get_text(lang, "not_enough_balance").format(balance=f"{balance:,}đ", need=f"{total_price:,}đ")
            )
        return
    
    # Lấy stock batch
    stocks = await get_available_stock_batch(product_id, quantity)
    
    if not stocks:
        await update.message.reply_text(get_text(lang, "out_of_stock").format(name=product['name']))
        context.user_data.pop('buying_product_id', None)
        return
    
    # Mark sold batch
    stock_ids = [s[0] for s in stocks]
    purchased_items = [s[1] for s in stocks]
    await mark_stock_sold_batch(stock_ids)
    
    # Tạo đơn hàng
    from datetime import datetime
    order_group = f"ORD{user_id}{datetime.now().strftime('%Y%m%d%H%M%S')}"
    
    # Lưu giá theo VNĐ để thống kê
    if currency == 'usdt':
        price_for_order = int(unit_price * USDT_RATE)
    else:
        price_for_order = unit_price
    
    await create_order_bulk(user_id, product_id, purchased_items, price_for_order, order_group)
    
    # Trừ tiền
    actual_total = unit_price * len(purchased_items)
    if currency == 'usdt':
        await update_balance_usdt(user_id, -actual_total)
        new_balance = await get_balance_usdt(user_id)
        balance_text = f"{new_balance:.2f} USDT"
        total_text = f"{actual_total} USDT"
    else:
        await update_balance(user_id, -int(actual_total))
        new_balance = await get_balance(user_id)
        balance_text = f"{new_balance:,}đ"
        total_text = f"{int(actual_total):,}đ"
    
    # Tạo file
    header = f"Product: {product['name']}\nQty: {len(purchased_items)}\nTotal: {total_text}"
    file_buf = make_file(purchased_items, header)
    filename = f"{product['name']}_{len(purchased_items)}.txt"
    
    success_text = get_text(lang, "buy_success").format(
        name=product['name'], qty=len(purchased_items), total=total_text, balance=balance_text
    )
    
    if len(purchased_items) > 10:
        await update.message.reply_document(
            document=file_buf,
            filename=filename,
            caption=success_text,
            reply_markup=user_reply_keyboard(lang)
        )
    else:
        items_formatted = "\n".join([f"<code>{item}</code>" for item in purchased_items])
        text = f"{success_text}\n\n{items_formatted}"
        await update.message.reply_text(text, parse_mode="HTML", reply_markup=user_reply_keyboard(lang))
    
    # Clear trạng thái mua
    context.user_data.pop('buying_product_id', None)
    context.user_data.pop('buying_max', None)
    context.user_data.pop('buying_currency', None)

async def handle_deposit_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    lang = await get_user_language(user_id)
    context.user_data['waiting_deposit'] = True
    context.user_data['user_lang'] = lang
    
    text = get_text(lang, "deposit_title")
    cancel_text = get_text(lang, "btn_cancel")
    keyboard = [
        [KeyboardButton("20,000đ"), KeyboardButton("50,000đ")],
        [KeyboardButton(cancel_text)],
    ]
    await update.message.reply_text(text, reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True))
    return WAITING_DEPOSIT_AMOUNT

async def process_deposit_amount(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Xử lý khi user nhập số tiền nạp"""
    text_input = update.message.text.strip()
    user_id = update.effective_user.id
    lang = await get_user_language(user_id)
    
    # Xử lý nút Hủy
    if text_input in ["❌ Hủy", "❌ Cancel"]:
        await update.message.reply_text(get_text(lang, "deposit_cancelled"), reply_markup=user_reply_keyboard(lang))
        return ConversationHandler.END
    
    try:
        amount_text = text_input.replace(",", "").replace(".", "").replace(" ", "").replace("đ", "")
        amount = int(amount_text)
        
        if amount < 5000:
            await update.message.reply_text(get_text(lang, "deposit_min"))
            return WAITING_DEPOSIT_AMOUNT
        
        # Generate unique code
        code = f"SEVQR NAP{user_id}{random.randint(1000, 9999)}"
        
        # Save deposit request
        await create_deposit(user_id, amount, code)
        
        # Lấy settings từ database
        bank_settings = await get_bank_settings()
        bank_name = bank_settings['bank_name']
        account_number = bank_settings['account_number']
        account_name = bank_settings['account_name']
        
        if account_number:
            qr_url = generate_vietqr_url(bank_name, account_number, account_name, amount, code)
            
            text = get_text(lang, "deposit_info").format(
                bank=bank_name, account=account_number, name=account_name,
                amount=f"{amount:,}", code=code
            )
            await update.message.reply_photo(
                photo=qr_url,
                caption=text,
                parse_mode="HTML",
                reply_markup=user_reply_keyboard(lang)
            )
        else:
            text = f"📱 MoMo: {MOMO_PHONE}\n👤 {MOMO_NAME}\n💰 {amount:,}đ\n📝 {code}"
            await update.message.reply_text(text, reply_markup=user_reply_keyboard(lang))
        
        context.user_data['waiting_deposit'] = False
        return ConversationHandler.END
        
    except ValueError:
        await update.message.reply_text(get_text(lang, "invalid_amount"))
        return WAITING_DEPOSIT_AMOUNT

async def handle_withdraw_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    lang = await get_user_language(user_id)
    balance = await get_balance(user_id)
    
    from database import get_user_pending_withdrawal
    pending = await get_user_pending_withdrawal(user_id)
    
    if pending:
        await update.message.reply_text(get_text(lang, "withdraw_pending").format(amount=f"{pending:,}"))
        return ConversationHandler.END
    
    if balance < 10000:
        await update.message.reply_text(get_text(lang, "withdraw_low_balance").format(balance=f"{balance:,}"))
        return ConversationHandler.END
    
    context.user_data['withdraw_balance'] = balance
    text = get_text(lang, "withdraw_title").format(balance=f"{balance:,}")
    cancel_text = get_text(lang, "btn_cancel")
    keyboard = [[KeyboardButton(cancel_text)]]
    await update.message.reply_text(text, reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True))
    return WAITING_WITHDRAW_AMOUNT

async def process_withdraw_amount(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Xử lý khi user nhập số tiền rút"""
    text_input = update.message.text.strip()
    user_id = update.effective_user.id
    lang = await get_user_language(user_id)
    
    if text_input in ["❌ Hủy", "❌ Cancel"]:
        await update.message.reply_text(get_text(lang, "withdraw_cancelled"), reply_markup=user_reply_keyboard(lang))
        return ConversationHandler.END
    
    try:
        amount_text = text_input.replace(",", "").replace(".", "").replace(" ", "").replace("đ", "")
        amount = int(amount_text)
        
        balance = context.user_data.get('withdraw_balance', 0)
        
        if amount < 10000:
            await update.message.reply_text(get_text(lang, "withdraw_min"))
            return WAITING_WITHDRAW_AMOUNT
        
        if amount > balance:
            await update.message.reply_text(get_text(lang, "withdraw_not_enough").format(balance=f"{balance:,}"))
            return WAITING_WITHDRAW_AMOUNT
        
        context.user_data['withdraw_amount'] = amount
        
        text = get_text(lang, "withdraw_select_bank").format(amount=f"{amount:,}")
        keyboard = [
            [KeyboardButton("MoMo"), KeyboardButton("MBBank")],
            [KeyboardButton("Vietcombank"), KeyboardButton("VietinBank")],
            [KeyboardButton("BIDV"), KeyboardButton("Techcombank")],
            [KeyboardButton("ACB"), KeyboardButton("TPBank")],
            [KeyboardButton(get_text(lang, "btn_cancel"))],
        ]
        await update.message.reply_text(text, reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True))
        return WAITING_WITHDRAW_BANK
        
    except ValueError:
        await update.message.reply_text(get_text(lang, "invalid_amount"))
        return WAITING_WITHDRAW_AMOUNT

async def process_withdraw_bank(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Xử lý khi user chọn ngân hàng"""
    text_input = update.message.text.strip()
    user_id = update.effective_user.id
    lang = await get_user_language(user_id)
    
    if text_input in ["❌ Hủy", "❌ Cancel"]:
        await update.message.reply_text(get_text(lang, "withdraw_cancelled"), reply_markup=user_reply_keyboard(lang))
        return ConversationHandler.END
    
    valid_banks = ["MoMo", "MBBank", "Vietcombank", "VietinBank", "BIDV", "Techcombank", "ACB", "TPBank"]
    if text_input not in valid_banks:
        select_text = "Please select a bank from the list!" if lang == 'en' else "Vui lòng chọn ngân hàng từ danh sách!"
        await update.message.reply_text(select_text)
        return WAITING_WITHDRAW_BANK
    
    context.user_data['withdraw_bank'] = text_input
    
    cancel_text = get_text(lang, "btn_cancel")
    keyboard = [[KeyboardButton(cancel_text)]]
    
    if text_input == "MoMo":
        await update.message.reply_text(get_text(lang, "withdraw_enter_momo"), reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True))
    else:
        await update.message.reply_text(get_text(lang, "withdraw_enter_account"), reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True))
    return WAITING_WITHDRAW_ACCOUNT

async def process_withdraw_account(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Xử lý khi user nhập số tài khoản"""
    text_input = update.message.text.strip()
    user_id = update.effective_user.id
    lang = await get_user_language(user_id)
    
    if text_input in ["❌ Hủy", "❌ Cancel"]:
        await update.message.reply_text(get_text(lang, "withdraw_cancelled"), reply_markup=user_reply_keyboard(lang))
        return ConversationHandler.END
    
    account_number = text_input
    amount = context.user_data.get('withdraw_amount', 0)
    bank_name = context.user_data.get('withdraw_bank', '')
    
    from database import create_withdrawal
    bank_info = f"{bank_name} - {account_number}"
    await create_withdrawal(user_id, amount, bank_info)
    
    balance = await get_balance(user_id)
    
    text = get_text(lang, "withdraw_submitted").format(
        amount=f"{amount:,}", bank=bank_name, account=account_number, balance=f"{balance:,}"
    )
    await update.message.reply_text(text, reply_markup=user_reply_keyboard(lang))
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
    user_id = query.from_user.id
    lang = await get_user_language(user_id)
    
    if not product:
        await query.edit_message_text(get_text(lang, "product_not_found"), reply_markup=back_keyboard("shop"))
        return
    
    if product['stock'] <= 0:
        await query.edit_message_text(
            get_text(lang, "out_of_stock").format(name=product['name']),
            reply_markup=back_keyboard("shop")
        )
        return
    
    user_balance = await get_balance(user_id)
    user_balance_usdt = await get_balance_usdt(user_id)
    
    if lang == 'en':
        # English: USDT only
        if product['price_usdt'] <= 0:
            await query.edit_message_text(
                f"❌ {product['name']} is not available for USDT payment.",
                reply_markup=back_keyboard("shop")
            )
            return
        max_buy = min(product['stock'], int(user_balance_usdt // product['price_usdt']))
        context.user_data['buying_product_id'] = product_id
        context.user_data['buying_max'] = max_buy
        context.user_data['buying_currency'] = 'usdt'
        
        text = f"📦 {product['name']}\n💵 Price: {product['price_usdt']} USDT\n📊 In stock: {product['stock']}\n\n💳 Your balance: {user_balance_usdt:.2f} USDT\n🛒 Max can buy: {max_buy}"
        if max_buy > 0:
            text += f"\n\n📝 Enter quantity (1-{max_buy}):"
        else:
            text += "\n\n❌ Insufficient balance!"
        await query.edit_message_text(text, reply_markup=back_keyboard("shop"))
    else:
        # Vietnamese: VND or USDT choice
        max_vnd = min(product['stock'], user_balance // product['price']) if product['price'] > 0 else 0
        max_usdt = min(product['stock'], int(user_balance_usdt // product['price_usdt'])) if product['price_usdt'] > 0 else 0
        
        context.user_data['buying_product_id'] = product_id
        
        text = f"📦 {product['name']}\n💰 Giá: {product['price']:,}đ"
        if product['price_usdt'] > 0:
            text += f" | {product['price_usdt']} USDT"
        text += f"\n📊 Còn: {product['stock']}\n\n💳 Số dư VNĐ: {user_balance:,}đ (mua tối đa {max_vnd})"
        text += f"\n💵 Số dư USDT: {user_balance_usdt:.2f} (mua tối đa {max_usdt})"
        text += "\n\nChọn phương thức thanh toán:"
        
        keyboard = []
        if product['price'] > 0 and max_vnd > 0:
            keyboard.append([InlineKeyboardButton(f"💰 VNĐ ({product['price']:,}đ)", callback_data=f"pay_vnd_{product_id}")])
        if product['price_usdt'] > 0 and max_usdt > 0:
            keyboard.append([InlineKeyboardButton(f"💵 USDT ({product['price_usdt']} USDT)", callback_data=f"pay_usdt_{product_id}")])
        keyboard.append([InlineKeyboardButton("🔙 Quay lại", callback_data="shop")])
        
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))

async def select_payment_vnd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """User chọn thanh toán bằng VNĐ"""
    query = update.callback_query
    await query.answer()
    
    product_id = int(query.data.split("_")[2])
    product = await get_product(product_id)
    user_id = query.from_user.id
    lang = await get_user_language(user_id)
    user_balance = await get_balance(user_id)
    
    max_can_buy = min(product['stock'], user_balance // product['price']) if product['price'] > 0 else 0
    
    context.user_data['buying_product_id'] = product_id
    context.user_data['buying_max'] = max_can_buy
    context.user_data['buying_currency'] = 'vnd'
    
    text = f"📦 {product['name']}\n💰 {product['price']:,}đ\n💳 {user_balance:,}đ\n🛒 Max: {max_can_buy}"
    text += get_text(lang, "enter_quantity").format(max=max_can_buy)
    await query.edit_message_text(text, reply_markup=back_keyboard("shop"))

async def select_payment_usdt(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """User chọn thanh toán bằng USDT"""
    query = update.callback_query
    await query.answer()
    
    product_id = int(query.data.split("_")[2])
    product = await get_product(product_id)
    user_id = query.from_user.id
    lang = await get_user_language(user_id)
    user_balance_usdt = await get_balance_usdt(user_id)
    
    max_can_buy = min(product['stock'], int(user_balance_usdt // product['price_usdt'])) if product['price_usdt'] > 0 else 0
    
    context.user_data['buying_product_id'] = product_id
    context.user_data['buying_max'] = max_can_buy
    context.user_data['buying_currency'] = 'usdt'
    
    text = f"📦 {product['name']}\n💵 {product['price_usdt']} USDT\n💳 {user_balance_usdt:.2f} USDT\n🛒 Max: {max_can_buy}"
    text += get_text(lang, "enter_quantity").format(max=max_can_buy)
    await query.edit_message_text(text, reply_markup=back_keyboard("shop"))

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
    
    # Lấy stock batch (1 query thay vì N queries)
    stocks = await get_available_stock_batch(product_id, quantity)
    
    if not stocks:
        await query.edit_message_text("❌ Sản phẩm đã hết hàng!", reply_markup=back_keyboard("shop"))
        return
    
    # Mark sold batch (1 query thay vì N queries)
    stock_ids = [s[0] for s in stocks]
    purchased_items = [s[1] for s in stocks]
    await mark_stock_sold_batch(stock_ids)
    
    # Tạo 1 đơn hàng duy nhất cho tất cả items
    from datetime import datetime
    order_group = f"ORD{user_id}{datetime.now().strftime('%Y%m%d%H%M%S')}"
    await create_order_bulk(user_id, product_id, purchased_items, product['price'], order_group)
    
    # Trừ tiền theo số lượng thực tế mua được
    actual_total = product['price'] * len(purchased_items)
    await update_balance(user_id, -actual_total)
    new_balance = await get_balance(user_id)
    
    # Tạo file trước
    header = f"Sản phẩm: {product['name']}\nSố lượng: {len(purchased_items)}\nTổng tiền: {actual_total:,}đ"
    file_buf = make_file(purchased_items, header)
    filename = f"{product['name']}_{len(purchased_items)}.txt"
    
    # Gửi file nếu nhiều items
    if len(purchased_items) > 10:
        await context.bot.send_document(
            chat_id=query.message.chat_id,
            document=file_buf,
            filename=filename,
            caption=f"✅ Mua thành công {len(purchased_items)} {product['name']}\n💰 {actual_total:,}đ | 💳 Còn {new_balance:,}đ"
        )
    else:
        # Gửi text bình thường
        items_formatted = "\n".join([f"<code>{item}</code>" for item in purchased_items])
        text = f"""✅ MUA HÀNG THÀNH CÔNG!

📦 {product['name']} x{len(purchased_items)}
💰 {actual_total:,}đ | 💳 Còn {new_balance:,}đ

{items_formatted}"""
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
    
    text = "📜 LỊCH SỬ MUA HÀNG\n\nChọn đơn để xem chi tiết:"
    keyboard = []
    
    # Giới hạn 5 đơn gần nhất
    for order in orders[:5]:
        order_id, product_name, content, price, created_at, quantity = order
        quantity = quantity or 1
        short_name = product_name[:8] if len(product_name) > 8 else product_name
        
        # Rút gọn giá
        if price >= 1000000:
            price_str = f"{price//1000000}tr"
        elif price >= 1000:
            price_str = f"{price//1000}k"
        else:
            price_str = str(price)
        
        # Button ngắn gọn
        keyboard.append([InlineKeyboardButton(f"#{order_id} {short_name} x{quantity} {price_str}", callback_data=f"order_detail_{order_id}")])
    
    keyboard.append([InlineKeyboardButton("🔙 Quay lại", callback_data="back_main")])
    
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))

async def show_order_detail(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Xem chi tiết đơn hàng - gửi file nếu nhiều items"""
    query = update.callback_query
    
    order_id = int(query.data.split("_")[2])
    
    from database import get_order_detail
    order = await get_order_detail(order_id)
    
    if not order:
        await query.answer("❌ Không tìm thấy đơn hàng!", show_alert=True)
        return
    
    # order: (id, product_name, content, price, created_at, quantity)
    _, product_name, content, price, created_at, quantity = order
    quantity = quantity or 1
    
    # Parse content (có thể là JSON array hoặc string đơn)
    import json
    try:
        items = json.loads(content)
        if not isinstance(items, list):
            items = [content]
    except:
        items = [content]
    
    # Nếu ít items -> hiển thị text
    if len(items) <= 10:
        await query.answer()
        items_text = "\n".join([f"<code>{item}</code>" for item in items])
        text = f"""
📋 CHI TIẾT ĐƠN HÀNG #{order_id}

📦 Sản phẩm: {product_name}
🔢 Số lượng: {quantity}
💰 Tổng tiền: {price:,}đ
📅 Ngày mua: {created_at[:19] if created_at else ""}

📝 Nội dung:
{items_text}
"""
        await query.edit_message_text(text, parse_mode="HTML", reply_markup=back_keyboard("history"))
    else:
        # Nhiều items -> gửi file ngay
        await query.answer()
        
        header = f"Đơn hàng: #{order_id}\nSản phẩm: {product_name}\nSố lượng: {quantity}\nTổng tiền: {price:,}đ"
        file_buf = make_file(items, header)
        filename = f"Don_{order_id}.txt"
        
        await context.bot.send_document(
            chat_id=query.message.chat_id,
            document=file_buf,
            filename=filename,
            caption=f"📋 Đơn #{order_id} | {product_name} | SL: {quantity}"
        )


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


# ============ BINANCE PAY DEPOSIT ============

async def handle_binance_deposit_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler khi user bấm nút Nạp Binance"""
    user_id = update.effective_user.id
    lang = await get_user_language(user_id)
    
    # Lấy Binance ID từ database
    from database import get_setting
    binance_id = await get_setting("binance_pay_id", "")
    
    if not binance_id and not BINANCE_PAY_ID:
        error_text = "❌ Binance not configured!" if lang == 'en' else "❌ Chức năng nạp Binance chưa được cấu hình!"
        await update.message.reply_text(error_text)
        return ConversationHandler.END
    
    # Ưu tiên database, fallback về config
    context.user_data['binance_id'] = binance_id or BINANCE_PAY_ID
    
    text = get_text(lang, "binance_title")
    cancel_text = get_text(lang, "btn_cancel")
    keyboard = [[KeyboardButton(cancel_text)]]
    await update.message.reply_text(text, reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True))
    return WAITING_BINANCE_AMOUNT

async def process_binance_amount(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Xử lý khi user nhập số USDT"""
    text_input = update.message.text.strip()
    user_id = update.effective_user.id
    lang = await get_user_language(user_id)
    
    if text_input in ["❌ Hủy", "❌ Cancel"]:
        await update.message.reply_text(get_text(lang, "deposit_cancelled"), reply_markup=user_reply_keyboard(lang))
        return ConversationHandler.END
    
    try:
        usdt_amount = float(text_input.replace(",", "."))
        
        if usdt_amount < 1:
            await update.message.reply_text(get_text(lang, "binance_min"))
            return WAITING_BINANCE_AMOUNT
        
        if usdt_amount > 10000:
            max_text = "❌ Maximum is 10,000 USDT." if lang == 'en' else "❌ Số tiền tối đa là 10,000 USDT."
            await update.message.reply_text(max_text)
            return WAITING_BINANCE_AMOUNT
        
        vnd_amount = int(usdt_amount * USDT_RATE)
        code = f"BN{user_id}{random.randint(1000, 9999)}"
        
        # Lấy Binance ID từ context
        binance_id = context.user_data.get('binance_id', BINANCE_PAY_ID)
        
        from database import create_binance_deposit
        await create_binance_deposit(user_id, usdt_amount, vnd_amount, code)
        
        context.user_data['binance_deposit_code'] = code
        context.user_data['binance_usdt'] = usdt_amount
        context.user_data['binance_vnd'] = vnd_amount
        
        text = get_text(lang, "binance_info").format(id=binance_id, amount=usdt_amount, code=code)
        cancel_text = get_text(lang, "btn_cancel")
        keyboard = [[KeyboardButton(cancel_text)]]
        await update.message.reply_text(text, parse_mode="HTML", reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True))
        return WAITING_BINANCE_SCREENSHOT
        
    except ValueError:
        await update.message.reply_text(get_text(lang, "invalid_amount"))
        return WAITING_BINANCE_AMOUNT

async def process_binance_screenshot(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Xử lý khi user gửi screenshot"""
    user_id = update.effective_user.id
    lang = await get_user_language(user_id)
    
    if update.message.text and update.message.text.strip() in ["❌ Hủy", "❌ Cancel"]:
        await update.message.reply_text(get_text(lang, "deposit_cancelled"), reply_markup=user_reply_keyboard(lang))
        return ConversationHandler.END
    
    if not update.message.photo:
        await update.message.reply_text(get_text(lang, "binance_send_screenshot"))
        return WAITING_BINANCE_SCREENSHOT
    
    photo = update.message.photo[-1]
    file_id = photo.file_id
    
    code = context.user_data.get('binance_deposit_code')
    usdt_amount = context.user_data.get('binance_usdt')
    vnd_amount = context.user_data.get('binance_vnd')
    
    if not code:
        await update.message.reply_text(get_text(lang, "error"), reply_markup=user_reply_keyboard(lang))
        return ConversationHandler.END
    
    from database import update_binance_deposit_screenshot
    await update_binance_deposit_screenshot(user_id, code, file_id)
    
    # Thông báo cho admin (tiếng Việt) - không gửi cho chính user đang nạp
    for admin_id in ADMIN_IDS:
        if admin_id == user_id:
            continue  # Không gửi thông báo cho chính mình
        try:
            await context.bot.send_photo(
                chat_id=admin_id,
                photo=file_id,
                caption=f"🔔 YÊU CẦU NẠP USDT MỚI!\n\n"
                        f"👤 User: {user_id}\n"
                        f"💵 Số tiền: {usdt_amount} USDT\n"
                        f"📝 Code: {code}\n\n"
                        f"Vào Admin → 🔶 Duyệt Binance để xử lý."
            )
        except:
            pass
    
    await update.message.reply_text(
        get_text(lang, "binance_submitted").format(amount=usdt_amount, code=code),
        reply_markup=user_reply_keyboard(lang)
    )
    
    context.user_data.pop('binance_deposit_code', None)
    context.user_data.pop('binance_usdt', None)
    context.user_data.pop('binance_vnd', None)
    
    return ConversationHandler.END

# ============ RÚT USDT ============

async def handle_usdt_withdraw_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler cho nút Rút USDT - hiện thông báo liên hệ admin"""
    user_id = update.effective_user.id
    lang = await get_user_language(user_id)
    
    balance_usdt = await get_balance_usdt(user_id)
    
    from database import get_setting
    admin_contact = await get_setting("admin_contact", "")
    admin_text = f"@{admin_contact}" if admin_contact else "admin"
    
    if lang == 'en':
        text = (f"💸 WITHDRAW USDT\n\n"
                f"💵 Your balance: {balance_usdt} USDT\n\n"
                f"📩 To withdraw USDT, please contact {admin_text}\n\n"
                f"⚠️ Minimum: 10 USDT\n"
                f"🌐 Network: TRC20 / BEP20")
    else:
        text = (f"💸 RÚT USDT\n\n"
                f"💵 Số dư của bạn: {balance_usdt} USDT\n\n"
                f"📩 Để rút USDT, vui lòng liên hệ {admin_text}\n\n"
                f"⚠️ Tối thiểu: 10 USDT\n"
                f"🌐 Network: TRC20 / BEP20")
    
    await update.message.reply_text(text, reply_markup=user_reply_keyboard(lang))
