import re
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from database import (
    get_or_create_user,
    get_balance,
    get_products,
    get_setting,
    get_user_orders,
    get_user_language,
    set_user_language,
)
from keyboards import products_keyboard
from helpers.ui import get_shop_page_size, get_user_keyboard, is_feature_enabled
from helpers.menu import delete_last_menu_message, set_last_menu_message, clear_last_menu_message
from locales import get_text


def _normalize_admin_contact(raw_value: str) -> str:
    if not raw_value:
        return ""
    text = str(raw_value).strip()
    if not text:
        return ""

    text = text.replace("https://", "").replace("http://", "")
    if text.startswith("t.me/"):
        text = text.split("t.me/", 1)[1]
    if text.startswith("@"):
        text = text[1:]
    text = text.split("?", 1)[0].split("/", 1)[0].strip()

    match = re.match(r"^[A-Za-z0-9_]+$", text)
    return text if match else ""


def _looks_like_url(text: str) -> bool:
    lower = text.lower()
    return lower.startswith("http://") or lower.startswith("https://")


def _normalize_web_url(raw_value: str) -> str:
    if not raw_value:
        return ""
    text = str(raw_value).strip()
    if not text:
        return ""

    if _looks_like_url(text):
        return text
    if text.startswith("t.me/"):
        username = _normalize_admin_contact(text)
        return f"https://t.me/{username}" if username else ""
    if text.startswith("www.") or re.match(r"^[A-Za-z0-9.-]+\.[A-Za-z]{2,}(/.*)?$", text):
        return f"https://{text}"
    return ""


def _format_contact_button_text(label: str, icon: str, fallback: str) -> str:
    text = (label or "").strip() or fallback
    if text[0] in {"💬", "📘", "💠", "🔗"}:
        return text
    return f"{icon} {text}"


def _parse_support_contacts(raw_value: str, admin_contact: str) -> list[tuple[str, str]]:
    contacts: list[tuple[str, str]] = []
    seen_urls: set[str] = set()

    def add_contact(label: str, url: str):
        cleaned_url = (url or "").strip()
        if not cleaned_url:
            return
        key = cleaned_url.lower()
        if key in seen_urls:
            return
        seen_urls.add(key)
        contacts.append((label.strip(), cleaned_url))

    raw_lines = str(raw_value or "")
    for line in raw_lines.splitlines():
        line = line.strip()
        if not line:
            continue

        if "|" in line:
            raw_label, raw_target = line.split("|", 1)
        else:
            raw_label, raw_target = "", line
        label = raw_label.strip()
        target = raw_target.strip()
        if not target:
            continue

        label_lower = label.lower()
        target_lower = target.lower()
        is_telegram = (
            "telegram" in label_lower
            or target.startswith("@")
            or target_lower.startswith("t.me/")
            or "t.me/" in target_lower
        )
        is_facebook = "facebook" in label_lower or "facebook.com" in target_lower or "fb.com" in target_lower
        is_zalo = "zalo" in label_lower or "zalo.me" in target_lower or "zaloapp.com" in target_lower

        if is_telegram:
            username = _normalize_admin_contact(target)
            if username:
                button_text = _format_contact_button_text(label, "💬", "Telegram")
                add_contact(button_text, f"https://t.me/{username}")
            continue

        if is_facebook:
            url = _normalize_web_url(target)
            if url:
                button_text = _format_contact_button_text(label, "📘", "Facebook")
                add_contact(button_text, url)
            continue

        if is_zalo:
            url = _normalize_web_url(target)
            if url:
                button_text = _format_contact_button_text(label, "💠", "Zalo")
                add_contact(button_text, url)
            continue

        url = _normalize_web_url(target)
        if url:
            button_text = _format_contact_button_text(label, "🔗", "Liên hệ")
            add_contact(button_text, url)

    if admin_contact:
        add_contact("💬 Telegram", f"https://t.me/{admin_contact}")

    return contacts

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
    
    await update.message.reply_text(welcome_text, reply_markup=await get_user_keyboard(lang))
    if not await is_feature_enabled("show_shop"):
        await update.message.reply_text("⚠️ Tính năng này đang tạm tắt.")
        return

    products = await get_products()
    page_size = await get_shop_page_size()
    menu_msg = await update.message.reply_text(
        select_text,
        reply_markup=products_keyboard(products, lang, page=0, page_size=page_size),
    )
    set_last_menu_message(context, menu_msg)

