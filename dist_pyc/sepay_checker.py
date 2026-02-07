"""
Tự động check giao dịch từ SePay API (không cần webhook/domain)
"""
import asyncio
import aiohttp
import aiosqlite

DB_PATH = "data/shop.db"

async def get_sepay_token():
    """Lấy SePay token từ database"""
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("SELECT value FROM settings WHERE key = 'sepay_token'")
        row = await cursor.fetchone()
        return row[0] if row else ""

async def get_recent_transactions():
    """Lấy giao dịch gần đây từ SePay"""
    SEPAY_API_TOKEN = await get_sepay_token()
    if not SEPAY_API_TOKEN:
        return []
    
    url = "https://my.sepay.vn/userapi/transactions/list"
    headers = {
        "Authorization": f"Bearer {SEPAY_API_TOKEN}",
        "Content-Type": "application/json"
    }
    
    async with aiohttp.ClientSession() as session:
        try:
            async with session.get(url, headers=headers) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    return data.get('transactions', [])
        except Exception as e:
            print(f"Error fetching transactions: {e}")
    return []

async def process_transactions(bot_app=None):
    """Xử lý giao dịch và cộng tiền tự động"""
    transactions = await get_recent_transactions()
    
    async with aiosqlite.connect(DB_PATH) as db:
        # Lấy pending deposits
        cursor = await db.execute(
            "SELECT id, user_id, amount, code FROM deposits WHERE status = 'pending'"
        )
        pending_deposits = await cursor.fetchall()
        
        for tx in transactions:
            # Lấy thông tin giao dịch (API trả về amount_in cho tiền vào)
            amount_in = tx.get('amount_in', '0')
            if float(amount_in) <= 0:
                continue
                
            content = tx.get('transaction_content', '').upper().strip()
            amount = int(float(amount_in))
            tx_id = str(tx.get('id'))
            
            # Kiểm tra đã xử lý chưa
            cursor = await db.execute(
                "SELECT 1 FROM processed_transactions WHERE tx_id = ?", (tx_id,)
            )
            if await cursor.fetchone():
                continue
            
            # Tìm deposit khớp
            for deposit in pending_deposits:
                deposit_id, user_id, expected_amount, code = deposit
                
                if code.upper() in content:
                    # Cộng tiền
                    await db.execute(
                        "UPDATE deposits SET status = 'confirmed' WHERE id = ?",
                        (deposit_id,)
                    )
                    await db.execute(
                        "UPDATE users SET balance = balance + ? WHERE user_id = ?",
                        (amount, user_id)
                    )
                    # Đánh dấu đã xử lý
                    await db.execute(
                        "INSERT INTO processed_transactions (tx_id) VALUES (?)",
                        (tx_id,)
                    )
                    await db.commit()
                    
                    print(f"✅ Confirmed: User {user_id}, Amount {amount:,}đ")
                    
                    # Thông báo user
                    if bot_app:
                        try:
                            # Lấy số dư mới
                            cursor = await db.execute(
                                "SELECT balance FROM users WHERE user_id = ?", (user_id,)
                            )
                            new_balance = (await cursor.fetchone())[0]
                            
                            await bot_app.bot.send_message(
                                user_id,
                                f"✅ NẠP TIỀN THÀNH CÔNG!\n\n"
                                f"💰 Số tiền: {amount:,}đ\n"
                                f"💳 Số dư hiện tại: {new_balance:,}đ"
                            )
                        except:
                            pass
                    break

async def init_checker_db():
    """Tạo bảng lưu giao dịch đã xử lý"""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS processed_transactions (
                tx_id TEXT PRIMARY KEY,
                processed_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)
        await db.commit()

async def run_checker(bot_app=None, interval=30):
    """Chạy checker định kỳ"""
    await init_checker_db()
    print(f"🔄 SePay checker started (interval: {interval}s)")
    
    while True:
        try:
            await process_transactions(bot_app)
        except Exception as e:
            print(f"Checker error: {e}")
        await asyncio.sleep(interval)

if __name__ == "__main__":
    asyncio.run(run_checker())
