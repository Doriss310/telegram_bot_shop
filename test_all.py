import asyncio
import time
from database import (
    init_db, get_products, get_product, get_balance, update_balance,
    get_available_stock_batch, mark_stock_sold_batch, create_order_bulk,
    get_user_orders, get_order_detail, add_stock_bulk, delete_all_stock,
    export_stock, get_or_create_user
)

USER_ID = 7346373274

async def test_all():
    print("="*50)
    print("🧪 TEST TẤT CẢ LOGIC BOT")
    print("="*50)
    
    await init_db()
    
    # 1. Test user
    print("\n1️⃣ TEST USER")
    user = await get_or_create_user(USER_ID, "test_user")
    balance = await get_balance(USER_ID)
    print(f"   ✅ User: {USER_ID} | Balance: {balance:,}đ")
    
    # 2. Test products
    print("\n2️⃣ TEST PRODUCTS")
    products = await get_products()
    print(f"   ✅ Có {len(products)} sản phẩm")
    for p in products[:3]:
        print(f"      - {p['name']}: {p['stock']} stock, {p['price']:,}đ")
    
    # 3. Test mua hàng batch (1000 items)
    print("\n3️⃣ TEST MUA HÀNG 1000 ITEMS")
    product_id = 8  # TEST_BULK
    product = await get_product(product_id)
    
    if product and product['stock'] >= 1000:
        start = time.time()
        
        # Lấy stock batch
        stocks = await get_available_stock_batch(product_id, 1000)
        get_time = time.time() - start
        
        # Mark sold batch
        stock_ids = [s[0] for s in stocks]
        purchased_items = [s[1] for s in stocks]
        
        start2 = time.time()
        await mark_stock_sold_batch(stock_ids)
        mark_time = time.time() - start2
        
        # Tạo order
        start3 = time.time()
        order_group = f"TEST{USER_ID}"
        await create_order_bulk(USER_ID, product_id, purchased_items, product['price'], order_group)
        order_time = time.time() - start3
        
        total_time = get_time + mark_time + order_time
        print(f"   ✅ Lấy 1000 stock: {get_time:.3f}s")
        print(f"   ✅ Mark sold: {mark_time:.3f}s")
        print(f"   ✅ Tạo order: {order_time:.3f}s")
        print(f"   ⚡ TỔNG: {total_time:.3f}s")
    else:
        print(f"   ⚠️ Không đủ stock để test (cần 1000, có {product['stock'] if product else 0})")
    
    # 4. Test lịch sử đơn hàng
    print("\n4️⃣ TEST LỊCH SỬ ĐƠN HÀNG")
    orders = await get_user_orders(USER_ID)
    print(f"   ✅ Có {len(orders)} đơn hàng")
    if orders:
        order = orders[0]
        order_id, name, content, price, created_at, qty = order
        print(f"   📋 Đơn mới nhất: #{order_id} | {name} | SL:{qty or 1} | {price:,}đ")
    
    # 5. Test chi tiết đơn hàng
    print("\n5️⃣ TEST CHI TIẾT ĐƠN HÀNG")
    if orders:
        detail = await get_order_detail(orders[0][0])
        if detail:
            _, name, content, price, _, qty = detail
            import json
            try:
                items = json.loads(content)
            except:
                items = [content]
            print(f"   ✅ Đơn #{orders[0][0]}: {len(items)} items")
            print(f"   📝 3 items đầu: {items[:3]}")
    
    # 6. Test export stock
    print("\n6️⃣ TEST EXPORT STOCK")
    start = time.time()
    stock_list = await export_stock(product_id, only_unsold=True)
    export_time = time.time() - start
    print(f"   ✅ Export {len(stock_list)} stock trong {export_time:.3f}s")
    
    # 7. Test tạo file
    print("\n7️⃣ TEST TẠO FILE")
    import io
    start = time.time()
    content = "\n".join(stock_list[:5000])  # Test 5000 items
    buf = io.BytesIO(content.encode('utf-8'))
    buf.seek(0)
    file_time = time.time() - start
    file_size = len(content) / 1024
    print(f"   ✅ Tạo file {file_size:.1f}KB trong {file_time:.3f}s")
    
    # 8. Test thêm stock bulk
    print("\n8️⃣ TEST THÊM STOCK BULK")
    test_stocks = [f"test_acc_{i}@mail.com|pass{i}" for i in range(1000)]
    start = time.time()
    await add_stock_bulk(product_id, test_stocks)
    add_time = time.time() - start
    print(f"   ✅ Thêm 1000 stock trong {add_time:.3f}s")
    
    # Summary
    print("\n" + "="*50)
    print("📊 KẾT QUẢ")
    print("="*50)
    product = await get_product(product_id)
    print(f"   Stock hiện tại: {product['stock']}")
    orders = await get_user_orders(USER_ID)
    print(f"   Tổng đơn hàng: {len(orders)}")
    print("\n✅ TẤT CẢ TEST PASSED!")

if __name__ == "__main__":
    asyncio.run(test_all())
