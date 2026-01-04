from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from database import get_or_create_user, get_balance, get_products, get_user_orders, get_user_language, set_user_language
from keyboards import user_reply_keyboard, products_keyboard
from locales import get_text

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    db_user = await get_or_create_user(user.id, user.username)
    lang = db_user.get('language', 'vi')
    
    # Nếu user chưa có ngôn ngữ (mới), hiện menu chọn
    if not db_user.get('language') or db_user.get('language') == '':
        keyboard = [
            [InlineKeyboardButton("🇻🇳 Tiếng Việt", callback_data="set_lang_vi")],
            [InlineKeyboardButton("🇬🇧 English", callback_data="set_lang_en")],
        ]
        await update.message.reply_text(
            "🌐 Chọn ngôn ngữ / Select language:",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return
    
    # User đã chọn ngôn ngữ rồi, hiện giao diện bình thường
    welcome_text = get_text(lang, "welcome").format(name=user.first_name)
    select_text = get_text(lang, "select_product")
    
    await update.message.reply_text(welcome_text, reply_markup=user_reply_keyboard(lang))
    
    products = await get_products()
    await update.message.reply_text(select_text, reply_markup=products_keyboard(products, lang))

async def handle_change_language(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Hiện menu đổi ngôn ngữ"""
    keyboard = [
        [InlineKeyboardButton("🇻🇳 Tiếng Việt", callback_data="set_lang_vi")],
        [InlineKeyboardButton("🇬🇧 English", callback_data="set_lang_en")],
    ]
    await update.message.reply_text(
        "🌐 Chọn ngôn ngữ / Select language:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def set_language(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Xử lý khi user chọn ngôn ngữ"""
    query = update.callback_query
    await query.answer()
    
    user = query.from_user
    lang = query.data.split("_")[2]  # set_lang_vi -> vi
    
    await set_user_language(user.id, lang)
    
    # Lấy text theo ngôn ngữ đã chọn
    lang_text = get_text(lang, "language_set")
    welcome_text = get_text(lang, "welcome").format(name=user.first_name)
    select_text = get_text(lang, "select_product")
    
    await query.edit_message_text(f"{lang_text}\n\n{welcome_text}")
    
    # Hiện danh sách sản phẩm với reply keyboard
    products = await get_products()
    await context.bot.send_message(
        chat_id=query.message.chat_id,
        text=select_text,
        reply_markup=user_reply_keyboard(lang)
    )
    await context.bot.send_message(
        chat_id=query.message.chat_id,
        text="👇",
        reply_markup=products_keyboard(products, lang)
    )

async def handle_history_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Xử lý khi user bấm nút Lịch sử từ reply keyboard"""
    user_id = update.effective_user.id
    lang = await get_user_language(user_id)
    orders = await get_user_orders(user_id)
    
    if not orders:
        await update.message.reply_text(get_text(lang, "history_empty"))
        return
    
    text = get_text(lang, "history_title")
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
        
        keyboard.append([InlineKeyboardButton(f"#{order_id} {short_name} x{quantity} {price_str}", callback_data=f"order_detail_{order_id}")])
    
    keyboard.append([InlineKeyboardButton(get_text(lang, "btn_back"), callback_data="back_main")])
    
    await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard))

async def handle_user_id(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Xử lý khi user bấm nút User ID từ reply keyboard"""
    user_id = update.effective_user.id
    await update.message.reply_text(f"🆔 User ID: `{user_id}`", parse_mode="Markdown")

async def handle_balance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    lang = await get_user_language(user_id)
    balance = await get_balance(user_id)
    from database import get_balance_usdt, get_setting
    balance_usdt = await get_balance_usdt(user_id)
    admin_contact = await get_setting("admin_contact", "")
    
    text = get_text(lang, "balance_vnd").format(amount=f"{balance:,}")
    text += "\n" + get_text(lang, "balance_usdt").format(amount=f"{balance_usdt:.2f}")
    
    # Thêm hướng dẫn rút tiền
    admin_text = f"@{admin_contact}" if admin_contact else "admin"
    if lang == 'en':
        text += f"\n\n💸 To withdraw, contact {admin_text}"
    else:
        text += f"\n\n💸 Để rút tiền, liên hệ {admin_text}"
    
    await update.message.reply_text(text)

async def back_to_main(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    lang = await get_user_language(user_id)
    
    products = await get_products()
    await query.edit_message_text(
        get_text(lang, "select_product"),
        reply_markup=products_keyboard(products, lang)
    )
