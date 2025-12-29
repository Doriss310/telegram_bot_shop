import asyncio
import os
import sys
import logging
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler,
    ConversationHandler, MessageHandler, filters
)
from config import BOT_TOKEN
from database import init_db, get_setting
from handlers.start import start_command, back_to_main, handle_history_text, handle_balance
from handlers.shop import (
    show_shop, show_product, confirm_buy, show_account,
    show_history, show_deposit, process_deposit, handle_deposit_text,
    handle_shop_text, handle_withdraw_text, process_deposit_amount,
    process_withdraw_amount, process_withdraw_bank, process_withdraw_account,
    handle_buy_quantity,
    WAITING_DEPOSIT_AMOUNT, WAITING_WITHDRAW_AMOUNT, WAITING_WITHDRAW_BANK, WAITING_WITHDRAW_ACCOUNT
)
from handlers.admin import (
    admin_command, admin_callback, admin_products, admin_delete_product,
    admin_add_product_start, admin_add_product_name, admin_add_product_price,
    admin_add_stock_menu, admin_select_stock_product, admin_add_stock_content,
    admin_deposits, admin_confirm_deposit, admin_cancel_deposit,
    admin_withdrawals, admin_view_withdrawal, admin_confirm_withdrawal, admin_cancel_withdrawal,
    admin_bank_settings, refresh_bank_info, set_bank_name_start, set_bank_name_done,
    set_account_number_start, set_account_number_done,
    set_account_name_start, set_account_name_done,
    set_sepay_token_start, set_sepay_token_done,
    cancel_conversation, ADD_PRODUCT_NAME, ADD_PRODUCT_PRICE, ADD_STOCK_CONTENT,
    BANK_NAME, ACCOUNT_NUMBER, ACCOUNT_NAME, SEPAY_TOKEN, NOTIFICATION_MESSAGE,
    handle_admin_products_text, handle_admin_stock_text, handle_admin_withdrawals_text,
    handle_admin_bank_text, handle_exit_admin, notification_command, notification_send
)
from sepay_checker import run_checker, init_checker_db

# Setup logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO,
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('bot.log', encoding='utf-8')
    ]
)
logger = logging.getLogger(__name__)

# Disable noisy loggers
logging.getLogger('httpx').setLevel(logging.WARNING)
logging.getLogger('telegram').setLevel(logging.WARNING)

async def post_init(application):
    pass  # Database already initialized in main()

