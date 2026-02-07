from datetime import datetime

_last_bot_message: dict[int, int] = {}
_last_vietqr_message: dict[int, int] = {}
_last_vietqr_at: dict[int, str] = {}


def mark_bot_message(chat_id: int, message_id: int) -> None:
    _last_bot_message[chat_id] = message_id


def mark_vietqr_message(chat_id: int, message_id: int) -> None:
    _last_bot_message[chat_id] = message_id
    _last_vietqr_message[chat_id] = message_id
    _last_vietqr_at[chat_id] = datetime.utcnow().isoformat()


def has_latest_vietqr_message() -> bool:
    for chat_id, msg_id in _last_vietqr_message.items():
        if _last_bot_message.get(chat_id) == msg_id:
            return True
    return False
