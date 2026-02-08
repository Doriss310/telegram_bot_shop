from keyboards import user_reply_keyboard
from database import get_setting, get_ui_flags as _get_ui_flags


async def get_ui_flags() -> dict:
    try:
        return await _get_ui_flags()
    except Exception:
        return {}


async def get_user_keyboard(lang: str):
    flags = await get_ui_flags()
    return user_reply_keyboard(lang, flags)


def _parse_shop_page_size(raw_value: str, default: int = 10) -> int:
    try:
        value = int(str(raw_value).strip())
    except (TypeError, ValueError):
        value = default
    return max(1, min(50, value))


async def get_shop_page_size(default: int = 10) -> int:
    try:
        raw_value = await get_setting("shop_page_size", str(default))
        return _parse_shop_page_size(raw_value, default=default)
    except Exception:
        return default


async def is_feature_enabled(key: str) -> bool:
    flags = await get_ui_flags()
    return bool(flags.get(key, True))
