from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler, MessageHandler, filters
from database import (
    get_products, add_product, delete_product, add_stock_bulk,
    get_pending_deposits, confirm_deposit, cancel_deposit, get_stats,
    get_pending_withdrawals, confirm_withdrawal, cancel_withdrawal,
    get_bank_settings, set_setting, get_setting, get_all_user_ids,
    get_stock_by_product, get_stock_detail, update_stock_content, delete_stock, get_product,
    delete_all_stock, export_stock, get_sold_codes_by_product, get_sold_codes_by_user, search_user_by_id
)
from keyboards import (
    admin_menu_keyboard, admin_products_keyboard, admin_stock_keyboard,
    pending_deposits_keyboard, pending_withdrawals_keyboard, back_keyboard, main_menu_keyboard,
    admin_reply_keyboard, user_reply_keyboard, admin_view_stock_keyboard,
    admin_stock_list_keyboard, admin_stock_detail_keyboard, admin_sold_codes_keyboard
)
import io
from config import ADMIN_IDS

# States
ADD_PRODUCT_NAME, ADD_PRODUCT_PRICE = range(2)
ADD_PRODUCT_PRICE_USDT = 3
ADD_STOCK_CONTENT = 10
BANK_NAME, ACCOUNT_NUMBER, ACCOUNT_NAME, SEPAY_TOKEN = range(20, 24)
BINANCE_ID = 24
NOTIFICATION_MESSAGE = 30
EDIT_STOCK_CONTENT = 31
SEARCH_USER_ID = 32

def is_admin(user_id: int) -> bool:
    return user_id in ADMIN_IDS

async def admin_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not is_admin(user_id):
        await update.message.reply_text("❌ Bạn không có quyền truy cập!")
        return
    
    # Gửi reply keyboard admin
    await update.message.reply_text(
        "🔐 ADMIN PANEL\n\nChọn chức năng quản trị:",
        reply_markup=admin_reply_keyboard()
    )

async def admin_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    if not is_admin(query.from_user.id):
        await query.edit_message_text("❌ Bạn không có quyền truy cập!")
        return
    
    text = """
🔐 ADMIN PANEL

Chọn chức năng quản trị:
"""
    await query.edit_message_text(text, reply_markup=admin_menu_keyboard())

