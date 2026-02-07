import asyncio
import json
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from .supabase_client import get_supabase_client


def _now_iso() -> str:
    return datetime.now().isoformat()


def _safe_int(value: Any, default: int = 0) -> int:
    if value is None:
        return default
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _safe_float(value: Any, default: float = 0.0) -> float:
    if value is None:
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


async def _to_thread(func, *args, **kwargs):
    return await asyncio.to_thread(func, *args, **kwargs)


def _get_table(name: str):
    supabase = get_supabase_client()
    return supabase.table(name)

_settings_cache: Dict[str, Dict[str, Any]] = {"values": {}, "ts": 0.0}
_SETTINGS_TTL_SECONDS = 60
_USER_CACHE_TTL_SECONDS = 30
_user_lang_cache: Dict[int, Tuple[str, float]] = {}


def _cache_get(cache: Dict[int, Tuple[Any, float]], key: int, ttl: int):
    entry = cache.get(key)
    if entry and (time.time() - entry[1] <= ttl):
        return entry[0]
    return None


def _cache_set(cache: Dict[int, Tuple[Any, float]], key: int, value: Any):
    cache[key] = (value, time.time())


def _parse_bool(value: Any, default: bool = True) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    text = str(value).strip().lower()
    if text in ("0", "false", "off", "no"):
        return False
    if text in ("1", "true", "on", "yes"):
        return True
    return default


async def init_db():
    # Ensure Supabase client can be created
    await _to_thread(get_supabase_client)


def _dt_to_utc_iso(value: Optional[datetime]) -> str:
    if not value:
        return datetime.now(timezone.utc).isoformat()
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).isoformat()


async def log_telegram_message(
    chat_id: int,
    message_id: int,
    direction: str,
    message_type: str = "text",
    text: Optional[str] = None,
    payload: Any = None,
    sent_at: Optional[datetime] = None,
):
    """
    Best-effort chat history logging for the admin dashboard.
    Logging must never break the bot flow, so errors are swallowed.
    """
    if not chat_id or not message_id:
        return

    direction_clean = str(direction).strip().lower()
    if direction_clean not in ("in", "out"):
        direction_clean = "out"

    message_type_clean = str(message_type or "text").strip().lower() or "text"

    row = {
        "chat_id": int(chat_id),
        "message_id": int(message_id),
        "direction": direction_clean,
        "message_type": message_type_clean,
        "text": text,
        "payload": payload,
        "sent_at": _dt_to_utc_iso(sent_at),
    }

    def _write():
        table = _get_table("telegram_messages")
        try:
            # Some versions support explicit conflict targets; fall back to plain insert otherwise.
            return table.upsert(row, on_conflict="chat_id,message_id").execute()
        except TypeError:
            return table.insert(row).execute()

    try:
        await _to_thread(_write)
    except Exception:
        return


# User functions
async def get_or_create_user(user_id: int, username: str = None):
    def _fetch():
        return _get_table("users").select("user_id, username, balance, balance_usdt, language").eq(
            "user_id", user_id
        ).limit(1).execute()

    resp = await _to_thread(_fetch)
    data = resp.data or []
    if not data:
        def _insert():
            return _get_table("users").insert({
                "user_id": user_id,
                "username": username,
                "language": None,
                "created_at": _now_iso(),
            }).execute()

        await _to_thread(_insert)
        _cache_set(_user_lang_cache, user_id, "vi")
        return {"user_id": user_id, "username": username, "balance": 0, "balance_usdt": 0, "language": None}

    row = data[0]
    balance = _safe_int(row.get("balance"))
    balance_usdt = _safe_float(row.get("balance_usdt"))
    language = row.get("language")
    if language:
        _cache_set(_user_lang_cache, user_id, language)
    return {
        "user_id": row.get("user_id"),
        "username": row.get("username"),
        "balance": balance,
        "balance_usdt": balance_usdt,
        "language": language,
    }


async def get_user_language(user_id: int) -> str:
    cached = _cache_get(_user_lang_cache, user_id, _USER_CACHE_TTL_SECONDS)
    if cached is not None:
        return cached

    def _fetch():
        return _get_table("users").select("language").eq("user_id", user_id).limit(1).execute()

    resp = await _to_thread(_fetch)
    data = resp.data or []
    if not data or not data[0].get("language"):
        _cache_set(_user_lang_cache, user_id, "vi")
        return "vi"
    lang = data[0]["language"]
    _cache_set(_user_lang_cache, user_id, lang)
    return lang