async def handle_change_language(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Hiện menu đổi ngôn ngữ"""
    if not await is_feature_enabled("show_language"):
        await update.message.reply_text("⚠️ Tính năng này đang tạm tắt.")
        return
    await delete_last_menu_message(context, update.effective_chat.id)
    keyboard = [
        [InlineKeyboardButton("🇻🇳 Tiếng Việt", callback_data="set_lang_vi")],
        [InlineKeyboardButton("🇬🇧 English", callback_data="set_lang_en")],
    ]
    menu_msg = await update.message.reply_text(
        "🌐 Chọn ngôn ngữ / Select language:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    set_last_menu_message(context, menu_msg)

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
    await context.bot.send_message(
        chat_id=query.message.chat_id,
        text=select_text,
        reply_markup=await get_user_keyboard(lang)
    )
    if not await is_feature_enabled("show_shop"):
        await context.bot.send_message(
            chat_id=query.message.chat_id,
            text="⚠️ Tính năng này đang tạm tắt."
        )
        return
    products = await get_products()
    page_size = await get_shop_page_size()
    menu_msg = await context.bot.send_message(
        chat_id=query.message.chat_id,
        text=select_text,
        reply_markup=products_keyboard(products, lang, page=0, page_size=page_size)
    )
    set_last_menu_message(context, menu_msg)

async def handle_history_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Xử lý khi user bấm nút Lịch sử từ reply keyboard"""
    user_id = update.effective_user.id
    lang = await get_user_language(user_id)
    if not await is_feature_enabled("show_history"):
        await update.message.reply_text("⚠️ Tính năng này đang tạm tắt.", reply_markup=await get_user_keyboard(lang))
        return
    await delete_last_menu_message(context, update.effective_chat.id)
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
    
    keyboard.append([InlineKeyboardButton("🗑 Xóa", callback_data="delete_msg")])
    
    menu_msg = await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
    set_last_menu_message(context, menu_msg)

async def handle_user_id(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Xử lý khi user bấm nút User ID từ reply keyboard"""
    user_id = update.effective_user.id
    await update.message.reply_text(f"🆔 User ID: `{user_id}`", parse_mode="Markdown")

async def handle_balance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    lang = await get_user_language(user_id)
    if not await is_feature_enabled("show_balance"):
        await update.message.reply_text("⚠️ Tính năng này đang tạm tắt.", reply_markup=await get_user_keyboard(lang))
        return
    await delete_last_menu_message(context, update.effective_chat.id)
    balance = await get_balance(user_id)
    from database import get_balance_usdt
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


async def handle_support_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    lang = await get_user_language(user_id)
    if not await is_feature_enabled("show_support"):
        await update.message.reply_text("⚠️ Tính năng này đang tạm tắt.", reply_markup=await get_user_keyboard(lang))
        return
    pressed_text = (update.message.text or "").strip()
    pressed_legacy_icon = pressed_text.startswith("🆘")
    contact = _normalize_admin_contact(await get_setting("admin_contact", ""))
    contacts = _parse_support_contacts(await get_setting("support_contacts", ""), contact)

    if not contacts:
        text = (
            "❌ Chưa cài đặt liên hệ hỗ trợ. Vui lòng báo admin cập nhật mục Support contacts trong Dashboard."
            if lang != "en"
            else "❌ Support contact is not configured. Please ask admin to set Support contacts in Dashboard settings."
        )
        await update.message.reply_text(text, reply_markup=await get_user_keyboard(lang))
        return

    text = (
        "💬 HỖ TRỢ\n\nNhấn nút bên dưới để liên hệ hỗ trợ:"
        if lang != "en"
        else "💬 SUPPORT\n\nTap a button below to contact support:"
    )
    buttons = [InlineKeyboardButton(label, url=url) for label, url in contacts]
    keyboard = [buttons[i:i + 2] for i in range(0, len(buttons), 2)]
    await update.message.reply_text(
        text,
        reply_markup=InlineKeyboardMarkup(keyboard),
    )

    # Telegram may keep showing old reply-keyboard buttons until a new keyboard is sent.
    # If user pressed the legacy icon, push the refreshed keyboard once.
    if pressed_legacy_icon:
        refresh_text = "✅ Đã cập nhật icon Hỗ trợ mới." if lang != "en" else "✅ Support icon updated."
        await update.message.reply_text(refresh_text, reply_markup=await get_user_keyboard(lang))

async def back_to_main(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    lang = await get_user_language(user_id)
    
    if not await is_feature_enabled("show_shop"):
        await query.edit_message_text("⚠️ Tính năng này đang tạm tắt.")
        return
    products = await get_products()
    page_size = await get_shop_page_size()
    await query.edit_message_text(
        get_text(lang, "select_product"),
        reply_markup=products_keyboard(products, lang, page=0, page_size=page_size)
    )
    set_last_menu_message(context, query.message)

async def delete_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    try:
        await query.message.delete()
    except Exception:
        # Fallback if deletion is not allowed
        await query.edit_message_text("✅ Đã xóa.")
    clear_last_menu_message(context, query.message)