async def admin_products(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    products = await get_products()
    text = "📦 QUẢN LÝ SẢN PHẨM\n\nNhấn ❌ để xóa sản phẩm:"
    await query.edit_message_text(text, reply_markup=admin_products_keyboard(products))

async def admin_delete_product(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    product_id = int(query.data.split("_")[2])
    product = await get_product(product_id)
    
    if not product:
        await query.edit_message_text("❌ Sản phẩm không tồn tại!", reply_markup=back_keyboard("admin_products"))
        return
    
    # Hiện xác nhận xóa
    keyboard = [
        [InlineKeyboardButton("✅ Xác nhận xóa", callback_data=f"admin_confirmdel_{product_id}")],
        [InlineKeyboardButton("🔙 Hủy", callback_data="admin_products")],
    ]
    await query.edit_message_text(
        f"⚠️ XÁC NHẬN XÓA SẢN PHẨM\n\n📦 {product['name']}\n💰 {product['price']:,}đ\n📊 Stock: {product['stock']}\n\nBạn có chắc muốn xóa?",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def admin_confirm_delete_product(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    product_id = int(query.data.split("_")[2])
    await delete_product(product_id)
    
    products = await get_products()
    text = "✅ Đã xóa sản phẩm!\n\n📦 QUẢN LÝ SẢN PHẨM:"
    await query.edit_message_text(text, reply_markup=admin_products_keyboard(products))

async def admin_add_product_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    await query.edit_message_text("📝 Nhập tên sản phẩm:")
    return ADD_PRODUCT_NAME

async def admin_add_product_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['new_product_name'] = update.message.text
    await update.message.reply_text("💰 Nhập giá sản phẩm (VNĐ):")
    return ADD_PRODUCT_PRICE

async def admin_add_product_price(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        price = int(update.message.text.replace(",", "").replace(".", ""))
        context.user_data['new_product_price'] = price
        await update.message.reply_text("💵 Nhập giá USDT (hoặc 0 nếu không bán bằng USDT):")
        return ADD_PRODUCT_PRICE_USDT
    except ValueError:
        await update.message.reply_text("❌ Giá không hợp lệ! Vui lòng nhập số:")
        return ADD_PRODUCT_PRICE

async def admin_add_product_price_usdt(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        price_usdt = float(update.message.text.replace(",", "."))
        name = context.user_data['new_product_name']
        price = context.user_data['new_product_price']
        
        await add_product(name, price, "", price_usdt)
        
        price_text = f"💰 {price:,}đ"
        if price_usdt > 0:
            price_text += f" | 💵 {price_usdt} USDT"
        
        await update.message.reply_text(
            f"✅ Đã thêm sản phẩm:\n📦 {name}\n{price_text}",
            reply_markup=back_keyboard("admin_products")
        )
    except ValueError:
        await update.message.reply_text("❌ Giá không hợp lệ! Vui lòng nhập số (VD: 0 hoặc 1.5):")
        return ADD_PRODUCT_PRICE_USDT
    
    return ConversationHandler.END

async def admin_add_stock_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    products = await get_products()
    text = "📥 THÊM STOCK\n\nChọn sản phẩm để thêm stock:"
    await query.edit_message_text(text, reply_markup=admin_stock_keyboard(products))

async def admin_select_stock_product(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    product_id = int(query.data.split("_")[2])
    context.user_data['stock_product_id'] = product_id
    
    await query.edit_message_text(
        "📝 THÊM STOCK\n\n"
        "Cách 1: Gửi text (mỗi dòng 1 sản phẩm)\n"
        "Cách 2: Gửi file .txt (hỗ trợ hàng nghìn stock)\n\n"
        "Ví dụ:\nacc1@gmail.com|pass123\nacc2@gmail.com|pass456"
    )
    return ADD_STOCK_CONTENT

async def admin_add_stock_content(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Xử lý thêm stock từ text hoặc file"""
    product_id = context.user_data.get('stock_product_id')
    if not product_id:
        await update.message.reply_text("❌ Lỗi! Vui lòng thử lại.")
        return ConversationHandler.END
    
    contents = []
    
    # Xử lý file upload
    if update.message.document:
        doc = update.message.document
        
        # Kiểm tra file type
        if not doc.file_name.endswith('.txt'):
            await update.message.reply_text("❌ Chỉ hỗ trợ file .txt!")
            return ADD_STOCK_CONTENT
        
        # Giới hạn 10MB
        if doc.file_size > 10 * 1024 * 1024:
            await update.message.reply_text("❌ File quá lớn! Tối đa 10MB.")
            return ADD_STOCK_CONTENT
        
        await update.message.reply_text("⏳ Đang xử lý file...")
        
        try:
            file = await doc.get_file()
            file_bytes = await file.download_as_bytearray()
            
            # Decode với nhiều encoding
            text_content = None
            for encoding in ['utf-8', 'utf-8-sig', 'latin-1', 'cp1252']:
                try:
                    text_content = file_bytes.decode(encoding)
                    break
                except:
                    continue
            
            if not text_content:
                await update.message.reply_text("❌ Không đọc được file! Hãy dùng encoding UTF-8.")
                return ADD_STOCK_CONTENT
            
            lines = text_content.strip().split("\n")
            contents = [line.strip() for line in lines if line.strip()]
            
        except Exception as e:
            await update.message.reply_text(f"❌ Lỗi đọc file: {str(e)}")
            return ADD_STOCK_CONTENT
    
    # Xử lý text thường
    elif update.message.text:
        lines = update.message.text.strip().split("\n")
        contents = [line.strip() for line in lines if line.strip()]
    
    if not contents:
        await update.message.reply_text("❌ Không có dữ liệu! Gửi lại text hoặc file .txt")
        return ADD_STOCK_CONTENT
    
    # Thêm stock vào database
    await add_stock_bulk(product_id, contents)
    
    await update.message.reply_text(
        f"✅ Đã thêm {len(contents):,} stock!",
        reply_markup=back_keyboard("admin_add_stock")
    )
    return ConversationHandler.END


# Deposit management
async def admin_deposits(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    deposits = await get_pending_deposits()
    
    if not deposits:
        await query.edit_message_text(
            "💳 Không có yêu cầu nạp tiền nào đang chờ duyệt.",
            reply_markup=back_keyboard("admin")
        )
        return
    
    text = "💳 DUYỆT NẠP TIỀN\n\n"
    for d in deposits:
        text += f"#{d[0]} | User: {d[1]} | {d[2]:,}đ | Code: {d[3]}\n"
    
    await query.edit_message_text(text, reply_markup=pending_deposits_keyboard(deposits))

async def admin_confirm_deposit(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    deposit_id = int(query.data.split("_")[2])
    result = await confirm_deposit(deposit_id)
    
    if result:
        user_id, amount = result
        # Notify user
        try:
            await context.bot.send_message(
                user_id,
                f"✅ Nạp tiền thành công!\n\n💰 Số tiền: {amount:,}đ\n\nCảm ơn bạn đã sử dụng dịch vụ!"
            )
        except:
            pass
    
    deposits = await get_pending_deposits()
    text = "✅ Đã duyệt nạp tiền!\n\n💳 DUYỆT NẠP TIỀN:"
    
    if not deposits:
        await query.edit_message_text(text + "\nKhông còn yêu cầu nào.", reply_markup=back_keyboard("admin"))
    else:
        await query.edit_message_text(text, reply_markup=pending_deposits_keyboard(deposits))

async def admin_cancel_deposit(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    deposit_id = int(query.data.split("_")[2])
    await cancel_deposit(deposit_id)
    
    deposits = await get_pending_deposits()
    text = "❌ Đã hủy yêu cầu nạp tiền!\n\n💳 DUYỆT NẠP TIỀN:"
    
    if not deposits:
        await query.edit_message_text(text + "\nKhông còn yêu cầu nào.", reply_markup=back_keyboard("admin"))
    else:
        await query.edit_message_text(text, reply_markup=pending_deposits_keyboard(deposits))

async def admin_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    stats = await get_stats()
    products = await get_products()
    
    text = f"""
📊 THỐNG KÊ HỆ THỐNG

👥 Tổng người dùng: {stats['users']}
🛒 Tổng đơn hàng: {stats['orders']}
💰 Tổng doanh thu: {stats['revenue']:,}đ

📦 Sản phẩm:
"""
    for p in products:
        text += f"• {p['name']}: còn {p['stock']} stock\n"
    
    await query.edit_message_text(text, reply_markup=back_keyboard("admin"))

# Withdrawal management
async def admin_withdrawals(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    withdrawals = await get_pending_withdrawals()
    
    if not withdrawals:
        await query.edit_message_text(
            "💸 Không có yêu cầu rút tiền nào đang chờ duyệt.",
            reply_markup=back_keyboard("admin")
        )
        return
    
    text = "💸 DUYỆT RÚT TIỀN\n\nChọn yêu cầu để xem chi tiết & QR:\n\n"
    for w in withdrawals:
        text += f"#{w[0]} | {w[2]:,}đ | {w[3]}\n"
    
    await query.edit_message_text(text, reply_markup=pending_withdrawals_keyboard(withdrawals))

async def admin_view_withdrawal(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Xem chi tiết yêu cầu rút tiền + QR code"""
    query = update.callback_query
    await query.answer()
    
    withdrawal_id = int(query.data.split("_")[2])
    
    # Lấy thông tin withdrawal
    from database import get_withdrawal_detail
    withdrawal = await get_withdrawal_detail(withdrawal_id)
    
    if not withdrawal:
        await query.edit_message_text("❌ Không tìm thấy yêu cầu!", reply_markup=back_keyboard("admin_withdraws"))
        return
    
    w_id, user_id, amount, bank_info, status, created_at = withdrawal
    
    # Parse bank_info (format: "BankName - AccountNumber")
    parts = bank_info.split(" - ")
    if len(parts) == 2:
        bank_name, account_number = parts
    else:
        bank_name = "Unknown"
        account_number = bank_info
    
    # Tạo QR VietQR hoặc MoMo
    from handlers.shop import BANK_CODES
    bank_code = BANK_CODES.get(bank_name, "")
    
    if bank_code == "MOMO" or bank_name.lower() == "momo":
        # MoMo không hỗ trợ VietQR chuẩn, hiện thông tin để chuyển thủ công
        qr_url = None
        bank_display = "MoMo"
    elif bank_code:
        # QR VietQR cho ngân hàng
        qr_url = f"https://img.vietqr.io/image/{bank_code}-{account_number}-compact2.png?amount={amount}&addInfo=Rut%20tien"
        bank_display = bank_name
    else:
        # Không có QR, hiện thông tin thủ công
        qr_url = None
        bank_display = bank_name
    
    text = f"""
💸 CHI TIẾT YÊU CẦU RÚT TIỀN #{w_id}

👤 User ID: {user_id}
💰 Số tiền: {amount:,}đ
🏦 Ngân hàng: {bank_display}
🔢 Số TK/SĐT: {account_number}
📅 Thời gian: {created_at[:19]}
"""
    
    keyboard = [
        [InlineKeyboardButton("✅ Đã chuyển - Duyệt", callback_data=f"admin_confirm_withdraw_{w_id}")],
        [InlineKeyboardButton("❌ Từ chối", callback_data=f"admin_cancel_withdraw_{w_id}")],
        [InlineKeyboardButton("🔙 Quay lại", callback_data="admin_withdraws")],
    ]
    
    # Gửi ảnh QR nếu có
    try:
        await query.message.delete()
        if qr_url:
            await context.bot.send_photo(
                chat_id=query.message.chat_id,
                photo=qr_url,
                caption=text + "\n⬇️ Quét QR để chuyển tiền:",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
        else:
            if bank_display == "MoMo":
                text += "\n📱 Mở app MoMo → Chuyển tiền → Nhập SĐT trên"
            else:
                text += "\n⚠️ Vui lòng chuyển khoản thủ công"
            await context.bot.send_message(
                chat_id=query.message.chat_id,
                text=text,
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
    except Exception as e:
        # Fallback
        await context.bot.send_message(
            chat_id=query.message.chat_id,
            text=text + (f"\n🔗 QR: {qr_url}" if qr_url else ""),
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

async def admin_confirm_withdrawal(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    withdrawal_id = int(query.data.split("_")[3])
    result = await confirm_withdrawal(withdrawal_id)
    
    if result:
        user_id, amount, bank_info = result
        try:
            await context.bot.send_message(
                user_id,
                f"✅ RÚT TIỀN THÀNH CÔNG!\n\n"
                f"💰 Số tiền: {amount:,}đ\n"
                f"🏦 Tài khoản: {bank_info}\n\n"
                f"💸 Tiền đã được chuyển vào tài khoản của bạn!"
            )
        except Exception as e:
            print(f"Error sending withdrawal notification: {e}")
        
        text = "✅ Đã duyệt rút tiền!"
    else:
        text = "❌ Không thể duyệt! User không đủ số dư."
    
    # Xóa message cũ (có thể là ảnh QR)
    try:
        await query.message.delete()
    except:
        pass
    
    withdrawals = await get_pending_withdrawals()
    text += "\n\n💸 DUYỆT RÚT TIỀN:"
    
    if not withdrawals:
        await context.bot.send_message(
            chat_id=query.message.chat_id,
            text=text + "\nKhông còn yêu cầu nào.",
            reply_markup=back_keyboard("admin")
        )
    else:
        await context.bot.send_message(
            chat_id=query.message.chat_id,
            text=text,
            reply_markup=pending_withdrawals_keyboard(withdrawals)
        )

async def admin_cancel_withdrawal(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    withdrawal_id = int(query.data.split("_")[3])
    result = await cancel_withdrawal(withdrawal_id)
    
    if result:
        user_id, amount = result
        try:
            await context.bot.send_message(
                user_id,
                f"❌ Yêu cầu rút tiền bị từ chối!\n\n💰 Số tiền {amount:,}đ đã được hoàn lại vào tài khoản."
            )
        except:
            pass
    
    withdrawals = await get_pending_withdrawals()
    text = "❌ Đã hủy yêu cầu rút tiền!\n\n💸 DUYỆT RÚT TIỀN:"
    
    if not withdrawals:
        await query.edit_message_text(text + "\nKhông còn yêu cầu nào.", reply_markup=back_keyboard("admin"))
    else:
        await query.edit_message_text(text, reply_markup=pending_withdrawals_keyboard(withdrawals))

async def cancel_conversation(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("❌ Đã hủy.", reply_markup=user_reply_keyboard())
    return ConversationHandler.END

# Admin reply keyboard handlers
async def handle_admin_products_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return
    products = await get_products()
    text = "📦 QUẢN LÝ SẢN PHẨM\n\nNhấn ❌ để xóa sản phẩm:"
    await update.message.reply_text(text, reply_markup=admin_products_keyboard(products))

async def handle_admin_stock_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return
    products = await get_products()
    text = "📥 THÊM STOCK\n\nChọn sản phẩm để thêm stock:"
    await update.message.reply_text(text, reply_markup=admin_stock_keyboard(products))

async def handle_admin_manage_stock_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler cho nút text Quản lý stock"""
    if not is_admin(update.effective_user.id):
        return
    products = await get_products()
    text = "📋 QUẢN LÝ STOCK\n\nChọn sản phẩm để xem/sửa stock:"
    await update.message.reply_text(text, reply_markup=admin_view_stock_keyboard(products))

async def handle_admin_sold_codes_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler cho nút text Xem code đã bán"""
    if not is_admin(update.effective_user.id):
        return
    products = await get_products()
    text = "📜 XEM CODE ĐÃ BÁN\n\nChọn sản phẩm hoặc tìm theo User ID:"
    await update.message.reply_text(text, reply_markup=admin_sold_codes_keyboard(products))

async def handle_admin_withdrawals_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return
    withdrawals = await get_pending_withdrawals()
    if not withdrawals:
        await update.message.reply_text(
            "💸 Không có yêu cầu rút tiền nào đang chờ duyệt.",
            reply_markup=back_keyboard("admin")
        )
        return
    text = "💸 DUYỆT RÚT TIỀN\n\n"
    for w in withdrawals:
        text += f"#{w[0]} | User: {w[1]} | {w[2]:,}đ | SĐT: {w[3]}\n"
    await update.message.reply_text(text, reply_markup=pending_withdrawals_keyboard(withdrawals))

async def handle_admin_transactions_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler gộp: Duyệt rút tiền VNĐ + Duyệt nạp Binance"""
    if not is_admin(update.effective_user.id):
        return
    
    withdrawals = await get_pending_withdrawals()
    from database import get_pending_binance_deposits
    binance_deposits = await get_pending_binance_deposits()
    
    if not withdrawals and not binance_deposits:
        await update.message.reply_text(
            "✅ Không có giao dịch nào đang chờ duyệt.",
            reply_markup=back_keyboard("admin")
        )
        return
    
    text = "✅ DUYỆT GIAO DỊCH\n\n"
    
    keyboard = []
    
    if withdrawals:
        text += f"💸 Rút tiền VNĐ: {len(withdrawals)} yêu cầu\n"
        keyboard.append([InlineKeyboardButton(f"💸 Rút VNĐ ({len(withdrawals)})", callback_data="admin_withdraws")])
    
    if binance_deposits:
        text += f"🔶 Nạp USDT: {len(binance_deposits)} yêu cầu\n"
        keyboard.append([InlineKeyboardButton(f"🔶 Nạp USDT ({len(binance_deposits)})", callback_data="admin_binance")])
    
    keyboard.append([InlineKeyboardButton("🔙 Quay lại", callback_data="admin")])
    
    await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard))

async def handle_admin_bank_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return
    settings = await get_bank_settings()
    binance_id = await get_setting("binance_pay_id", "")
    admin_contact = await get_setting("admin_contact", "")
    
    text = f"""
🏦 CÀI ĐẶT THANH TOÁN

👤 Admin liên hệ: {('@' + admin_contact) if admin_contact else 'Chưa cài đặt'}

📌 Ngân hàng (VNĐ):
• Ngân hàng: {settings['bank_name'] or 'Chưa cài đặt'}
• Số TK: {settings['account_number'] or 'Chưa cài đặt'}
• Tên TK: {settings['account_name'] or 'Chưa cài đặt'}
• SePay Token: {'✅ Đã cài' if settings['sepay_token'] else '❌ Chưa cài'}

🔶 Binance (USDT):
• Binance ID: {binance_id or 'Chưa cài đặt'}
"""
    keyboard = [
        [InlineKeyboardButton("👤 Admin liên hệ", callback_data="set_admin_contact")],
        [InlineKeyboardButton("🔑 SePay Token", callback_data="set_sepay_token"),
         InlineKeyboardButton("🔄 Cập nhật SePay", callback_data="refresh_bank_info")],
        [InlineKeyboardButton("🔶 Binance ID", callback_data="set_binance_id")],
    ]
    await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard))

async def handle_exit_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 Đã thoát Admin Panel",
        reply_markup=user_reply_keyboard()
    )

# Notification to all users
async def notification_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Lệnh /notification để gửi thông báo đến tất cả user"""
    user_id = update.effective_user.id
    if not is_admin(user_id):
        await update.message.reply_text("❌ Bạn không có quyền sử dụng lệnh này!")
        return ConversationHandler.END
    
    await update.message.reply_text(
        "📢 GỬI THÔNG BÁO\n\n"
        "Nhập nội dung thông báo muốn gửi đến tất cả user:\n\n"
        "💡 Gợi ý: Bạn có thể dùng emoji và xuống dòng thoải mái.\n"
        "Gửi /cancel để hủy."
    )
    return NOTIFICATION_MESSAGE

async def notification_send(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Gửi thông báo đến tất cả user"""
    message_content = update.message.text
    
    # Lấy tất cả user
    user_ids = await get_all_user_ids()
    
    if not user_ids:
        await update.message.reply_text("❌ Chưa có user nào trong hệ thống!")
        return ConversationHandler.END
    
    # Format thông báo
    notification_text = f"📢 Thông báo từ Admin:\n\n{message_content}"
    
    await update.message.reply_text(f"⏳ Đang gửi thông báo đến {len(user_ids)} user...")
    
    success = 0
    failed = 0
    
    for uid in user_ids:
        try:
            await context.bot.send_message(chat_id=uid, text=notification_text)
            success += 1
        except Exception:
            failed += 1
    
    await update.message.reply_text(
        f"✅ Đã gửi thông báo!\n\n"
        f"📤 Thành công: {success}\n"
        f"❌ Thất bại: {failed} (user đã block bot)"
    )
    return ConversationHandler.END

# Stock management
async def admin_manage_stock(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Menu quản lý stock - chọn sản phẩm để xem"""
    query = update.callback_query
    await query.answer()
    
    products = await get_products()
    text = "📋 QUẢN LÝ STOCK\n\nChọn sản phẩm để xem/sửa stock:"
    await query.edit_message_text(text, reply_markup=admin_view_stock_keyboard(products))

async def admin_view_stock(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Xem danh sách stock của sản phẩm"""
    query = update.callback_query
    await query.answer()
    
    product_id = int(query.data.split("_")[2])
    context.user_data['current_product_id'] = product_id
    
    product = await get_product(product_id)
    stocks = await get_stock_by_product(product_id)
    
    if not stocks:
        keyboard = [
            [InlineKeyboardButton("📥 Thêm stock", callback_data=f"admin_stock_{product_id}")],
            [InlineKeyboardButton("🔙 Quay lại", callback_data="admin_manage_stock")],
        ]
        await query.edit_message_text(
            f"📦 {product['name']}\n\n❌ Chưa có stock nào!",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return
    
    total = len(stocks)
    sold = sum(1 for s in stocks if s[2])
    available = total - sold
    
    text = f"📦 {product['name']}\n\n📊 Tổng: {total} | 🟢 Còn: {available} | 🔴 Đã bán: {sold}"
    
    # Thêm các nút quản lý nhanh
    keyboard = [
        [InlineKeyboardButton("📤 Export stock còn", callback_data=f"admin_export_{product_id}")],
        [InlineKeyboardButton("🗑 Xóa stock còn", callback_data=f"admin_clearunsold_{product_id}"),
         InlineKeyboardButton("🗑 Xóa TẤT CẢ", callback_data=f"admin_clearall_{product_id}")],
        [InlineKeyboardButton("📥 Thêm stock mới", callback_data=f"admin_stock_{product_id}")],
        [InlineKeyboardButton("🔙 Quay lại", callback_data="admin_manage_stock")],
    ]
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))

async def admin_export_stock(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Export stock còn lại ra file .txt"""
    query = update.callback_query
    await query.answer("Đang export...")
    
    product_id = int(query.data.split("_")[2])
    product = await get_product(product_id)
    stocks = await export_stock(product_id, only_unsold=True)
    
    if not stocks:
        await query.edit_message_text(
            f"📦 {product['name']}\n\n❌ Không có stock nào còn lại!",
            reply_markup=back_keyboard(f"admin_viewstock_{product_id}")
        )
        return
    
    # Tạo file nhanh
    filename = f"{product['name']}_stock.txt"
    content = "\n".join(stocks)
    file_buf = io.BytesIO(content.encode('utf-8'))
    file_buf.seek(0)
    
    await context.bot.send_document(
        chat_id=query.message.chat_id,
        document=file_buf,
        filename=filename,
        caption=f"📤 {len(stocks)} stock của {product['name']}"
    )

async def admin_clear_unsold_stock(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Xóa tất cả stock chưa bán"""
    query = update.callback_query
    await query.answer()
    
    product_id = int(query.data.split("_")[2])
    product = await get_product(product_id)
    
    # Đếm trước khi xóa
    stocks = await get_stock_by_product(product_id)
    unsold = sum(1 for s in stocks if not s[2])
    
    await delete_all_stock(product_id, only_unsold=True)
    
    await query.edit_message_text(
        f"✅ Đã xóa {unsold} stock chưa bán của {product['name']}!",
        reply_markup=back_keyboard(f"admin_viewstock_{product_id}")
    )

async def admin_clear_all_stock(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Xóa TẤT CẢ stock (cả đã bán)"""
    query = update.callback_query
    await query.answer()
    
    product_id = int(query.data.split("_")[2])
    product = await get_product(product_id)
    
    # Đếm trước khi xóa
    stocks = await get_stock_by_product(product_id)
    total = len(stocks)
    
    await delete_all_stock(product_id, only_unsold=False)
    
    await query.edit_message_text(
        f"✅ Đã xóa TẤT CẢ {total} stock của {product['name']}!",
        reply_markup=back_keyboard(f"admin_viewstock_{product_id}")
    )

async def admin_stock_page(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Chuyển trang danh sách stock"""
    query = update.callback_query
    await query.answer()
    
    parts = query.data.split("_")
    product_id = int(parts[2])
    page = int(parts[3])
    
    product = await get_product(product_id)
    stocks = await get_stock_by_product(product_id)
    
    total = len(stocks)
    sold = sum(1 for s in stocks if s[2])
    available = total - sold
    
    text = f"📦 {product['name']}\n\n📊 Tổng: {total} | 🟢 Còn: {available} | 🔴 Đã bán: {sold}\n\nChọn stock để xem chi tiết:"
    await query.edit_message_text(text, reply_markup=admin_stock_list_keyboard(stocks, product_id, page))

async def admin_stock_detail(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Xem chi tiết một stock"""
    query = update.callback_query
    await query.answer()
    
    stock_id = int(query.data.split("_")[2])
    stock = await get_stock_detail(stock_id)
    
    if not stock:
        await query.edit_message_text("❌ Stock không tồn tại!", reply_markup=back_keyboard("admin_manage_stock"))
        return
    
    s_id, product_id, content, sold = stock
    status = "🔴 Đã bán" if sold else "🟢 Chưa bán"
    
    text = f"📋 CHI TIẾT STOCK #{s_id}\n\n{status}\n\n📝 Nội dung:\n{content}"
    await query.edit_message_text(text, reply_markup=admin_stock_detail_keyboard(s_id, product_id))

async def admin_edit_stock_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Bắt đầu sửa stock"""
    query = update.callback_query
    await query.answer()
    
    stock_id = int(query.data.split("_")[2])
    context.user_data['edit_stock_id'] = stock_id
    
    stock = await get_stock_detail(stock_id)
    if stock:
        await query.edit_message_text(
            f"✏️ SỬA STOCK #{stock_id}\n\n"
            f"📝 Nội dung hiện tại:\n{stock[2]}\n\n"
            f"Nhập nội dung mới:"
        )
        return EDIT_STOCK_CONTENT
    
    await query.edit_message_text("❌ Stock không tồn tại!", reply_markup=back_keyboard("admin_manage_stock"))
    return ConversationHandler.END

async def admin_edit_stock_done(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Hoàn thành sửa stock"""
    stock_id = context.user_data.get('edit_stock_id')
    if not stock_id:
        await update.message.reply_text("❌ Lỗi! Vui lòng thử lại.")
        return ConversationHandler.END
    
    new_content = update.message.text.strip()
    await update_stock_content(stock_id, new_content)
    
    stock = await get_stock_detail(stock_id)
    product_id = stock[1] if stock else None
    
    await update.message.reply_text(
        f"✅ Đã cập nhật stock #{stock_id}!",
        reply_markup=back_keyboard(f"admin_viewstock_{product_id}" if product_id else "admin_manage_stock")
    )
    return ConversationHandler.END

async def admin_delete_stock(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Xóa một stock"""
    query = update.callback_query
    await query.answer()
    
    parts = query.data.split("_")
    stock_id = int(parts[2])
    product_id = int(parts[3])
    
    await delete_stock(stock_id)
    
    # Quay lại danh sách stock
    product = await get_product(product_id)
    stocks = await get_stock_by_product(product_id)
    
    if not stocks:
        await query.edit_message_text(
            f"✅ Đã xóa stock!\n\n📦 {product['name']}\n\n❌ Không còn stock nào!",
            reply_markup=back_keyboard("admin_manage_stock")
        )
        return
    
    total = len(stocks)
    sold = sum(1 for s in stocks if s[2])
    available = total - sold
    
    text = f"✅ Đã xóa stock!\n\n📦 {product['name']}\n\n📊 Tổng: {total} | 🟢 Còn: {available} | 🔴 Đã bán: {sold}"
    await query.edit_message_text(text, reply_markup=admin_stock_list_keyboard(stocks, product_id))

# Bank settings
ADMIN_CONTACT = 25  # State for admin contact setting

async def admin_bank_settings(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    settings = await get_bank_settings()
    binance_id = await get_setting("binance_pay_id", "")
    admin_contact = await get_setting("admin_contact", "")
    
    text = f"""
🏦 CÀI ĐẶT THANH TOÁN

👤 Admin liên hệ: {('@' + admin_contact) if admin_contact else 'Chưa cài đặt'}

📌 Ngân hàng (VNĐ):
• Ngân hàng: {settings['bank_name'] or 'Chưa cài đặt'}
• Số TK: {settings['account_number'] or 'Chưa cài đặt'}
• Tên TK: {settings['account_name'] or 'Chưa cài đặt'}
• SePay Token: {'✅ Đã cài' if settings['sepay_token'] else '❌ Chưa cài'}

🔶 Binance (USDT):
• Binance ID: {binance_id or 'Chưa cài đặt'}
"""
    keyboard = [
        [InlineKeyboardButton("👤 Admin liên hệ", callback_data="set_admin_contact")],
        [InlineKeyboardButton("🔑 SePay Token", callback_data="set_sepay_token"),
         InlineKeyboardButton("🔄 Cập nhật SePay", callback_data="refresh_bank_info")],
        [InlineKeyboardButton("🔶 Binance ID", callback_data="set_binance_id")],
        [InlineKeyboardButton("🔙 Quay lại", callback_data="admin")],
    ]
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))

async def refresh_bank_info(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Cập nhật lại thông tin ngân hàng từ SePay"""
    query = update.callback_query
    await query.answer("Đang cập nhật...")
    
    import aiohttp
    
    token = await get_setting("sepay_token", "")
    if not token:
        await query.edit_message_text(
            "❌ Chưa cài đặt SePay Token!\n\nVui lòng cài đặt token trước.",
            reply_markup=back_keyboard("admin_bank_settings")
        )
        return
    
    try:
        async with aiohttp.ClientSession() as session:
            headers = {
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json"
            }
            
            async with session.get(
                "https://my.sepay.vn/userapi/bankaccounts/list",
                headers=headers
            ) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    bank_accounts = data.get('bankaccounts', [])
                    
                    if bank_accounts:
                        # Lấy tài khoản active đầu tiên
                        account = None
                        for acc in bank_accounts:
                            if acc.get('active') == '1':
                                account = acc
                                break
                        if not account:
                            account = bank_accounts[0]
                        
                        bank_name = account.get('bank_short_name', '') or account.get('bank_name', '')
                        account_number = account.get('account_number', '')
                        account_name = account.get('account_holder_name', '')
                        
                        await set_setting("bank_name", bank_name)
                        await set_setting("account_number", account_number)
                        await set_setting("account_name", account_name)
                        
                        text = f"""
✅ CẬP NHẬT THÀNH CÔNG!

🏦 Ngân hàng: {bank_name}
🔢 Số TK: {account_number}
👤 Tên TK: {account_name}
"""
                        await query.edit_message_text(text, reply_markup=back_keyboard("admin_bank_settings"))
                    else:
                        await query.edit_message_text(
                            "⚠️ Không tìm thấy tài khoản ngân hàng nào!\n\n"
                            "Vui lòng liên kết tài khoản tại: https://my.sepay.vn/bankaccount",
                            reply_markup=back_keyboard("admin_bank_settings")
                        )
                else:
                    await query.edit_message_text(
                        f"❌ Lỗi kết nối SePay! (Mã {resp.status})\n\nToken có thể đã hết hạn.",
                        reply_markup=back_keyboard("admin_bank_settings")
                    )
    except Exception as e:
        await query.edit_message_text(
            f"❌ Lỗi: {str(e)}",
            reply_markup=back_keyboard("admin_bank_settings")
        )

async def set_bank_name_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text(
        "🏦 Nhập tên ngân hàng:\n\nVí dụ: VietinBank, MBBank, Vietcombank, BIDV, Techcombank..."
    )
    return BANK_NAME

async def set_bank_name_done(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await set_setting("bank_name", update.message.text.strip())
    await update.message.reply_text("✅ Đã cập nhật tên ngân hàng!", reply_markup=back_keyboard("admin_bank_settings"))
    return ConversationHandler.END

async def set_account_number_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text("🔢 Nhập số tài khoản ngân hàng:")
    return ACCOUNT_NUMBER

async def set_account_number_done(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await set_setting("account_number", update.message.text.strip())
    await update.message.reply_text("✅ Đã cập nhật số tài khoản!", reply_markup=back_keyboard("admin_bank_settings"))
    return ConversationHandler.END

async def set_account_name_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text("👤 Nhập tên chủ tài khoản (viết HOA, không dấu):")
    return ACCOUNT_NAME

async def set_account_name_done(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await set_setting("account_name", update.message.text.strip().upper())
    await update.message.reply_text("✅ Đã cập nhật tên tài khoản!", reply_markup=back_keyboard("admin_bank_settings"))
    return ConversationHandler.END

async def set_sepay_token_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text(
        "🔑 Nhập SePay API Token:\n\n"
        "Lấy token tại: https://my.sepay.vn/companyapi\n\n"
        "⚡ Bot sẽ tự động lấy thông tin ngân hàng từ SePay!"
    )
    return SEPAY_TOKEN

async def set_sepay_token_done(update: Update, context: ContextTypes.DEFAULT_TYPE):
    import aiohttp
    
    token = update.message.text.strip()
    await update.message.reply_text("⏳ Đang kiểm tra token và lấy thông tin ngân hàng...")
    
    # Gọi API SePay để lấy thông tin tài khoản
    try:
        async with aiohttp.ClientSession() as session:
            headers = {
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json"
            }
            
            # Lấy danh sách tài khoản ngân hàng
            async with session.get(
                "https://my.sepay.vn/userapi/bankaccounts/list",
                headers=headers
            ) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    bank_accounts = data.get('bankaccounts', [])
                    
                    if bank_accounts:
                        # Lấy tài khoản đầu tiên (hoặc tài khoản active)
                        account = bank_accounts[0]
                        bank_name = account.get('bank_short_name', '') or account.get('bank_name', '')
                        account_number = account.get('account_number', '')
                        account_name = account.get('account_holder_name', '')
                        
                        # Lưu tất cả vào database
                        await set_setting("sepay_token", token)
                        await set_setting("bank_name", bank_name)
                        await set_setting("account_number", account_number)
                        await set_setting("account_name", account_name)
                        
                        text = f"""
✅ CẬP NHẬT THÀNH CÔNG!

🔑 SePay Token: Đã lưu
🏦 Ngân hàng: {bank_name}
🔢 Số TK: {account_number}
👤 Tên TK: {account_name}

⚡ Thông tin đã được tự động cập nhật từ SePay!
"""
                        await update.message.reply_text(text, reply_markup=back_keyboard("admin_bank_settings"))
                        return ConversationHandler.END
                    else:
                        await set_setting("sepay_token", token)
                        await update.message.reply_text(
                            "⚠️ Token hợp lệ nhưng chưa có tài khoản ngân hàng nào được liên kết!\n\n"
                            "Vui lòng liên kết tài khoản tại: https://my.sepay.vn/bankaccount",
                            reply_markup=back_keyboard("admin_bank_settings")
                        )
                        return ConversationHandler.END
                else:
                    await update.message.reply_text(
                        f"❌ Token không hợp lệ! (Lỗi {resp.status})\n\n"
                        "Vui lòng kiểm tra lại token tại: https://my.sepay.vn/companyapi",
                        reply_markup=back_keyboard("admin_bank_settings")
                    )
                    return ConversationHandler.END
                    
    except Exception as e:
        # Nếu lỗi, vẫn lưu token
        await set_setting("sepay_token", token)
        await update.message.reply_text(
            f"⚠️ Đã lưu token nhưng không thể lấy thông tin tự động.\n"
            f"Lỗi: {str(e)}\n\n"
            "Bạn có thể nhập thông tin ngân hàng thủ công.",
            reply_markup=back_keyboard("admin_bank_settings")
        )
        return ConversationHandler.END

async def set_binance_id_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text(
        "🔶 Nhập Binance ID (Pay ID):\n\n"
        "Lấy ID: Mở app Binance → Profile → Binance ID (dãy số 9 chữ số)"
    )
    return BINANCE_ID

async def set_binance_id_done(update: Update, context: ContextTypes.DEFAULT_TYPE):
    binance_id = update.message.text.strip()
    await set_setting("binance_pay_id", binance_id)
    await update.message.reply_text(
        f"✅ Đã cập nhật Binance ID: {binance_id}",
        reply_markup=back_keyboard("admin_bank_settings")
    )
    return ConversationHandler.END

async def set_admin_contact_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text(
        "👤 Nhập username Telegram của admin (không có @):\n\n"
        "Ví dụ: phuongdev hoặc admin_shop"
    )
    return ADMIN_CONTACT

async def set_admin_contact_done(update: Update, context: ContextTypes.DEFAULT_TYPE):
    admin_contact = update.message.text.strip().replace("@", "")
    await set_setting("admin_contact", admin_contact)
    await update.message.reply_text(
        f"✅ Đã cập nhật Admin liên hệ: @{admin_contact}",
        reply_markup=back_keyboard("admin_bank_settings")
    )
    return ConversationHandler.END


# ============ XEM CODE ĐÃ BÁN ============

async def admin_sold_codes_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Menu xem code đã bán"""
    query = update.callback_query
    await query.answer()
    
    products = await get_products()
    text = "📜 XEM CODE ĐÃ BÁN\n\nChọn sản phẩm hoặc tìm theo User ID:"
    await query.edit_message_text(text, reply_markup=admin_sold_codes_keyboard(products))

async def admin_sold_by_product(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Xem code đã bán theo sản phẩm"""
    query = update.callback_query
    await query.answer()
    
    product_id = int(query.data.split("_")[3])
    product = await get_product(product_id)
    orders = await get_sold_codes_by_product(product_id)
    
    if not orders:
        await query.edit_message_text(
            f"📦 {product['name']}\n\n❌ Chưa có đơn hàng nào!",
            reply_markup=back_keyboard("admin_sold_codes")
        )
        return
    
    text = f"📦 {product['name']}\n📜 {len(orders)} đơn hàng gần nhất:\n\n"
    
    # Tạo file để gửi nếu có nhiều đơn
    import json
    file_content = f"=== CODE ĐÃ BÁN - {product['name']} ===\n\n"
    
    for order in orders[:10]:  # Hiển thị 10 đơn gần nhất trong message
        order_id, user_id, content, price, quantity, created_at = order
        qty_text = f" x{quantity}" if quantity and quantity > 1 else ""
        text += f"#{order_id} | User: {user_id} | {price:,}đ{qty_text}\n"
        text += f"📅 {created_at[:16]}\n"
        
        # Parse content (có thể là JSON array hoặc string)
        try:
            codes = json.loads(content)
            if isinstance(codes, list):
                text += f"📝 {len(codes)} code\n\n"
            else:
                short = content[:30] + "..." if len(content) > 30 else content
                text += f"📝 {short}\n\n"
        except:
            short = content[:30] + "..." if len(content) > 30 else content
            text += f"📝 {short}\n\n"
    
    # Tạo nội dung file đầy đủ
    for order in orders:
        order_id, user_id, content, price, quantity, created_at = order
        file_content += f"--- Đơn #{order_id} ---\n"
        file_content += f"User ID: {user_id}\n"
        file_content += f"Giá: {price:,}đ\n"
        file_content += f"Thời gian: {created_at}\n"
        file_content += f"Code:\n"
        try:
            codes = json.loads(content)
            if isinstance(codes, list):
                file_content += "\n".join(codes)
            else:
                file_content += content
        except:
            file_content += content
        file_content += "\n\n"
    
    if len(orders) > 10:
        text += f"... và {len(orders) - 10} đơn khác"
    
    keyboard = [
        [InlineKeyboardButton("📤 Tải file đầy đủ", callback_data=f"admin_export_sold_{product_id}")],
        [InlineKeyboardButton("🔙 Quay lại", callback_data="admin_sold_codes")],
    ]
    
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
    
    # Lưu file content để export
    context.user_data['sold_codes_export'] = file_content
    context.user_data['sold_codes_product'] = product['name']

async def admin_export_sold_codes(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Export code đã bán ra file"""
    query = update.callback_query
    await query.answer("Đang tạo file...")
    
    file_content = context.user_data.get('sold_codes_export', '')
    product_name = context.user_data.get('sold_codes_product', 'unknown')
    
    if not file_content:
        await query.edit_message_text("❌ Không có dữ liệu!", reply_markup=back_keyboard("admin_sold_codes"))
        return
    
    filename = f"sold_codes_{product_name}.txt"
    file_buf = io.BytesIO(file_content.encode('utf-8'))
    file_buf.seek(0)
    
    await context.bot.send_document(
        chat_id=query.message.chat_id,
        document=file_buf,
        filename=filename,
        caption=f"📤 Code đã bán - {product_name}"
    )

async def admin_sold_by_user_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Bắt đầu tìm code theo User ID"""
    query = update.callback_query
    await query.answer()
    
    await query.edit_message_text(
        "🔍 TÌM CODE THEO USER\n\n"
        "Nhập User ID (số Telegram ID):\n\n"
        "Gửi /cancel để hủy"
    )
    return SEARCH_USER_ID

async def admin_sold_by_user_search(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Tìm và hiển thị code đã bán cho user"""
    import json
    
    try:
        user_id = int(update.message.text.strip())
    except ValueError:
        await update.message.reply_text("❌ User ID phải là số! Nhập lại:")
        return SEARCH_USER_ID
    
    # Kiểm tra user có tồn tại không
    user = await search_user_by_id(user_id)
    orders = await get_sold_codes_by_user(user_id)
    
    if not orders:
        await update.message.reply_text(
            f"👤 User ID: {user_id}\n"
            f"{'📛 Username: @' + user[1] if user and user[1] else ''}\n\n"
            f"❌ User này chưa mua gì!",
            reply_markup=back_keyboard("admin_sold_codes")
        )
        return ConversationHandler.END
    
    text = f"👤 User ID: {user_id}\n"
    if user and user[1]:
        text += f"📛 Username: @{user[1]}\n"
    text += f"📜 {len(orders)} đơn hàng:\n\n"
    
    file_content = f"=== CODE ĐÃ BÁN CHO USER {user_id} ===\n\n"
    
    for order in orders[:10]:
        order_id, product_name, content, price, quantity, created_at = order
        qty_text = f" x{quantity}" if quantity and quantity > 1 else ""
        text += f"#{order_id} | {product_name} | {price:,}đ{qty_text}\n"
        text += f"📅 {created_at[:16]}\n"
        
        try:
            codes = json.loads(content)
            if isinstance(codes, list):
                text += f"📝 {len(codes)} code\n\n"
            else:
                short = content[:30] + "..." if len(content) > 30 else content
                text += f"📝 {short}\n\n"
        except:
            short = content[:30] + "..." if len(content) > 30 else content
            text += f"📝 {short}\n\n"
    
    # File đầy đủ
    for order in orders:
        order_id, product_name, content, price, quantity, created_at = order
        file_content += f"--- Đơn #{order_id} - {product_name} ---\n"
        file_content += f"Giá: {price:,}đ\n"
        file_content += f"Thời gian: {created_at}\n"
        file_content += f"Code:\n"
        try:
            codes = json.loads(content)
            if isinstance(codes, list):
                file_content += "\n".join(codes)
            else:
                file_content += content
        except:
            file_content += content
        file_content += "\n\n"
    
    if len(orders) > 10:
        text += f"... và {len(orders) - 10} đơn khác"
    
    # Gửi file luôn
    filename = f"sold_codes_user_{user_id}.txt"
    file_buf = io.BytesIO(file_content.encode('utf-8'))
    file_buf.seek(0)
    
    await update.message.reply_text(text, reply_markup=back_keyboard("admin_sold_codes"))
    await context.bot.send_document(
        chat_id=update.message.chat_id,
        document=file_buf,
        filename=filename,
        caption=f"📤 Code đã bán cho User {user_id}"
    )
    
    return ConversationHandler.END


# ============ BINANCE DEPOSITS ============

async def handle_admin_binance_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler cho nút text Duyệt Binance"""
    if not is_admin(update.effective_user.id):
        return
    
    from database import get_pending_binance_deposits
    deposits = await get_pending_binance_deposits()
    
    if not deposits:
        await update.message.reply_text(
            "🔶 Không có yêu cầu nạp Binance nào đang chờ duyệt.",
            reply_markup=back_keyboard("admin")
        )
        return
    
    text = f"🔶 DUYỆT NẠP BINANCE\n\n📋 {len(deposits)} yêu cầu đang chờ:\n"
    
    from keyboards import pending_binance_deposits_keyboard
    await update.message.reply_text(text, reply_markup=pending_binance_deposits_keyboard(deposits))

async def admin_binance_deposits(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Callback handler cho menu duyệt Binance"""
    query = update.callback_query
    await query.answer()
    
    from database import get_pending_binance_deposits
    deposits = await get_pending_binance_deposits()
    
    if not deposits:
        await query.edit_message_text(
            "🔶 Không có yêu cầu nạp Binance nào đang chờ duyệt.",
            reply_markup=back_keyboard("admin")
        )
        return
    
    text = f"🔶 DUYỆT NẠP BINANCE\n\n📋 {len(deposits)} yêu cầu đang chờ:\n"
    
    from keyboards import pending_binance_deposits_keyboard
    await query.edit_message_text(text, reply_markup=pending_binance_deposits_keyboard(deposits))

async def admin_view_binance_deposit(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Xem chi tiết yêu cầu nạp Binance + screenshot"""
    query = update.callback_query
    await query.answer()
    
    deposit_id = int(query.data.split("_")[2])
    
    from database import get_binance_deposit_detail
    deposit = await get_binance_deposit_detail(deposit_id)
    
    if not deposit:
        await query.edit_message_text("❌ Không tìm thấy yêu cầu!", reply_markup=back_keyboard("admin_binance"))
        return
    
    d_id, user_id, usdt_amount, vnd_amount, code, screenshot_file_id, status, created_at = deposit
    
    text = f"""
🔶 CHI TIẾT NẠP BINANCE #{d_id}

👤 User ID: {user_id}
💵 Số tiền: {usdt_amount} USDT
💰 Quy đổi: {vnd_amount:,}đ
📝 Code: {code}
📅 Thời gian: {created_at[:19]}
"""
    
    keyboard = [
        [InlineKeyboardButton("✅ Duyệt - Cộng tiền", callback_data=f"admin_confirmbn_{d_id}")],
        [InlineKeyboardButton("❌ Từ chối", callback_data=f"admin_cancelbn_{d_id}")],
        [InlineKeyboardButton("🔙 Quay lại", callback_data="admin_binance")],
    ]
    
    # Xóa message cũ và gửi ảnh screenshot
    try:
        await query.message.delete()
        if screenshot_file_id:
            await context.bot.send_photo(
                chat_id=query.message.chat_id,
                photo=screenshot_file_id,
                caption=text,
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
        else:
            await context.bot.send_message(
                chat_id=query.message.chat_id,
                text=text + "\n⚠️ Không có screenshot!",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
    except Exception as e:
        await context.bot.send_message(
            chat_id=query.message.chat_id,
            text=text,
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

async def admin_confirm_binance_deposit(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Duyệt nạp Binance - cộng USDT cho user"""
    query = update.callback_query
    await query.answer()
    
    deposit_id = int(query.data.split("_")[2])
    
    from database import confirm_binance_deposit, get_pending_binance_deposits, get_user_language
    from locales import get_text
    result = await confirm_binance_deposit(deposit_id)
    
    if result:
        user_id, usdt_amount = result
        user_lang = await get_user_language(user_id)
        # Thông báo cho user theo ngôn ngữ của họ
        try:
            await context.bot.send_message(
                user_id,
                get_text(user_lang, "binance_success").format(amount=usdt_amount)
            )
        except:
            pass
        
        text = f"✅ Đã duyệt! Cộng {usdt_amount} USDT cho user {user_id}"
    else:
        text = "❌ Không thể duyệt!"
    
    try:
        await query.message.delete()
    except:
        pass
    
    deposits = await get_pending_binance_deposits()
    
    if not deposits:
        await context.bot.send_message(
            chat_id=query.message.chat_id,
            text=text + "\n\n🔶 Không còn yêu cầu nào.",
            reply_markup=back_keyboard("admin")
        )
    else:
        from keyboards import pending_binance_deposits_keyboard
        await context.bot.send_message(
            chat_id=query.message.chat_id,
            text=text + f"\n\n🔶 Còn {len(deposits)} yêu cầu:",
            reply_markup=pending_binance_deposits_keyboard(deposits)
        )

async def admin_cancel_binance_deposit(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Từ chối nạp Binance"""
    query = update.callback_query
    await query.answer()
    
    deposit_id = int(query.data.split("_")[2])
    
    from database import cancel_binance_deposit, get_binance_deposit_detail, get_pending_binance_deposits
    
    # Lấy thông tin trước khi hủy
    deposit = await get_binance_deposit_detail(deposit_id)
    if deposit:
        user_id = deposit[1]
        usdt_amount = deposit[2]
        
        await cancel_binance_deposit(deposit_id)
        
        # Thông báo cho user
        try:
            await context.bot.send_message(
                user_id,
                f"❌ YÊU CẦU NẠP BINANCE BỊ TỪ CHỐI!\n\n"
                f"💵 Số tiền: {usdt_amount} USDT\n\n"
                f"Lý do: Không xác nhận được giao dịch.\n"
                f"Vui lòng liên hệ admin nếu cần hỗ trợ."
            )
        except:
            pass
    
    # Xóa message cũ
    try:
        await query.message.delete()
    except:
        pass
    
    deposits = await get_pending_binance_deposits()
    
    if not deposits:
        await context.bot.send_message(
            chat_id=query.message.chat_id,
            text="❌ Đã từ chối!\n\n🔶 Không còn yêu cầu nào.",
            reply_markup=back_keyboard("admin")
        )
    else:
        from keyboards import pending_binance_deposits_keyboard
        await context.bot.send_message(
            chat_id=query.message.chat_id,
            text=f"❌ Đã từ chối!\n\n🔶 Còn {len(deposits)} yêu cầu:",
            reply_markup=pending_binance_deposits_keyboard(deposits)
        )


# ============ USDT WITHDRAWALS ============

async def handle_admin_usdt_withdraw_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler cho nút text Duyệt rút USDT"""
    if not is_admin(update.effective_user.id):
        return
    
    from database import get_pending_usdt_withdrawals
    withdrawals = await get_pending_usdt_withdrawals()
    
    if not withdrawals:
        await update.message.reply_text(
            "💸 Không có yêu cầu rút USDT nào đang chờ duyệt.",
            reply_markup=back_keyboard("admin")
        )
        return
    
    text = f"💸 DUYỆT RÚT USDT\n\n📋 {len(withdrawals)} yêu cầu đang chờ:\n"
    
    from keyboards import pending_usdt_withdrawals_keyboard
    await update.message.reply_text(text, reply_markup=pending_usdt_withdrawals_keyboard(withdrawals))

async def admin_usdt_withdrawals(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Callback handler cho menu duyệt rút USDT"""
    query = update.callback_query
    await query.answer()
    
    from database import get_pending_usdt_withdrawals
    withdrawals = await get_pending_usdt_withdrawals()
    
    if not withdrawals:
        await query.edit_message_text(
            "💸 Không có yêu cầu rút USDT nào đang chờ duyệt.",
            reply_markup=back_keyboard("admin")
        )
        return
    
    text = f"💸 DUYỆT RÚT USDT\n\n📋 {len(withdrawals)} yêu cầu đang chờ:\n"
    
    from keyboards import pending_usdt_withdrawals_keyboard
    await query.edit_message_text(text, reply_markup=pending_usdt_withdrawals_keyboard(withdrawals))

async def admin_view_usdt_withdrawal(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Xem chi tiết yêu cầu rút USDT"""
    query = update.callback_query
    await query.answer()
    
    withdrawal_id = int(query.data.split("_")[2])
    
    from database import get_usdt_withdrawal_detail
    withdrawal = await get_usdt_withdrawal_detail(withdrawal_id)
    
    if not withdrawal:
        await query.edit_message_text("❌ Không tìm thấy yêu cầu!", reply_markup=back_keyboard("admin_usdt_withdraws"))
        return
    
    w_id, user_id, usdt_amount, wallet_address, network, status, created_at = withdrawal
    
    text = f"""
💸 CHI TIẾT YÊU CẦU RÚT USDT #{w_id}

👤 User ID: {user_id}
💵 Số tiền: {usdt_amount} USDT
🔗 Ví: {wallet_address}
🌐 Network: {network}
📅 Thời gian: {created_at[:19]}

📋 Copy địa chỉ ví và chuyển USDT thủ công.
"""
    
    keyboard = [
        [InlineKeyboardButton("✅ Đã chuyển - Duyệt", callback_data=f"admin_confirmusdt_{w_id}")],
        [InlineKeyboardButton("❌ Từ chối", callback_data=f"admin_cancelusdt_{w_id}")],
        [InlineKeyboardButton("🔙 Quay lại", callback_data="admin_usdt_withdraws")],
    ]
    
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))

async def admin_confirm_usdt_withdrawal(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Duyệt rút USDT - trừ USDT của user"""
    query = update.callback_query
    await query.answer()
    
    withdrawal_id = int(query.data.split("_")[2])
    
    from database import confirm_usdt_withdrawal, get_pending_usdt_withdrawals, get_user_language
    from locales import get_text
    result = await confirm_usdt_withdrawal(withdrawal_id)
    
    if result:
        user_id, usdt_amount, wallet_address = result
        user_lang = await get_user_language(user_id)
        # Thông báo cho user
        try:
            if user_lang == 'en':
                await context.bot.send_message(
                    user_id,
                    f"✅ USDT WITHDRAWAL SUCCESSFUL!\n\n"
                    f"💵 Amount: {usdt_amount} USDT\n"
                    f"🔗 Wallet: {wallet_address}\n\n"
                    f"💸 USDT has been sent to your wallet!"
                )
            else:
                await context.bot.send_message(
                    user_id,
                    f"✅ RÚT USDT THÀNH CÔNG!\n\n"
                    f"💵 Số tiền: {usdt_amount} USDT\n"
                    f"🔗 Ví: {wallet_address}\n\n"
                    f"💸 USDT đã được chuyển vào ví của bạn!"
                )
        except:
            pass
        
        text = f"✅ Đã duyệt! Trừ {usdt_amount} USDT của user {user_id}"
    else:
        text = "❌ Không thể duyệt! User không đủ số dư USDT."
    
    withdrawals = await get_pending_usdt_withdrawals()
    
    if not withdrawals:
        await query.edit_message_text(
            text + "\n\n💸 Không còn yêu cầu nào.",
            reply_markup=back_keyboard("admin")
        )
    else:
        from keyboards import pending_usdt_withdrawals_keyboard
        await query.edit_message_text(
            text + f"\n\n💸 Còn {len(withdrawals)} yêu cầu:",
            reply_markup=pending_usdt_withdrawals_keyboard(withdrawals)
        )

async def admin_cancel_usdt_withdrawal(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Từ chối rút USDT"""
    query = update.callback_query
    await query.answer()
    
    withdrawal_id = int(query.data.split("_")[2])
    
    from database import cancel_usdt_withdrawal, get_usdt_withdrawal_detail, get_pending_usdt_withdrawals, get_user_language
    
    # Lấy thông tin trước khi hủy
    withdrawal = await get_usdt_withdrawal_detail(withdrawal_id)
    if withdrawal:
        user_id = withdrawal[1]
        usdt_amount = withdrawal[2]
        user_lang = await get_user_language(user_id)
        
        await cancel_usdt_withdrawal(withdrawal_id)
        
        # Thông báo cho user
        try:
            if user_lang == 'en':
                await context.bot.send_message(
                    user_id,
                    f"❌ USDT WITHDRAWAL REJECTED!\n\n"
                    f"💵 Amount: {usdt_amount} USDT\n\n"
                    f"Please contact admin for support."
                )
            else:
                await context.bot.send_message(
                    user_id,
                    f"❌ YÊU CẦU RÚT USDT BỊ TỪ CHỐI!\n\n"
                    f"💵 Số tiền: {usdt_amount} USDT\n\n"
                    f"Vui lòng liên hệ admin nếu cần hỗ trợ."
                )
        except:
            pass
    
    withdrawals = await get_pending_usdt_withdrawals()
    
    if not withdrawals:
        await query.edit_message_text(
            "❌ Đã từ chối!\n\n💸 Không còn yêu cầu nào.",
            reply_markup=back_keyboard("admin")
        )
    else:
        from keyboards import pending_usdt_withdrawals_keyboard
        await query.edit_message_text(
            f"❌ Đã từ chối!\n\n💸 Còn {len(withdrawals)} yêu cầu:",
            reply_markup=pending_usdt_withdrawals_keyboard(withdrawals)
        )
