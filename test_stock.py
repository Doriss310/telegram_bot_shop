import asyncio
import time
from database import init_db, add_product, add_stock_bulk, get_products, get_product

async def test_bulk_stock():
    await init_db()
    
    # Tạo sản phẩm test
    products = await get_products()
    test_product = None
    for p in products:
        if p['name'] == 'TEST_BULK':
            test_product = p
            break
    
    if not test_product:
        product_id = await add_product("TEST_BULK", 10000)
        print(f"✅ Tạo sản phẩm test ID: {product_id}")
    else:
        product_id = test_product['id']
        print(f"📦 Dùng sản phẩm có sẵn ID: {product_id}")
    
    # Test thêm 10000 stock
    num_items = 10000
    print(f"\n⏳ Đang tạo {num_items} stock items...")
    
    stock_items = [f"account{i}@test.com|password{i}" for i in range(num_items)]
    
    start = time.time()
    await add_stock_bulk(product_id, stock_items)
    elapsed = time.time() - start
    
    print(f"✅ Hoàn thành trong {elapsed:.2f}s")
    
    # Verify
    product = await get_product(product_id)
    print(f"\n📊 Kết quả:")
    print(f"   - Sản phẩm: {product['name']}")
    print(f"   - Stock hiện có: {product['stock']}")
    print(f"   - Tốc độ: {num_items/elapsed:.0f} items/s")

if __name__ == "__main__":
    asyncio.run(test_bulk_stock())