async def set_user_language(user_id: int, language: str):
    def _update():
        return _get_table("users").update({"language": language}).eq("user_id", user_id).execute()

    await _to_thread(_update)
    _cache_set(_user_lang_cache, user_id, language)


async def get_balance(user_id: int):
    def _fetch():
        return _get_table("users").select("balance").eq("user_id", user_id).limit(1).execute()

    resp = await _to_thread(_fetch)
    data = resp.data or []
    return _safe_int(data[0].get("balance")) if data else 0


async def get_balance_usdt(user_id: int):
    def _fetch():
        return _get_table("users").select("balance_usdt").eq("user_id", user_id).limit(1).execute()

    resp = await _to_thread(_fetch)
    data = resp.data or []
    return _safe_float(data[0].get("balance_usdt")) if data else 0


async def _set_balance(user_id: int, new_balance: int):
    def _update():
        return _get_table("users").update({"balance": new_balance}).eq("user_id", user_id).execute()

    await _to_thread(_update)


async def _set_balance_usdt(user_id: int, new_balance: float):
    def _update():
        return _get_table("users").update({"balance_usdt": new_balance}).eq("user_id", user_id).execute()

    await _to_thread(_update)


async def update_balance(user_id: int, amount: int):
    current = await get_balance(user_id)
    await _set_balance(user_id, current + amount)


async def update_balance_usdt(user_id: int, amount: float):
    current = await get_balance_usdt(user_id)
    await _set_balance_usdt(user_id, current + amount)


# Product functions
async def get_products():
    def _rpc():
        return get_supabase_client().rpc("get_products_with_stock").execute()

    try:
        resp = await _to_thread(_rpc)
        rows = resp.data or []
        return [
            {
                "id": row.get("id"),
                "name": row.get("name"),
                "price": _safe_int(row.get("price")),
                "description": row.get("description"),
                "stock": _safe_int(row.get("stock")),
                "price_usdt": _safe_float(row.get("price_usdt")),
                "format_data": row.get("format_data"),
            }
            for row in rows
        ]
    except Exception:
        # Fallback to per-product counting if RPC not available
        def _fetch():
            return _get_table("products").select("id, name, price, description, price_usdt, format_data").order("id").execute()

        resp = await _to_thread(_fetch)
        rows = resp.data or []
        products = []
        for row in rows:
            product_id = row.get("id")

            def _stock():
                return _get_table("stock").select("id").eq("product_id", product_id).eq("sold", False).execute()

            stock_resp = await _to_thread(_stock)
            stock_count = len(stock_resp.data or [])
            products.append({
                "id": product_id,
                "name": row.get("name"),
                "price": _safe_int(row.get("price")),
                "description": row.get("description"),
                "stock": stock_count,
                "price_usdt": _safe_float(row.get("price_usdt")),
                "format_data": row.get("format_data"),
            })
        return products


async def get_product(product_id: int):
    def _rpc():
        return get_supabase_client().rpc("get_product_with_stock", {"p_id": product_id}).execute()

    try:
        resp = await _to_thread(_rpc)
        data = resp.data or []
        if not data:
            return None
        row = data[0]
        return {
            "id": row.get("id"),
            "name": row.get("name"),
            "price": _safe_int(row.get("price")),
            "description": row.get("description"),
            "stock": _safe_int(row.get("stock")),
            "price_usdt": _safe_float(row.get("price_usdt")),
            "format_data": row.get("format_data"),
        }
    except Exception:
        def _fetch():
            return _get_table("products").select("id, name, price, description, price_usdt, format_data").eq(
                "id", product_id
            ).limit(1).execute()

        resp = await _to_thread(_fetch)
        data = resp.data or []
        if not data:
            return None
        row = data[0]

        def _stock():
            return _get_table("stock").select("id").eq("product_id", product_id).eq("sold", False).execute()

        stock_resp = await _to_thread(_stock)
        stock_count = len(stock_resp.data or [])
        return {
            "id": row.get("id"),
            "name": row.get("name"),
            "price": _safe_int(row.get("price")),
            "description": row.get("description"),
            "stock": stock_count,
            "price_usdt": _safe_float(row.get("price_usdt")),
            "format_data": row.get("format_data"),
        }


