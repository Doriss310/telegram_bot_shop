import asyncio
from database import init_db, get_product, get_available_stock, mark_stock_sold, create_order, get_balance, update_balance

async def test_buy_flow():
    await init_db()
    
    # Test với sản phẩm TEST_BULK (ID 8)
    product_id = 8
    user_id = 7346373274
    quantity = 20
    
    product = await get_product(product_id)
    if not product:
        print("❌ Sản phẩm không tồn tại")
        return
    
    print(f"📦 Sản phẩm: {product['name']}")
    print(f"💰 Giá: {product['price']:,}đ")
    print(f"📊 Stock: {product['stock']}")
    
    balance = await get_balance(user_id)
    print(f"\n👤 User balance: {balance:,}đ")
    
    # Simulate mua hàng
    purchased_items = []
    for i in range(quantity):
        stock = await get_available_stock(product_id)
        if not stock:
            print(f"⚠️ Hết stock sau {i} items")
            break
        await mark_stock_sold(stock[0])
        purchased_items.append(stock[1])
    
    print(f"\n✅ Mua được: {len(purchased_items)} items")
    
    # Test format message
    items_formatted = "\n".join([f"<code>{item}</code>" for item in purchased_items])
    print(f"📝 Độ dài message: {len(items_formatted)} ký tự")
    
    if len(items_formatted) > 3500:
        print("📎 -> Sẽ gửi FILE")
    else:
        print("💬 -> Sẽ gửi TEXT")
    
    # Hiện 3 items đầu
    print(f"\n📋 Sample items:")
    for item in purchased_items[:3]:
        print(f"   {item}")

if __name__ == "__main__":
    asyncio.run(test_buy_flow())
