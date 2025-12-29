from telegram import Update
from telegram.ext import ContextTypes
from database import get_or_create_user, get_balance, get_products, get_user_orders
from keyboards import user_reply_keyboard, products_keyboard

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    await get_or_create_user(user.id, user.username)
    
    # Gửi reply keyboard trước
    await update.message.reply_text(
        f"🎉 Chào mừng {user.first_name}!",
        reply_markup=user_reply_keyboard()
    )
    
    # Hiện danh sách sản phẩm
    products = await get_products()
    await update.message.reply_text(
        "👉 CHỌN SẢN PHẨM BÊN DƯỚI:",
        reply_markup=products_keyboard(products)
    )

async def handle_history_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Xử lý khi user bấm nút Lịch sử từ reply keyboard"""
    user_id = update.effective_user.id
    orders = await get_user_orders(user_id)
    
    if not orders:
        await update.message.reply_text("📜 Bạn chưa có đơn hàng nào!")
        return
    
    text = "📜 LỊCH SỬ MUA HÀNG:\n\n"
    for order in orders:
        text += f"#{order[0]} | {order[1]} | {order[3]:,}đ\n"
        text += f"📋 <code>{order[2]}</code>\n\n"
    
    await update.message.reply_text(text, parse_mode="HTML")

async def handle_user_id(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Xử lý khi user bấm nút User ID từ reply keyboard"""
    user_id = update.effective_user.id
    await update.message.reply_text(f"🆔 User ID của bạn: `{user_id}`", parse_mode="Markdown")

async def handle_balance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    balance = await get_balance(user_id)
    text = f"💰 Số dư của bạn: {balance:,}đ"
    await update.message.reply_text(text)

async def back_to_main(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    products = await get_products()
    await query.edit_message_text(
        "👉 CHỌN SẢN PHẨM BÊN DƯỚI:",
        reply_markup=products_keyboard(products)
    )