async def add_product(name: str, price: int, description: str = "", price_usdt: float = 0, format_data: str = ""):
    def _insert():
        return _get_table("products").insert({
            "name": name,
            "price": price,
            "description": description,
            "price_usdt": price_usdt,
            "format_data": format_data,
        }).execute()

    resp = await _to_thread(_insert)
    data = resp.data or []
    return data[0].get("id") if data else None


async def update_product_price_usdt(product_id: int, price_usdt: float):
    def _update():
        return _get_table("products").update({"price_usdt": price_usdt}).eq("id", product_id).execute()

    await _to_thread(_update)


async def delete_product(product_id: int):
    def _delete_stock():
        return _get_table("stock").delete().eq("product_id", product_id).execute()

    def _delete_product():
        return _get_table("products").delete().eq("id", product_id).execute()

    await _to_thread(_delete_stock)
    await _to_thread(_delete_product)


async def add_stock(product_id: int, content: str):
    def _insert():
        return _get_table("stock").insert({"product_id": product_id, "content": content}).execute()

    await _to_thread(_insert)


async def add_stock_bulk(product_id: int, contents: list):
    payload = [{"product_id": product_id, "content": content} for content in contents]

    def _insert():
        return _get_table("stock").insert(payload).execute()

    await _to_thread(_insert)


async def get_available_stock(product_id: int):
    def _fetch():
        return _get_table("stock").select("id, content").eq("product_id", product_id).eq(
            "sold", False
        ).limit(1).execute()

    resp = await _to_thread(_fetch)
    data = resp.data or []
    if not data:
        return None
    row = data[0]
    return (row.get("id"), row.get("content"))


async def get_available_stock_batch(product_id: int, quantity: int):
    def _fetch():
        return _get_table("stock").select("id, content").eq("product_id", product_id).eq(
            "sold", False
        ).limit(quantity).execute()

    resp = await _to_thread(_fetch)
    rows = resp.data or []
    return [(row.get("id"), row.get("content")) for row in rows]


async def mark_stock_sold(stock_id: int):
    def _update():
        return _get_table("stock").update({"sold": True}).eq("id", stock_id).execute()

    await _to_thread(_update)


async def mark_stock_sold_batch(stock_ids: list):
    if not stock_ids:
        return

    def _update():
        return _get_table("stock").update({"sold": True}).in_("id", stock_ids).execute()

    await _to_thread(_update)


async def get_stock_by_product(product_id: int):
    def _fetch():
        return _get_table("stock").select("id, content, sold").eq("product_id", product_id).order(
            "sold", desc=False
        ).order("id", desc=True).execute()

    resp = await _to_thread(_fetch)
    rows = resp.data or []
    return [(row.get("id"), row.get("content"), row.get("sold")) for row in rows]


async def get_stock_detail(stock_id: int):
    def _fetch():
        return _get_table("stock").select("id, product_id, content, sold").eq(
            "id", stock_id
        ).limit(1).execute()

    resp = await _to_thread(_fetch)
    data = resp.data or []
    if not data:
        return None
    row = data[0]
    return (row.get("id"), row.get("product_id"), row.get("content"), row.get("sold"))


async def update_stock_content(stock_id: int, new_content: str):
    def _update():
        return _get_table("stock").update({"content": new_content}).eq("id", stock_id).execute()

    await _to_thread(_update)


async def delete_stock(stock_id: int):
    def _delete():
        return _get_table("stock").delete().eq("id", stock_id).execute()

    await _to_thread(_delete)


async def delete_all_stock(product_id: int, only_unsold: bool = False):
    def _delete():
        query = _get_table("stock").delete().eq("product_id", product_id)
        if only_unsold:
            query = query.eq("sold", False)
        return query.execute()

    await _to_thread(_delete)


async def export_stock(product_id: int, only_unsold: bool = True):
    def _fetch():
        query = _get_table("stock").select("content").eq("product_id", product_id)
        if only_unsold:
            query = query.eq("sold", False)
        return query.order("id").execute()

    resp = await _to_thread(_fetch)
    rows = resp.data or []
    return [row.get("content") for row in rows]


