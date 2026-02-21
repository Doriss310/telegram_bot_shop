"""
Tự động check giao dịch từ SePay API (không cần webhook/domain)
"""
import asyncio
import aiohttp
import os
import io
import logging
from datetime import datetime
from config import SEPAY_API_TOKEN
from helpers.sepay_state import has_latest_vietqr_message, mark_bot_message
from helpers.formatting import format_stock_items

USE_SUPABASE = os.getenv("USE_SUPABASE", "true").lower() in ("1", "true", "yes") and os.getenv("SUPABASE_URL")
SEPAY_DEBUG = os.getenv("SEPAY_DEBUG", "").lower() in ("1", "true", "yes")
SEPAY_LIMIT = os.getenv("SEPAY_LIMIT", "").strip()
SEPAY_FROM_DATE = os.getenv("SEPAY_FROM_DATE", "").strip()
SEPAY_TO_DATE = os.getenv("SEPAY_TO_DATE", "").strip()


def _env_positive_int(name: str, default: int) -> int:
    raw = os.getenv(name, str(default))
    try:
        return max(1, int(str(raw).strip()))
    except (TypeError, ValueError):
        return default


DIRECT_ORDER_PENDING_EXPIRE_MINUTES = _env_positive_int("DIRECT_ORDER_PENDING_EXPIRE_MINUTES", 10)
DIRECT_ORDER_PENDING_EXPIRE_SECONDS = DIRECT_ORDER_PENDING_EXPIRE_MINUTES * 60
logger = logging.getLogger(__name__)

if USE_SUPABASE:
    from database import (
        get_setting,
        get_pending_deposits,
        update_balance,
        get_balance,
        is_processed_transaction,
        mark_processed_transaction,
        set_deposit_status,
        get_pending_direct_orders,
        set_direct_order_status,
        get_available_stock_batch,
        mark_stock_sold_batch,
        create_order_bulk,
        create_website_order_bulk,
        get_product,
        get_pending_website_direct_orders,
        set_website_direct_order_status,
    )
else:
    import aiosqlite

DB_PATH = "data/shop.db"
_SEPAY_TOKEN_WARNED = False
_SEPAY_TOKEN_OK = False


def make_file(items: list, header: str = "") -> io.BytesIO:
    if header:
        content = header + "\n" + "=" * 40 + "\n\n" + "\n\n".join(items)
    else:
        content = "\n\n".join(items)
    buf = io.BytesIO(content.encode("utf-8"))
    buf.seek(0)
    return buf

def format_description_block(description: str | None, label: str = "📝 Mô tả") -> str:
    if not description:
        return ""
    cleaned = str(description).strip()
    if not cleaned:
        return ""
    return f"{label}:\n{cleaned}\n\n"

async def get_sepay_token():
    """Lấy SePay token từ database"""
    if USE_SUPABASE:
        token = await get_setting("sepay_token", "")
        return token or SEPAY_API_TOKEN
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("SELECT value FROM settings WHERE key = 'sepay_token'")
        row = await cursor.fetchone()
        return (row[0] if row else "") or SEPAY_API_TOKEN

async def get_recent_transactions():
    """Lấy giao dịch gần đây từ SePay"""
    SEPAY_API_TOKEN = await get_sepay_token()
    if not SEPAY_API_TOKEN:
        global _SEPAY_TOKEN_WARNED
        if not _SEPAY_TOKEN_WARNED:
            logger.warning("SePay token missing. Set settings.sepay_token or SEPAY_API_TOKEN in .env.")
            _SEPAY_TOKEN_WARNED = True
        return []
    global _SEPAY_TOKEN_OK
    if not _SEPAY_TOKEN_OK:
        logger.info("✅ SePay token loaded.")
        _SEPAY_TOKEN_OK = True
    
    url = "https://my.sepay.vn/userapi/transactions/list"
    headers = {
        "Authorization": f"Bearer {SEPAY_API_TOKEN}",
        "Content-Type": "application/json"
    }
    
    params = {}
    if SEPAY_LIMIT:
        params["limit"] = SEPAY_LIMIT
    if SEPAY_FROM_DATE:
        params["from_date"] = SEPAY_FROM_DATE
    if SEPAY_TO_DATE:
        params["to_date"] = SEPAY_TO_DATE

    async with aiohttp.ClientSession() as session:
        try:
            async with session.get(url, headers=headers, params=params or None) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    transactions = data.get('transactions', []) or data.get('data', []) or []
                    if SEPAY_DEBUG:
                        logger.info("SePay payload keys: %s", list(data.keys()))
                        logger.info("SePay transactions count: %s", len(transactions))
                        logger.info("SePay status: %s | error: %s | messages: %s", data.get("status"), data.get("error"), data.get("messages"))
                    if data.get("status") is False or data.get("error"):
                        logger.warning("SePay API returned error: %s | messages: %s", data.get("error"), data.get("messages"))
                    return transactions
                body = await resp.text()
                logger.warning("SePay API error %s: %s", resp.status, body[:200])
        except Exception as e:
            logger.exception("Error fetching SePay transactions: %s", e)
    return []

