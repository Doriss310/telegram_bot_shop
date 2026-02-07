from .vi import VI
from .en import EN

LANGS = {
    'vi': VI,
    'en': EN
}

def get_text(lang: str, key: str) -> str:
    """Lấy text theo ngôn ngữ"""
    texts = LANGS.get(lang, VI)
    return texts.get(key, VI.get(key, key))