# Order functions
async def create_order_bulk(user_id: int, product_id: int, contents: list, price_per_item: int, order_group: str):
    def _insert():
        return _get_table("orders").insert({
            "user_id": user_id,
            "product_id": product_id,
            "content": json.dumps(contents),
            "price": price_per_item * len(contents),
            "quantity": len(contents),
            "order_group": order_group,
            "created_at": _now_iso(),
        }).execute()

    await _to_thread(_insert)


async def create_order(user_id: int, product_id: int, content: str, price: int):
    def _insert():
        return _get_table("orders").insert({
            "user_id": user_id,
            "product_id": product_id,
            "content": content,
            "price": price,
            "quantity": 1,
            "created_at": _now_iso(),
        }).execute()

    await _to_thread(_insert)


async def _get_product_names(product_ids: List[int]) -> Dict[int, str]:
    if not product_ids:
        return {}

    def _fetch():
        return _get_table("products").select("id, name").in_("id", list(set(product_ids))).execute()

    resp = await _to_thread(_fetch)
    rows = resp.data or []
    return {row.get("id"): row.get("name") for row in rows}


async def get_user_orders(user_id: int):
    def _fetch():
        return _get_table("orders").select(
            "id, product_id, content, price, created_at, quantity, products(name)"
        ).eq("user_id", user_id).order("created_at", desc=True).limit(20).execute()

    resp = await _to_thread(_fetch)
    rows = resp.data or []
    results = []
    for row in rows:
        product = row.get("products") or {}
        results.append((
            row.get("id"),
            product.get("name"),
            row.get("content"),
            _safe_int(row.get("price")),
            row.get("created_at"),
            _safe_int(row.get("quantity"), 1),
        ))
    return results


async def get_order_detail(order_id: int):
    def _fetch():
        return _get_table("orders").select(
            "id, product_id, content, price, created_at, quantity, products(name)"
        ).eq("id", order_id).limit(1).execute()

    resp = await _to_thread(_fetch)
    data = resp.data or []
    if not data:
        return None
    row = data[0]
    product = row.get("products") or {}
    return (
        row.get("id"),
        product.get("name"),
        row.get("content"),
        _safe_int(row.get("price")),
        row.get("created_at"),
        _safe_int(row.get("quantity"), 1),
    )


async def get_sold_codes_by_product(product_id: int, limit: int = 100):
    def _fetch():
        return _get_table("orders").select(
            "id, user_id, content, price, quantity, created_at"
        ).eq("product_id", product_id).order("created_at", desc=True).limit(limit).execute()

    resp = await _to_thread(_fetch)
    rows = resp.data or []
    return [
        (
            row.get("id"),
            row.get("user_id"),
            row.get("content"),
            _safe_int(row.get("price")),
            _safe_int(row.get("quantity"), 1),
            row.get("created_at"),
        )
        for row in rows
    ]


async def get_sold_codes_by_user(user_id: int, limit: int = 50):
    def _fetch():
        return _get_table("orders").select(
            "id, product_id, content, price, quantity, created_at, products(name)"
        ).eq("user_id", user_id).order("created_at", desc=True).limit(limit).execute()

    resp = await _to_thread(_fetch)
    rows = resp.data or []
    return [
        (
            row.get("id"),
            (row.get("products") or {}).get("name"),
            row.get("content"),
            _safe_int(row.get("price")),
            _safe_int(row.get("quantity"), 1),
            row.get("created_at"),
        )
        for row in rows
    ]


async def search_user_by_id(user_id: int):
    def _fetch():
        return _get_table("users").select("user_id, username, balance, created_at").eq(
            "user_id", user_id
        ).limit(1).execute()

    resp = await _to_thread(_fetch)
    data = resp.data or []
    if not data:
        return None
    row = data[0]
    return (row.get("user_id"), row.get("username"), _safe_int(row.get("balance")), row.get("created_at"))


# Deposit functions
async def create_deposit_with_settings(user_id: int, amount: int, code: str):
    def _rpc():
        return get_supabase_client().rpc(
            "create_deposit_and_get_bank_settings",
            {"p_user_id": user_id, "p_amount": amount, "p_code": code},
        ).execute()

    try:
        resp = await _to_thread(_rpc)
        data = resp.data or []
        row = data[0] if isinstance(data, list) and data else data
        if row:
            return {
                "bank_name": row.get("bank_name") or "",
                "account_number": row.get("account_number") or "",
                "account_name": row.get("account_name") or "",
                "sepay_token": "",
            }
    except Exception:
        pass

    # Fallback to separate calls if RPC missing
    await create_deposit(user_id, amount, code)
    return await get_bank_settings()


