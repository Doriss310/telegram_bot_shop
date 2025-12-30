import asyncio
import time
from database import init_db, get_available_stock_batch, mark_stock_sold_batch, get_product

async def test_speed():
    await init_db()
    
    product_id = 8
    quantity = 1000
    
    product = await get_product(product_id)
    print(f"📦 Sản phẩm: {product['name']}")
    print(f"📊 Stock còn: {product['stock']}")
    print(f"🛒 Test mua: {quantity} items")
    print()
    
    # Test batch
    start = time.time()
    stocks = await get_available_stock_batch(product_id, quantity)
    get_time = time.time() - start
    
    print(f"✅ Lấy {len(stocks)} stocks trong {get_time:.3f}s")
    
    # Test mark sold batch
    stock_ids = [s[0] for s in stocks]
    start = time.time()
    await mark_stock_sold_batch(stock_ids)
    mark_time = time.time() - start
    
    print(f"✅ Mark sold {len(stock_ids)} items trong {mark_time:.3f}s")
    print(f"⚡ Tổng: {get_time + mark_time:.3f}s cho {quantity} items")

asyncio.run(test_speed())
