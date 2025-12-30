import asyncio
import aiosqlite

async def migrate():
    async with aiosqlite.connect("data/shop.db") as db:
        # Thêm cột quantity nếu chưa có
        try:
            await db.execute("ALTER TABLE orders ADD COLUMN quantity INTEGER DEFAULT 1")
            print("✅ Added column: quantity")
        except Exception as e:
            print(f"⚠️ quantity: {e}")
        
        # Thêm cột order_group nếu chưa có
        try:
            await db.execute("ALTER TABLE orders ADD COLUMN order_group TEXT")
            print("✅ Added column: order_group")
        except Exception as e:
            print(f"⚠️ order_group: {e}")
        
        await db.commit()
        print("✅ Migration done!")

asyncio.run(migrate())