async def create_deposit(user_id: int, amount: int, code: str):
    def _insert():
        return _get_table("deposits").insert({
            "user_id": user_id,
            "amount": amount,
            "code": code,
            "created_at": _now_iso(),
        }).execute()

    await _to_thread(_insert)


# Direct order functions
async def create_direct_order_with_settings(user_id: int, product_id: int, quantity: int, unit_price: int, amount: int, code: str):
    def _rpc():
        return get_supabase_client().rpc(
            "create_direct_order_and_get_bank_settings",
            {
                "p_user_id": user_id,
                "p_product_id": product_id,
                "p_quantity": quantity,
                "p_unit_price": unit_price,
                "p_amount": amount,
                "p_code": code,
            },
        ).execute()

    try:
        resp = await _to_thread(_rpc)
        data = resp.data or []
        row = data[0] if isinstance(data, list) and data else data
        if row:
            return {
                "bank_name": row.get("bank_name") or "",
                "account_number": row.get("account_number") or "",
                "account_name": row.get("account_name") or "",
                "sepay_token": "",
            }
    except Exception:
        pass

    await create_direct_order(user_id, product_id, quantity, unit_price, amount, code)
    return await get_bank_settings()


async def create_direct_order(user_id: int, product_id: int, quantity: int, unit_price: int, amount: int, code: str):
    def _insert():
        return _get_table("direct_orders").insert({
            "user_id": user_id,
            "product_id": product_id,
            "quantity": quantity,
            "unit_price": unit_price,
            "amount": amount,
            "code": code,
            "created_at": _now_iso(),
        }).execute()

    await _to_thread(_insert)


async def get_pending_direct_orders():
    def _fetch():
        return _get_table("direct_orders").select(
            "id, user_id, product_id, quantity, unit_price, amount, code, created_at"
        ).eq("status", "pending").execute()

    resp = await _to_thread(_fetch)
    rows = resp.data or []
    return [
        (
            row.get("id"),
            row.get("user_id"),
            row.get("product_id"),
            _safe_int(row.get("quantity"), 1),
            _safe_int(row.get("unit_price")),
            _safe_int(row.get("amount")),
            row.get("code"),
            row.get("created_at"),
        )
        for row in rows
    ]


async def set_direct_order_status(order_id: int, status: str):
    def _update():
        return _get_table("direct_orders").update({"status": status}).eq("id", order_id).execute()

    await _to_thread(_update)


async def get_pending_deposits():
    def _fetch():
        return _get_table("deposits").select("id, user_id, amount, code, created_at").eq(
            "status", "pending"
        ).execute()

    resp = await _to_thread(_fetch)
    rows = resp.data or []
    return [
        (
            row.get("id"),
            row.get("user_id"),
            _safe_int(row.get("amount")),
            row.get("code"),
            row.get("created_at"),
        )
        for row in rows
    ]


async def confirm_deposit(deposit_id: int):
    def _fetch():
        return _get_table("deposits").select("user_id, amount").eq("id", deposit_id).limit(1).execute()

    resp = await _to_thread(_fetch)
    data = resp.data or []
    if not data:
        return None
    row = data[0]
    user_id = row.get("user_id")
    amount = _safe_int(row.get("amount"))

    def _update_deposit():
        return _get_table("deposits").update({"status": "confirmed"}).eq("id", deposit_id).execute()

    await _to_thread(_update_deposit)
    await update_balance(user_id, amount)
    return (user_id, amount)


async def cancel_deposit(deposit_id: int):
    def _update():
        return _get_table("deposits").update({"status": "cancelled"}).eq("id", deposit_id).execute()

    await _to_thread(_update)


async def set_deposit_status(deposit_id: int, status: str):
    def _update():
        return _get_table("deposits").update({"status": status}).eq("id", deposit_id).execute()

    await _to_thread(_update)