def _normalize_content(value: str) -> str:
    return "".join(str(value).upper().split())

def _pick_content(tx: dict) -> str:
    for key in ("transaction_content", "content", "description", "note", "memo"):
        val = tx.get(key)
        if val:
            return str(val)
    return ""

def _pick_amount(tx: dict) -> float:
    for key in ("amount_in", "amount", "amount_in_vnd"):
        if tx.get(key) is not None:
            raw = str(tx.get(key)).replace(",", "").strip()
            try:
                return float(raw)
            except ValueError:
                continue
    return 0.0

def _pick_tx_id(tx: dict) -> str:
    for key in ("id", "transaction_id", "ref_id", "reference", "transaction_ref"):
        val = tx.get(key)
        if val is not None:
            return str(val)
    return ""


def _parse_created_at(value: str | None):
    if not value:
        return None
    text = str(value).strip()
    if not text:
        return None
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        return datetime.fromisoformat(text)
    except ValueError:
        return None


def _is_direct_order_expired(created_at: str | None) -> bool:
    parsed = _parse_created_at(created_at)
    if not parsed:
        return False
    now_dt = datetime.now(parsed.tzinfo) if parsed.tzinfo else datetime.now()
    return (now_dt - parsed).total_seconds() >= DIRECT_ORDER_PENDING_EXPIRE_SECONDS


async def _auto_cancel_expired_direct_orders(pending_direct_orders, bot_app=None):
    active_orders = []
    for order in pending_direct_orders:
        order_id, user_id, _product_id, _quantity, _bonus_quantity, _unit_price, _expected_amount, code, created_at = order
        if not _is_direct_order_expired(created_at):
            active_orders.append(order)
            continue

        await set_direct_order_status(order_id, "cancelled")
        website_order = _find_website_direct_order(code, _website_orders_by_code_upper, _website_orders_by_code_norm)
        if website_order:
            try:
                await set_website_direct_order_status(website_order[0], "cancelled")
            except Exception:
                pass
            _remove_website_direct_order_from_maps(website_order)
        logger.info("⏱️ Auto-cancel direct order #%s after %sm pending.", order_id, DIRECT_ORDER_PENDING_EXPIRE_MINUTES)
        if bot_app and not website_order:
            try:
                await bot_app.bot.send_message(
                    user_id,
                    f"⌛ Đơn thanh toán #{order_id} đã hết hạn sau {DIRECT_ORDER_PENDING_EXPIRE_MINUTES} phút và đã tự hủy."
                )
            except Exception:
                pass
    return active_orders


_website_orders_by_code_upper = {}
_website_orders_by_code_norm = {}


def _build_website_direct_order_maps(pending_website_direct_orders):
    _website_orders_by_code_upper.clear()
    _website_orders_by_code_norm.clear()
    for row in pending_website_direct_orders:
        code = str(row[8] or "").strip()
        if not code:
            continue
        _website_orders_by_code_upper[code.upper()] = row
        _website_orders_by_code_norm[_normalize_content(code)] = row


def _find_website_direct_order(code: str, by_code_upper: dict, by_code_norm: dict):
    code_text = str(code or "").strip()
    if not code_text:
        return None
    return by_code_upper.get(code_text.upper()) or by_code_norm.get(_normalize_content(code_text))


def _remove_website_direct_order_from_maps(row):
    code = str(row[8] or "").strip()
    if not code:
        return
    _website_orders_by_code_upper.pop(code.upper(), None)
    _website_orders_by_code_norm.pop(_normalize_content(code), None)

