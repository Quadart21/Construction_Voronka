from pathlib import Path
from uuid import uuid4
import re

from telegram import Bot
from telegram.constants import ParseMode

from backend.config import settings


UPLOAD_PREFIX = "upload://"
PUBLIC_UPLOAD_PREFIX = "/uploads/"


def safe_upload_name(original_name: str) -> str:
    suffix = Path(original_name or "file").suffix.lower()
    stem = Path(original_name or "file").stem.lower()
    stem = re.sub(r"[^a-z0-9а-яё_-]+", "_", stem, flags=re.IGNORECASE).strip("_") or "file"
    return f"{uuid4().hex}_{stem[:48]}{suffix}"


def local_upload_path(media_url: str | None) -> Path | None:
    if not media_url:
        return None
    if media_url.startswith(UPLOAD_PREFIX):
        name = media_url.removeprefix(UPLOAD_PREFIX)
    elif media_url.startswith(PUBLIC_UPLOAD_PREFIX):
        name = media_url.removeprefix(PUBLIC_UPLOAD_PREFIX)
    else:
        return None
    path = (settings.upload_dir / name).resolve()
    upload_root = settings.upload_dir.resolve()
    if upload_root not in path.parents and path != upload_root:
        return None
    return path


async def send_media(
    bot: Bot,
    *,
    chat_id: int,
    media_type: str,
    media_url: str,
    caption: str | None = None,
    reply_markup=None,
    parse_mode: str | None = ParseMode.HTML,
    protect_content: bool = False,
):
    media_type = (media_type or "document").lower()
    local_path = local_upload_path(media_url)

    async def send(source):
        if media_type == "photo":
            return await bot.send_photo(
                chat_id=chat_id,
                photo=source,
                caption=caption,
                parse_mode=parse_mode,
                protect_content=protect_content,
                reply_markup=reply_markup,
            )
        if media_type == "video":
            return await bot.send_video(
                chat_id=chat_id,
                video=source,
                caption=caption,
                parse_mode=parse_mode,
                protect_content=protect_content,
                reply_markup=reply_markup,
            )
        if media_type in {"animation", "gif"}:
            return await bot.send_animation(
                chat_id=chat_id,
                animation=source,
                caption=caption,
                parse_mode=parse_mode,
                protect_content=protect_content,
                reply_markup=reply_markup,
            )
        return await bot.send_document(
            chat_id=chat_id,
            document=source,
            caption=caption,
            parse_mode=parse_mode,
            protect_content=protect_content,
            reply_markup=reply_markup,
        )

    if local_path:
        if not local_path.exists():
            raise FileNotFoundError(f"Uploaded media file not found: {local_path}")
        with local_path.open("rb") as file:
            return await send(file)
    return await send(media_url)