# Stats
async def get_stats():
    def _rpc():
        return get_supabase_client().rpc("get_stats").execute()

    try:
        resp = await _to_thread(_rpc)
        data = resp.data or []
        row = data[0] if isinstance(data, list) and data else data
        if row:
            return {
                "users": _safe_int(row.get("users")),
                "orders": _safe_int(row.get("orders")),
                "revenue": _safe_int(row.get("revenue")),
            }
    except Exception:
        pass

    # Fallback to manual counts
    def _count_users():
        return _get_table("users").select("user_id").execute()

    def _count_orders():
        return _get_table("orders").select("id, price").execute()

    users_resp = await _to_thread(_count_users)
    orders_resp = await _to_thread(_count_orders)
    users = len(users_resp.data or [])
    orders = len(orders_resp.data or [])
    revenue = sum(_safe_int(row.get("price")) for row in (orders_resp.data or []))
    return {"users": users, "orders": orders, "revenue": revenue}


async def get_all_user_ids():
    def _fetch():
        return _get_table("users").select("user_id").execute()

    resp = await _to_thread(_fetch)
    rows = resp.data or []
    return [row.get("user_id") for row in rows if row.get("user_id") is not None]


# Withdrawal functions
async def create_withdrawal(user_id: int, amount: int, momo_phone: str):
    def _insert():
        return _get_table("withdrawals").insert({
            "user_id": user_id,
            "amount": amount,
            "momo_phone": momo_phone,
            "created_at": _now_iso(),
        }).execute()

    await _to_thread(_insert)


async def get_pending_withdrawals():
    def _fetch():
        return _get_table("withdrawals").select(
            "id, user_id, amount, momo_phone, created_at"
        ).eq("status", "pending").execute()

    resp = await _to_thread(_fetch)
    rows = resp.data or []
    return [
        (
            row.get("id"),
            row.get("user_id"),
            _safe_int(row.get("amount")),
            row.get("momo_phone"),
            row.get("created_at"),
        )
        for row in rows
    ]


async def get_withdrawal_detail(withdrawal_id: int):
    def _fetch():
        return _get_table("withdrawals").select(
            "id, user_id, amount, momo_phone, status, created_at"
        ).eq("id", withdrawal_id).limit(1).execute()

    resp = await _to_thread(_fetch)
    data = resp.data or []
    if not data:
        return None
    row = data[0]
    return (
        row.get("id"),
        row.get("user_id"),
        _safe_int(row.get("amount")),
        row.get("momo_phone"),
        row.get("status"),
        row.get("created_at"),
    )


async def get_user_pending_withdrawal(user_id: int):
    def _fetch():
        return _get_table("withdrawals").select("amount").eq("user_id", user_id).eq(
            "status", "pending"
        ).execute()

    resp = await _to_thread(_fetch)
    rows = resp.data or []
    return sum(_safe_int(row.get("amount")) for row in rows)


async def confirm_withdrawal(withdrawal_id: int):
    def _fetch():
        return _get_table("withdrawals").select("user_id, amount, momo_phone").eq(
            "id", withdrawal_id
        ).limit(1).execute()

    resp = await _to_thread(_fetch)
    data = resp.data or []
    if not data:
        return None
    row = data[0]
    user_id = row.get("user_id")
    amount = _safe_int(row.get("amount"))
    momo_phone = row.get("momo_phone")

    balance = await get_balance(user_id)
    if balance < amount:
        return None

    await _set_balance(user_id, balance - amount)

    def _update():
        return _get_table("withdrawals").update({"status": "confirmed"}).eq("id", withdrawal_id).execute()

    await _to_thread(_update)
    return (user_id, amount, momo_phone)


async def cancel_withdrawal(withdrawal_id: int):
    def _fetch():
        return _get_table("withdrawals").select("user_id, amount").eq("id", withdrawal_id).limit(1).execute()

    resp = await _to_thread(_fetch)
    data = resp.data or []
    if not data:
        return None
    row = data[0]

    def _update():
        return _get_table("withdrawals").update({"status": "cancelled"}).eq("id", withdrawal_id).execute()

    await _to_thread(_update)
    return (row.get("user_id"), _safe_int(row.get("amount")))


# Settings functions
async def get_setting(key: str, default: str = ""):
    now = time.time()
    cached = _settings_cache["values"].get(key)
    if cached is not None and (now - _settings_cache["ts"] <= _SETTINGS_TTL_SECONDS):
        return cached

    def _fetch():
        return _get_table("settings").select("value").eq("key", key).limit(1).execute()

    resp = await _to_thread(_fetch)
    data = resp.data or []
    value = data[0].get("value") if data else default
    _settings_cache["values"][key] = value
    _settings_cache["ts"] = now
    return value


