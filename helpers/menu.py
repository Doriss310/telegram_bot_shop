from typing import Optional
from helpers.sepay_state import mark_bot_message


async def delete_last_menu_message(context, chat_id: int, current_message_id: Optional[int] = None) -> None:
    data = context.user_data
    msg_id = data.get("last_menu_message_id")
    msg_chat = data.get("last_menu_chat_id")
    if not msg_id or msg_chat != chat_id:
        return
    if current_message_id and msg_id == current_message_id:
        return
    try:
        await context.bot.delete_message(chat_id=chat_id, message_id=msg_id)
    except Exception:
        pass
    data.pop("last_menu_message_id", None)
    data.pop("last_menu_chat_id", None)


def set_last_menu_message(context, message) -> None:
    if not message:
        return
    try:
        context.user_data["last_menu_message_id"] = message.message_id
        context.user_data["last_menu_chat_id"] = message.chat_id
        mark_bot_message(message.chat_id, message.message_id)
    except Exception:
        return


def clear_last_menu_message(context, message) -> None:
    if not message:
        return
    try:
        if (
            context.user_data.get("last_menu_message_id") == message.message_id
            and context.user_data.get("last_menu_chat_id") == message.chat_id
        ):
            context.user_data.pop("last_menu_message_id", None)
            context.user_data.pop("last_menu_chat_id", None)
    except Exception:
        return
