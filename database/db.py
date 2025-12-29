import aiosqlite
import json
from datetime import datetime

DB_PATH = "data/shop.db"

async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                balance INTEGER DEFAULT 0,
                created_at TEXT
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS products (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                price INTEGER NOT NULL,
                description TEXT
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS stock (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                product_id INTEGER,
                content TEXT NOT NULL,
                sold INTEGER DEFAULT 0,
                FOREIGN KEY (product_id) REFERENCES products(id)
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS orders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                product_id INTEGER,
                content TEXT,
                price INTEGER,
                created_at TEXT
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS deposits (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                amount INTEGER,
                code TEXT,
                status TEXT DEFAULT 'pending',
                created_at TEXT
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS withdrawals (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                amount INTEGER,
                momo_phone TEXT,
                status TEXT DEFAULT 'pending',
                created_at TEXT
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT
            )
        """)
        await db.commit()

# User functions
async def get_or_create_user(user_id: int, username: str = None):
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
        user = await cursor.fetchone()
        if not user:
            await db.execute(
                "INSERT INTO users (user_id, username, created_at) VALUES (?, ?, ?)",
                (user_id, username, datetime.now().isoformat())
            )
            await db.commit()
            return {"user_id": user_id, "username": username, "balance": 0}
        return {"user_id": user[0], "username": user[1], "balance": user[2]}

async def get_balance(user_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("SELECT balance FROM users WHERE user_id = ?", (user_id,))
        row = await cursor.fetchone()
        return row[0] if row else 0

async def update_balance(user_id: int, amount: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (amount, user_id))
        await db.commit()


# Product functions
async def get_products():
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("SELECT * FROM products")
        rows = await cursor.fetchall()
        products = []
        for row in rows:
            stock_cursor = await db.execute(
                "SELECT COUNT(*) FROM stock WHERE product_id = ? AND sold = 0", (row[0],)
            )
            stock_count = (await stock_cursor.fetchone())[0]
            products.append({
                "id": row[0], "name": row[1], "price": row[2],
                "description": row[3], "stock": stock_count
            })
        return products

async def get_product(product_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("SELECT * FROM products WHERE id = ?", (product_id,))
        row = await cursor.fetchone()
        if row:
            stock_cursor = await db.execute(
                "SELECT COUNT(*) FROM stock WHERE product_id = ? AND sold = 0", (row[0],)
            )
            stock_count = (await stock_cursor.fetchone())[0]
            return {"id": row[0], "name": row[1], "price": row[2], "description": row[3], "stock": stock_count}
        return None

async def add_product(name: str, price: int, description: str = ""):
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "INSERT INTO products (name, price, description) VALUES (?, ?, ?)",
            (name, price, description)
        )
        await db.commit()
        return cursor.lastrowid

async def delete_product(product_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM stock WHERE product_id = ?", (product_id,))
        await db.execute("DELETE FROM products WHERE id = ?", (product_id,))
        await db.commit()

async def add_stock(product_id: int, content: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("INSERT INTO stock (product_id, content) VALUES (?, ?)", (product_id, content))
        await db.commit()

async def add_stock_bulk(product_id: int, contents: list):
    """Thêm nhiều stock cùng lúc - tối ưu cho vài trăm items"""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.executemany(
            "INSERT INTO stock (product_id, content) VALUES (?, ?)",
            [(product_id, content) for content in contents]
        )
        await db.commit()

async def get_available_stock(product_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "SELECT id, content FROM stock WHERE product_id = ? AND sold = 0 LIMIT 1", (product_id,)
        )
        return await cursor.fetchone()

async def mark_stock_sold(stock_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE stock SET sold = 1 WHERE id = ?", (stock_id,))
        await db.commit()

# Order functions
async def create_order(user_id: int, product_id: int, content: str, price: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO orders (user_id, product_id, content, price, created_at) VALUES (?, ?, ?, ?, ?)",
            (user_id, product_id, content, price, datetime.now().isoformat())
        )
        await db.commit()

async def get_user_orders(user_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            """SELECT o.id, p.name, o.content, o.price, o.created_at 
               FROM orders o JOIN products p ON o.product_id = p.id 
               WHERE o.user_id = ? ORDER BY o.created_at DESC LIMIT 10""",
            (user_id,)
        )
        return await cursor.fetchall()

# Deposit functions
async def create_deposit(user_id: int, amount: int, code: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO deposits (user_id, amount, code, created_at) VALUES (?, ?, ?, ?)",
            (user_id, amount, code, datetime.now().isoformat())
        )
        await db.commit()

async def get_pending_deposits():
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "SELECT id, user_id, amount, code, created_at FROM deposits WHERE status = 'pending'"
        )
        return await cursor.fetchall()

async def confirm_deposit(deposit_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("SELECT user_id, amount FROM deposits WHERE id = ?", (deposit_id,))
        row = await cursor.fetchone()
        if row:
            await db.execute("UPDATE deposits SET status = 'confirmed' WHERE id = ?", (deposit_id,))
            await db.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (row[1], row[0]))
            await db.commit()
            return row
        return None

async def cancel_deposit(deposit_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE deposits SET status = 'cancelled' WHERE id = ?", (deposit_id,))
        await db.commit()

# Stats
async def get_stats():
    async with aiosqlite.connect(DB_PATH) as db:
        users = (await (await db.execute("SELECT COUNT(*) FROM users")).fetchone())[0]
        orders = (await (await db.execute("SELECT COUNT(*) FROM orders")).fetchone())[0]
        revenue = (await (await db.execute("SELECT COALESCE(SUM(price), 0) FROM orders")).fetchone())[0]
        return {"users": users, "orders": orders, "revenue": revenue}

# Withdrawal functions
async def create_withdrawal(user_id: int, amount: int, momo_phone: str):
    async with aiosqlite.connect(DB_PATH) as db:
        # Chỉ tạo yêu cầu, KHÔNG trừ tiền - sẽ trừ khi admin duyệt
        await db.execute(
            "INSERT INTO withdrawals (user_id, amount, momo_phone, created_at) VALUES (?, ?, ?, ?)",
            (user_id, amount, momo_phone, datetime.now().isoformat())
        )
        await db.commit()

async def get_pending_withdrawals():
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "SELECT id, user_id, amount, momo_phone, created_at FROM withdrawals WHERE status = 'pending'"
        )
        return await cursor.fetchall()

async def get_withdrawal_detail(withdrawal_id: int):
    """Lấy chi tiết một yêu cầu rút tiền"""
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "SELECT id, user_id, amount, momo_phone, status, created_at FROM withdrawals WHERE id = ?",
            (withdrawal_id,)
        )
        return await cursor.fetchone()

async def get_user_pending_withdrawal(user_id: int):
    """Kiểm tra user có yêu cầu rút tiền đang pending không, trả về số tiền pending"""
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "SELECT SUM(amount) FROM withdrawals WHERE user_id = ? AND status = 'pending'",
            (user_id,)
        )
        row = await cursor.fetchone()
        return row[0] if row and row[0] else 0

async def confirm_withdrawal(withdrawal_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("SELECT user_id, amount, momo_phone FROM withdrawals WHERE id = ?", (withdrawal_id,))
        row = await cursor.fetchone()
        if row:
            user_id, amount, bank_info = row
            
            # Check số dư trước khi trừ
            cursor = await db.execute("SELECT balance FROM users WHERE user_id = ?", (user_id,))
            balance_row = await cursor.fetchone()
            if not balance_row or balance_row[0] < amount:
                return None  # Không đủ tiền
            
            # Trừ tiền khi admin duyệt
            await db.execute("UPDATE users SET balance = balance - ? WHERE user_id = ? AND balance >= ?", (amount, user_id, amount))
            await db.execute("UPDATE withdrawals SET status = 'confirmed' WHERE id = ?", (withdrawal_id,))
            await db.commit()
            return row  # (user_id, amount, bank_info)
        return None

async def cancel_withdrawal(withdrawal_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("SELECT user_id, amount FROM withdrawals WHERE id = ?", (withdrawal_id,))
        row = await cursor.fetchone()
        if row:
            # Không cần hoàn tiền vì chưa trừ
            await db.execute("UPDATE withdrawals SET status = 'cancelled' WHERE id = ?", (withdrawal_id,))
            await db.commit()
            return row
        return None

# Settings functions
async def get_setting(key: str, default: str = ""):
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("SELECT value FROM settings WHERE key = ?", (key,))
        row = await cursor.fetchone()
        return row[0] if row else default

async def set_setting(key: str, value: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)",
            (key, value)
        )
        await db.commit()

async def get_bank_settings():
    return {
        "bank_name": await get_setting("bank_name", ""),
        "account_number": await get_setting("account_number", ""),
        "account_name": await get_setting("account_name", ""),
        "sepay_token": await get_setting("sepay_token", ""),
    }