async def set_setting(key: str, value: str):
    def _upsert():
        return _get_table("settings").upsert({"key": key, "value": value}).execute()

    await _to_thread(_upsert)
    _settings_cache["values"][key] = value
    _settings_cache["ts"] = time.time()


async def get_ui_flags() -> Dict[str, bool]:
    return {
        "show_shop": _parse_bool(await get_setting("show_shop", "true")),
        "show_balance": _parse_bool(await get_setting("show_balance", "true")),
        "show_deposit": _parse_bool(await get_setting("show_deposit", "true")),
        "show_withdraw": _parse_bool(await get_setting("show_withdraw", "true")),
        "show_usdt": _parse_bool(await get_setting("show_usdt", "true")),
        "show_history": _parse_bool(await get_setting("show_history", "true")),
        "show_language": _parse_bool(await get_setting("show_language", "true")),
    }


async def get_bank_settings():
    return {
        "bank_name": await get_setting("bank_name", ""),
        "account_number": await get_setting("account_number", ""),
        "account_name": await get_setting("account_name", ""),
        "sepay_token": await get_setting("sepay_token", ""),
    }


# Binance deposit functions
async def create_binance_deposit(user_id: int, usdt_amount: float, vnd_amount: int, code: str):
    def _insert():
        return _get_table("binance_deposits").insert({
            "user_id": user_id,
            "usdt_amount": usdt_amount,
            "vnd_amount": vnd_amount,
            "code": code,
            "created_at": _now_iso(),
        }).execute()

    await _to_thread(_insert)


async def update_binance_deposit_screenshot(user_id: int, code: str, file_id: str):
    def _update():
        return _get_table("binance_deposits").update(
            {"screenshot_file_id": file_id}
        ).eq("user_id", user_id).eq("code", code).eq("status", "pending").execute()

    await _to_thread(_update)


async def get_pending_binance_deposits():
    def _fetch():
        return _get_table("binance_deposits").select(
            "id, user_id, usdt_amount, vnd_amount, code, screenshot_file_id, created_at"
        ).eq("status", "pending").not_.is_("screenshot_file_id", "null").execute()

    resp = await _to_thread(_fetch)
    rows = resp.data or []
    return [
        (
            row.get("id"),
            row.get("user_id"),
            _safe_float(row.get("usdt_amount")),
            _safe_int(row.get("vnd_amount")),
            row.get("code"),
            row.get("screenshot_file_id"),
            row.get("created_at"),
        )
        for row in rows
    ]


async def get_binance_deposit_detail(deposit_id: int):
    def _fetch():
        return _get_table("binance_deposits").select(
            "id, user_id, usdt_amount, vnd_amount, code, screenshot_file_id, status, created_at"
        ).eq("id", deposit_id).limit(1).execute()

    resp = await _to_thread(_fetch)
    data = resp.data or []
    if not data:
        return None
    row = data[0]
    return (
        row.get("id"),
        row.get("user_id"),
        _safe_float(row.get("usdt_amount")),
        _safe_int(row.get("vnd_amount")),
        row.get("code"),
        row.get("screenshot_file_id"),
        row.get("status"),
        row.get("created_at"),
    )


async def confirm_binance_deposit(deposit_id: int):
    def _fetch():
        return _get_table("binance_deposits").select("user_id, usdt_amount").eq(
            "id", deposit_id
        ).limit(1).execute()

    resp = await _to_thread(_fetch)
    data = resp.data or []
    if not data:
        return None
    row = data[0]
    user_id = row.get("user_id")
    usdt_amount = _safe_float(row.get("usdt_amount"))

    def _update_deposit():
        return _get_table("binance_deposits").update({"status": "confirmed"}).eq(
            "id", deposit_id
        ).execute()

    await _to_thread(_update_deposit)
    await update_balance_usdt(user_id, usdt_amount)
    return (user_id, usdt_amount)


async def cancel_binance_deposit(deposit_id: int):
    def _update():
        return _get_table("binance_deposits").update({"status": "cancelled"}).eq("id", deposit_id).execute()

    await _to_thread(_update)


