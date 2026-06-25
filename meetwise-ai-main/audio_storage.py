"""
Helpers for storing participant audio in Supabase Storage.

When Supabase Storage is not configured, callers can fall back to local files.
"""

import os
import re
import tempfile

import requests


SUPABASE_URL = os.getenv("SUPABASE_URL", "").rstrip("/")
SUPABASE_STORAGE_BUCKET = os.getenv("SUPABASE_STORAGE_BUCKET", "meeting-audio").strip()
SUPABASE_BACKEND_KEY = (
    os.getenv("SUPABASE_SECRET_KEY", "").strip()
    or os.getenv("SUPABASE_SERVICE_ROLE_KEY", "").strip()
)
STORAGE_ENABLED = bool(SUPABASE_URL and SUPABASE_STORAGE_BUCKET and SUPABASE_BACKEND_KEY)
TEMP_AUDIO_DIR = os.path.join(tempfile.gettempdir(), "meetwise-audio")
os.makedirs(TEMP_AUDIO_DIR, exist_ok=True)


def _storage_headers(content_type: str | None = None) -> dict:
    headers = {
        "apikey": SUPABASE_BACKEND_KEY,
        "Authorization": f"Bearer {SUPABASE_BACKEND_KEY}",
    }
    if content_type:
        headers["Content-Type"] = content_type
    return headers


def sanitize_filename(text: str) -> str:
    cleaned = re.sub(r"[^a-zA-Z0-9._-]+", "-", text.strip().lower())
    cleaned = cleaned.strip(".-")
    return cleaned or "participant"


def build_object_path(room_code: str, participant_id: str, participant_name: str, extension: str = "webm") -> str:
    safe_name = sanitize_filename(participant_name)
    safe_ext = extension.lstrip(".") or "webm"
    return f"{room_code}/{participant_id}-{safe_name}.{safe_ext}"


def upload_audio_bytes(
    room_code: str,
    participant_id: str,
    participant_name: str,
    contents: bytes,
    content_type: str = "audio/webm",
    extension: str = "webm",
) -> str:
    if not STORAGE_ENABLED:
        raise RuntimeError("Supabase Storage is not configured")

    object_path = build_object_path(room_code, participant_id, participant_name, extension=extension)
    response = requests.post(
        f"{SUPABASE_URL}/storage/v1/object/{SUPABASE_STORAGE_BUCKET}/{object_path}",
        headers={
            **_storage_headers(content_type),
            "x-upsert": "true",
        },
        data=contents,
        timeout=60,
    )
    response.raise_for_status()
    return object_path


def download_audio_to_temp(object_path: str, suffix: str = ".webm") -> str:
    if not STORAGE_ENABLED:
        raise RuntimeError("Supabase Storage is not configured")

    response = requests.get(
        f"{SUPABASE_URL}/storage/v1/object/authenticated/{SUPABASE_STORAGE_BUCKET}/{object_path}",
        headers=_storage_headers(),
        timeout=60,
    )
    response.raise_for_status()

    fd, temp_path = tempfile.mkstemp(prefix="meetwise-audio-", suffix=suffix, dir=TEMP_AUDIO_DIR)
    try:
        with os.fdopen(fd, "wb") as temp_file:
            temp_file.write(response.content)
    except Exception:
        try:
            os.remove(temp_path)
        except OSError:
            pass
        raise

    return temp_path


def cleanup_temp_file(path: str | None) -> None:
    if not path:
        return

    try:
        os.remove(path)
    except OSError:
        pass