def setup_bot():
    app = (
        Application.builder()
        .token(BOT_TOKEN)
        .post_init(post_init)
        .connect_timeout(30)
        .read_timeout(30)
        .write_timeout(30)
        .build()
    )
    
    # Add product conversation
    add_product_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(admin_add_product_start, pattern="^admin_add_product$")],
        states={
            ADD_PRODUCT_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, admin_add_product_name)],
            ADD_PRODUCT_PRICE: [MessageHandler(filters.TEXT & ~filters.COMMAND, admin_add_product_price)],
        },
        fallbacks=[CommandHandler("cancel", cancel_conversation)],
    )
    
    # Add stock conversation
    add_stock_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(admin_select_stock_product, pattern="^admin_stock_\\d+$")],
        states={
            ADD_STOCK_CONTENT: [MessageHandler(filters.TEXT & ~filters.COMMAND, admin_add_stock_content)],
        },
        fallbacks=[CommandHandler("cancel", cancel_conversation)],
    )
    
    # Deposit conversation
    deposit_conv = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex("^➕ Nạp tiền$"), handle_deposit_text)],
        states={
            WAITING_DEPOSIT_AMOUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, process_deposit_amount)],
        },
        fallbacks=[CommandHandler("cancel", cancel_conversation)],
    )
    
    # Withdraw conversation
    withdraw_conv = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex("^💸 Rút tiền$"), handle_withdraw_text)],
        states={
            WAITING_WITHDRAW_AMOUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, process_withdraw_amount)],
            WAITING_WITHDRAW_BANK: [MessageHandler(filters.TEXT & ~filters.COMMAND, process_withdraw_bank)],
            WAITING_WITHDRAW_ACCOUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, process_withdraw_account)],
        },
        fallbacks=[CommandHandler("cancel", cancel_conversation)],
    )
    
    # Bank settings conversations
    bank_name_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(set_bank_name_start, pattern="^set_bank_name$")],
        states={BANK_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, set_bank_name_done)]},
        fallbacks=[CommandHandler("cancel", cancel_conversation)],
    )
    account_number_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(set_account_number_start, pattern="^set_account_number$")],
        states={ACCOUNT_NUMBER: [MessageHandler(filters.TEXT & ~filters.COMMAND, set_account_number_done)]},
        fallbacks=[CommandHandler("cancel", cancel_conversation)],
    )
    account_name_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(set_account_name_start, pattern="^set_account_name$")],
        states={ACCOUNT_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, set_account_name_done)]},
        fallbacks=[CommandHandler("cancel", cancel_conversation)],
    )
    sepay_token_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(set_sepay_token_start, pattern="^set_sepay_token$")],
        states={SEPAY_TOKEN: [MessageHandler(filters.TEXT & ~filters.COMMAND, set_sepay_token_done)]},
        fallbacks=[CommandHandler("cancel", cancel_conversation)],
    )
    
    # Commands
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("admin", admin_command))
    
    # Notification conversation
    notification_conv = ConversationHandler(
        entry_points=[CommandHandler("notification", notification_command)],
        states={
            NOTIFICATION_MESSAGE: [MessageHandler(filters.TEXT & ~filters.COMMAND, notification_send)],
        },
        fallbacks=[CommandHandler("cancel", cancel_conversation)],
    )
    app.add_handler(notification_conv)
    
    # Conversations
    app.add_handler(add_product_conv)
    app.add_handler(add_stock_conv)
    app.add_handler(deposit_conv)
    app.add_handler(withdraw_conv)
    app.add_handler(bank_name_conv)
    app.add_handler(account_number_conv)
    app.add_handler(account_name_conv)
    app.add_handler(sepay_token_conv)
    
    # Reply keyboard handlers
    app.add_handler(MessageHandler(filters.Regex("^📜 Lịch sử$"), handle_history_text))
    app.add_handler(MessageHandler(filters.Regex("^💰 Số dư$"), handle_balance))
    app.add_handler(MessageHandler(filters.Regex("^🛒 Danh mục$"), handle_shop_text))
    
    # Handler nhập số lượng mua (chỉ số)
    app.add_handler(MessageHandler(filters.Regex("^\\d+$"), handle_buy_quantity))
    
    # Admin reply keyboard handlers
    app.add_handler(MessageHandler(filters.Regex("^📦 Quản lý SP$"), handle_admin_products_text))
    app.add_handler(MessageHandler(filters.Regex("^📥 Thêm stock$"), handle_admin_stock_text))
    app.add_handler(MessageHandler(filters.Regex("^💳 Duyệt rút tiền$"), handle_admin_withdrawals_text))
    app.add_handler(MessageHandler(filters.Regex("^🏦 Cài đặt NH$"), handle_admin_bank_text))
    app.add_handler(MessageHandler(filters.Regex("^❌ Thoát Admin$"), handle_exit_admin))
    
    # User callbacks
    app.add_handler(CallbackQueryHandler(back_to_main, pattern="^back_main$"))
    app.add_handler(CallbackQueryHandler(show_shop, pattern="^shop$"))
    app.add_handler(CallbackQueryHandler(show_product, pattern="^buy_\\d+$"))
    app.add_handler(CallbackQueryHandler(show_account, pattern="^account$"))
    app.add_handler(CallbackQueryHandler(show_history, pattern="^history$"))
    app.add_handler(CallbackQueryHandler(show_deposit, pattern="^deposit$"))
    app.add_handler(CallbackQueryHandler(process_deposit, pattern="^deposit_\\d+$"))
    
    # Admin callbacks
    app.add_handler(CallbackQueryHandler(admin_callback, pattern="^admin$"))
    app.add_handler(CallbackQueryHandler(admin_products, pattern="^admin_products$"))
    app.add_handler(CallbackQueryHandler(admin_delete_product, pattern="^admin_del_\\d+$"))
    app.add_handler(CallbackQueryHandler(admin_add_stock_menu, pattern="^admin_add_stock$"))
    app.add_handler(CallbackQueryHandler(admin_deposits, pattern="^admin_deposits$"))
    app.add_handler(CallbackQueryHandler(admin_confirm_deposit, pattern="^admin_confirm_\\d+$"))
    app.add_handler(CallbackQueryHandler(admin_cancel_deposit, pattern="^admin_cancel_\\d+$"))
    app.add_handler(CallbackQueryHandler(admin_withdrawals, pattern="^admin_withdraws$"))
    app.add_handler(CallbackQueryHandler(admin_view_withdrawal, pattern="^admin_view_\\d+$"))
    app.add_handler(CallbackQueryHandler(admin_confirm_withdrawal, pattern="^admin_confirm_withdraw_\\d+$"))
    app.add_handler(CallbackQueryHandler(admin_cancel_withdrawal, pattern="^admin_cancel_withdraw_\\d+$"))
    app.add_handler(CallbackQueryHandler(admin_bank_settings, pattern="^admin_bank_settings$"))
    app.add_handler(CallbackQueryHandler(refresh_bank_info, pattern="^refresh_bank_info$"))
    
    return app

async def main():
    # Init database FIRST
    os.makedirs("data", exist_ok=True)
    logger.info("📁 Data directory ready")
    await init_db()
    logger.info("✅ Main database initialized!")
    await init_checker_db()
    logger.info("✅ Checker database initialized!")
    
    bot_app = setup_bot()
    
    logger.info("🤖 Bot is starting...")
    await bot_app.initialize()
    await bot_app.start()
    await bot_app.updater.start_polling(drop_pending_updates=True)
    
    # Start SePay checker
    asyncio.create_task(run_checker(bot_app, interval=30))
    logger.info("🔄 SePay auto-checker enabled (30s interval)")
    
    # Keep running
    stop_event = asyncio.Event()
    
    def signal_handler():
        stop_event.set()
    
    try:
        import signal
        for sig in (signal.SIGINT, signal.SIGTERM):
            asyncio.get_event_loop().add_signal_handler(sig, signal_handler)
    except (NotImplementedError, AttributeError):
        pass  # Windows doesn't support signals
    
    try:
        await stop_event.wait()
    except KeyboardInterrupt:
        pass
    finally:
        logger.info("🛑 Shutting down...")
        await bot_app.updater.stop()
        await bot_app.stop()
        await bot_app.shutdown()
        logger.info("👋 Bot stopped!")

if __name__ == "__main__":
    # Use uvloop on Linux for better performance
    try:
        import uvloop
        asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())
        logger.info("Using uvloop")
    except ImportError:
        pass
    
    asyncio.run(main())