async def process_transactions(bot_app=None):
    """Xử lý giao dịch và cộng tiền tự động"""
    transactions = await get_recent_transactions()
    if USE_SUPABASE:
        pending_deposits = await get_pending_deposits()
        pending_direct_orders = await get_pending_direct_orders()
        pending_website_direct_orders = await get_pending_website_direct_orders()
        _build_website_direct_order_maps(pending_website_direct_orders)
        pending_direct_orders = await _auto_cancel_expired_direct_orders(pending_direct_orders, bot_app)
        if SEPAY_DEBUG:
            logger.info(
                "Pending deposits: %s | pending direct orders: %s | pending website direct orders: %s",
                len(pending_deposits),
                len(pending_direct_orders),
                len(pending_website_direct_orders),
            )
        for tx in transactions:
            amount_in = _pick_amount(tx)
            if float(amount_in) <= 0:
                continue

            content = _pick_content(tx)
            content_upper = str(content).upper().strip()
            content_norm = _normalize_content(content)
            amount = int(float(amount_in))
            tx_id = _pick_tx_id(tx)
            if SEPAY_DEBUG:
                logger.info("TX id=%s amount=%s content=%s", tx_id, amount, str(content)[:80])

            if not tx_id:
                continue
            if await is_processed_transaction(tx_id):
                continue

            matched = False
            for deposit in pending_deposits:
                deposit_id, user_id, _expected_amount, code, _created_at = deposit
                code_upper = code.upper()
                code_norm = _normalize_content(code)
                if code_upper in content_upper or code_norm in content_norm:
                    await set_deposit_status(deposit_id, "confirmed")
                    await update_balance(user_id, amount)
                    await mark_processed_transaction(tx_id)

                    print(f"✅ Confirmed: User {user_id}, Amount {amount:,}đ")

                    if bot_app:
                        try:
                            new_balance = await get_balance(user_id)
                            msg = await bot_app.bot.send_message(
                                user_id,
                                f"✅ NẠP TIỀN THÀNH CÔNG!\n\n"
                                f"💰 Số tiền: {amount:,}đ\n"
                                f"💳 Số dư hiện tại: {new_balance:,}đ"
                            )
                            mark_bot_message(user_id, msg.message_id)
                        except:
                            pass
                    matched = True
                    break

            if matched:
                continue

            for order in pending_direct_orders:
                order_id, user_id, product_id, quantity, bonus_quantity, unit_price, expected_amount, code, _created_at = order
                code_upper = code.upper()
                code_norm = _normalize_content(code)
                website_direct_order = _find_website_direct_order(code, _website_orders_by_code_upper, _website_orders_by_code_norm)
                if (code_upper in content_upper or code_norm in content_norm) and amount >= expected_amount:
                    # Fulfill direct order
                    deliver_quantity = max(1, int(quantity) + max(0, int(bonus_quantity or 0)))
                    stocks = await get_available_stock_batch(product_id, deliver_quantity)
                    if not stocks or len(stocks) < deliver_quantity:
                        await set_direct_order_status(order_id, "failed")
                        if website_direct_order:
                            try:
                                await set_website_direct_order_status(website_direct_order[0], "failed")
                            except Exception:
                                pass
                            _remove_website_direct_order_from_maps(website_direct_order)
                        elif bot_app:
                            await bot_app.bot.send_message(
                                user_id,
                                "❌ Thanh toán đã nhận nhưng sản phẩm hiện hết hàng. Vui lòng liên hệ admin."
                            )
                        await mark_processed_transaction(tx_id)
                        matched = True
                        break

                    stock_ids = [s[0] for s in stocks]
                    purchased_items = [s[1] for s in stocks]
                    await mark_stock_sold_batch(stock_ids)

                    order_group = f"PAY{user_id}{datetime.now().strftime('%Y%m%d%H%M%S')}"
                    if website_direct_order:
                        website_direct_order_id = website_direct_order[0]
                        website_auth_user_id = website_direct_order[1]
                        website_user_email = website_direct_order[2]
                        website_order_id = await create_website_order_bulk(
                            website_auth_user_id,
                            website_user_email,
                            product_id,
                            purchased_items,
                            unit_price,
                            order_group,
                            total_price=expected_amount,
                            quantity=len(purchased_items),
                            source_direct_code=code,
                        )
                        await set_direct_order_status(order_id, "confirmed")
                        await set_website_direct_order_status(
                            website_direct_order_id,
                            "confirmed",
                            fulfilled_order_id=website_order_id,
                        )
                        _remove_website_direct_order_from_maps(website_direct_order)
                        await mark_processed_transaction(tx_id)
                        logger.info(
                            "✅ Website direct order confirmed: code=%s website_direct_order_id=%s website_order_id=%s",
                            code,
                            website_direct_order_id,
                            website_order_id,
                        )
                    else:
                        await create_order_bulk(
                            user_id,
                            product_id,
                            purchased_items,
                            unit_price,
                            order_group,
                            total_price=expected_amount,
                            quantity=len(purchased_items),
                        )
                        await set_direct_order_status(order_id, "confirmed")
                        await mark_processed_transaction(tx_id)

                    if bot_app and not website_direct_order:
                        try:
                            product = await get_product(product_id)
                            product_name = product["name"] if product else f"#{product_id}"
                            description = (product.get("description") or "").strip() if product else ""
                            format_data = product.get("format_data") if product else None
                            total_text = f"{expected_amount:,}đ"
                            header_lines = [
                                f"Product: {product_name}",
                                f"Qty: {len(purchased_items)}",
                                f"Paid Qty: {quantity}",
                                f"Total: {total_text}",
                            ]
                            if bonus_quantity:
                                header_lines.append(f"Bonus: {bonus_quantity}")
                            if description:
                                header_lines.append(f"Description: {description}")
                            header = "\n".join(header_lines)
                            formatted_items_plain = format_stock_items(purchased_items, format_data, html=False)
                            file_buf = make_file(formatted_items_plain, header)
                            filename = f"{product_name}_{len(purchased_items)}.txt"

                            success_text = (
                                "✅ Thanh toán thành công!\n\n"
                                f"🧾 {product_name} | SL: {len(purchased_items)}\n"
                                f"💰 Tổng: {total_text}"
                            )
                            if bonus_quantity:
                                success_text += f"\n🎁 Tặng thêm: {bonus_quantity}"
                            description_block = format_description_block(description)
                            if len(purchased_items) > 5:
                                msg = await bot_app.bot.send_document(
                                    chat_id=user_id,
                                    document=file_buf,
                                    filename=filename,
                                    caption=success_text
                                )
                                mark_bot_message(user_id, msg.message_id)
                            else:
                                items_formatted = "\n\n".join(format_stock_items(purchased_items, format_data, html=True))
                                msg = await bot_app.bot.send_message(
                                    chat_id=user_id,
                                    text=f"{success_text}\n\n{description_block}🔐 Account:\n{items_formatted}",
                                    parse_mode="HTML"
                                )
                                mark_bot_message(user_id, msg.message_id)
                        except Exception:
                            pass
                    matched = True
                    break
            if matched:
                continue
        return

    async with aiosqlite.connect(DB_PATH) as db:
        # Auto-cancel stale direct orders in sqlite mode as well.
        cursor = await db.execute(
            "SELECT id, user_id, created_at FROM direct_orders WHERE status = 'pending'"
        )
        sqlite_pending_direct_orders = await cursor.fetchall()
        for order_id, user_id, created_at in sqlite_pending_direct_orders:
            if not _is_direct_order_expired(created_at):
                continue
            await db.execute(
                "UPDATE direct_orders SET status = 'cancelled' WHERE id = ?",
                (order_id,)
            )
            logger.info("⏱️ Auto-cancel direct order #%s after %sm pending. (sqlite)", order_id, DIRECT_ORDER_PENDING_EXPIRE_MINUTES)
            if bot_app:
                try:
                    await bot_app.bot.send_message(
                        user_id,
                        f"⌛ Đơn thanh toán #{order_id} đã hết hạn sau {DIRECT_ORDER_PENDING_EXPIRE_MINUTES} phút và đã tự hủy."
                    )
                except Exception:
                    pass
        await db.commit()

        # Lấy pending deposits
        cursor = await db.execute(
            "SELECT id, user_id, amount, code FROM deposits WHERE status = 'pending'"
        )
        pending_deposits = await cursor.fetchall()

        for tx in transactions:
            # Lấy thông tin giao dịch (API trả về amount_in cho tiền vào)
            amount_in = _pick_amount(tx)
            if float(amount_in) <= 0:
                continue

            content = _pick_content(tx)
            content_upper = str(content).upper().strip()
            content_norm = _normalize_content(content)
            amount = int(float(amount_in))
            tx_id = _pick_tx_id(tx)
            if SEPAY_DEBUG:
                logger.info("TX id=%s amount=%s content=%s", tx_id, amount, str(content)[:80])

            # Kiểm tra đã xử lý chưa
            if not tx_id:
                continue
            cursor = await db.execute(
                "SELECT 1 FROM processed_transactions WHERE tx_id = ?", (tx_id,)
            )
            if await cursor.fetchone():
                continue

            # Tìm deposit khớp
            for deposit in pending_deposits:
                deposit_id, user_id, expected_amount, code = deposit

                code_upper = code.upper()
                code_norm = _normalize_content(code)
                if code_upper in content_upper or code_norm in content_norm:
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
    if USE_SUPABASE:
        return
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
    logger.info("🔄 SePay checker started (interval: %ss, supabase=%s)", interval, USE_SUPABASE)
    last_mode = None
    
    while True:
        try:
            await process_transactions(bot_app)
        except Exception as e:
            logger.exception("Checker error: %s", e)
        fast_mode = has_latest_vietqr_message()
        mode = "fast" if fast_mode else "normal"
        if mode != last_mode:
            logger.info("SePay checker mode: %s", mode)
            last_mode = mode
        await asyncio.sleep(5 if fast_mode else interval)

if __name__ == "__main__":
    asyncio.run(run_checker())
