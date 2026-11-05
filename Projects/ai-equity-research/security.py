"""Fail-closed Telegram chat allowlist helpers."""
import os

def parse_allowed_chat_ids(raw: str | None = None) -> set[int]:
    value = os.getenv("TELEGRAM_ALLOWED_CHAT_IDS", "") if raw is None else raw
    allowed = set()
    for item in value.split(","):
        item = item.strip()
        if not item:
            continue
        try:
            allowed.add(int(item))
        except ValueError as exc:
            raise ValueError("TELEGRAM_ALLOWED_CHAT_IDS harus berisi ID numerik dipisahkan koma.") from exc
    return allowed

def is_authorized_chat(chat_id: int | None, allowed_ids: set[int] | None = None) -> bool:
    allowed = parse_allowed_chat_ids() if allowed_ids is None else allowed_ids
    return chat_id is not None and bool(allowed) and int(chat_id) in allowed