async def get_user_pending_binance_deposit(user_id: int):
    def _fetch():
        return _get_table("binance_deposits").select(
            "id, usdt_amount, vnd_amount, code"
        ).eq("user_id", user_id).eq("status", "pending").order("id", desc=True).limit(1).execute()

    resp = await _to_thread(_fetch)
    data = resp.data or []
    if not data:
        return None
    row = data[0]
    return (
        row.get("id"),
        _safe_float(row.get("usdt_amount")),
        _safe_int(row.get("vnd_amount")),
        row.get("code"),
    )


# USDT Withdrawal functions
async def create_usdt_withdrawal(user_id: int, usdt_amount: float, wallet_address: str, network: str = "TRC20"):
    def _insert():
        return _get_table("usdt_withdrawals").insert({
            "user_id": user_id,
            "usdt_amount": usdt_amount,
            "wallet_address": wallet_address,
            "network": network,
            "created_at": _now_iso(),
        }).execute()

    await _to_thread(_insert)


async def get_pending_usdt_withdrawals():
    def _fetch():
        return _get_table("usdt_withdrawals").select(
            "id, user_id, usdt_amount, wallet_address, network, created_at"
        ).eq("status", "pending").execute()

    resp = await _to_thread(_fetch)
    rows = resp.data or []
    return [
        (
            row.get("id"),
            row.get("user_id"),
            _safe_float(row.get("usdt_amount")),
            row.get("wallet_address"),
            row.get("network"),
            row.get("created_at"),
        )
        for row in rows
    ]


async def get_usdt_withdrawal_detail(withdrawal_id: int):
    def _fetch():
        return _get_table("usdt_withdrawals").select(
            "id, user_id, usdt_amount, wallet_address, network, status, created_at"
        ).eq("id", withdrawal_id).limit(1).execute()

    resp = await _to_thread(_fetch)
    data = resp.data or []
    if not data:
        return None
    row = data[0]
    return (
        row.get("id"),
        row.get("user_id"),
        _safe_float(row.get("usdt_amount")),
        row.get("wallet_address"),
        row.get("network"),
        row.get("status"),
        row.get("created_at"),
    )


async def get_user_pending_usdt_withdrawal(user_id: int):
    def _fetch():
        return _get_table("usdt_withdrawals").select("usdt_amount").eq("user_id", user_id).eq(
            "status", "pending"
        ).execute()

    resp = await _to_thread(_fetch)
    rows = resp.data or []
    return sum(_safe_float(row.get("usdt_amount")) for row in rows)


async def confirm_usdt_withdrawal(withdrawal_id: int):
    def _fetch():
        return _get_table("usdt_withdrawals").select(
            "user_id, usdt_amount, wallet_address"
        ).eq("id", withdrawal_id).limit(1).execute()

    resp = await _to_thread(_fetch)
    data = resp.data or []
    if not data:
        return None
    row = data[0]
    user_id = row.get("user_id")
    usdt_amount = _safe_float(row.get("usdt_amount"))
    wallet_address = row.get("wallet_address")

    balance = await get_balance_usdt(user_id)
    if balance < usdt_amount:
        return None

    await _set_balance_usdt(user_id, balance - usdt_amount)

    def _update():
        return _get_table("usdt_withdrawals").update({"status": "confirmed"}).eq("id", withdrawal_id).execute()

    await _to_thread(_update)
    return (user_id, usdt_amount, wallet_address)


async def cancel_usdt_withdrawal(withdrawal_id: int):
    def _fetch():
        return _get_table("usdt_withdrawals").select("user_id, usdt_amount").eq(
            "id", withdrawal_id
        ).limit(1).execute()

    resp = await _to_thread(_fetch)
    data = resp.data or []
    if not data:
        return None
    row = data[0]

    def _update():
        return _get_table("usdt_withdrawals").update({"status": "cancelled"}).eq("id", withdrawal_id).execute()

    await _to_thread(_update)
    return (row.get("user_id"), _safe_float(row.get("usdt_amount")))


# SePay processed transactions
async def is_processed_transaction(tx_id: str) -> bool:
    def _fetch():
        return _get_table("processed_transactions").select("tx_id").eq("tx_id", tx_id).limit(1).execute()

    resp = await _to_thread(_fetch)
    data = resp.data or []
    return bool(data)


async def mark_processed_transaction(tx_id: str):
    def _insert():
        return _get_table("processed_transactions").insert({"tx_id": tx_id}).execute()

    await _to_thread(_insert)
