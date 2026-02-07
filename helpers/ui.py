from keyboards import user_reply_keyboard
from database import get_ui_flags as _get_ui_flags


async def get_ui_flags() -> dict:
    try:
        return await _get_ui_flags()
    except Exception:
        return {}


async def get_user_keyboard(lang: str):
    flags = await get_ui_flags()
    return user_reply_keyboard(lang, flags)


async def is_feature_enabled(key: str) -> bool:
    flags = await get_ui_flags()
    return bool(flags.get(key, True))
