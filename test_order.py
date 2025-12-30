import asyncio
from database import init_db, get_product, get_available_stock, mark_stock_sold, create_order_bulk, get_user_orders
from datetime import datetime

async def test_buy():
    await init_db()
    
    product_id = 8
    user_id = 7346373274
    quantity = 5
    
    product = await get_product(product_id)
    
    # Mua 5 items
    purchased_items = []
    for _ in range(quantity):
        stock = await get_available_stock(product_id)
        if stock:
            await mark_stock_sold(stock[0])
            purchased_items.append(stock[1])
    
    # Tạo 1 đơn hàng
    order_group = f"ORD{user_id}{datetime.now().strftime('%Y%m%d%H%M%S')}"
    await create_order_bulk(user_id, product_id, purchased_items, product['price'], order_group)
    
    print(f"✅ Đã tạo đơn hàng {len(purchased_items)} items")
    
    # Xem lịch sử
    orders = await get_user_orders(user_id)
    print()
    print("📜 LỊCH SỬ (5 đơn gần nhất):")
    for order in orders[:5]:
        order_id, product_name, content, price, created_at, qty = order
        qty = qty or 1
        date_str = created_at[:10] if created_at else ""
        print(f"🛒 #{order_id} | {product_name} | SL: {qty} | {price:,}đ")

asyncio.run(test_buy())
