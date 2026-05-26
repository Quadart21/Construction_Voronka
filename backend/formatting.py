from html import escape


TELEGRAM_MEDIA_CAPTION_LIMIT = 1024


def text_value(value, fallback: str = "") -> str:
    return str(value if value is not None else fallback).strip()


def truncate_text(value: str, limit: int) -> str:
    if limit <= 0:
        return ""
    if len(value) <= limit:
        return value
    return value[: max(0, limit - 3)].rstrip() + "..."


def html_message(title: str | None, body: str | None) -> str:
    title_text = text_value(title)
    body_text = text_value(body)
    if title_text and body_text:
        return f"<b>{escape(title_text)}</b>\n\n{escape(body_text)}"
    if title_text:
        return f"<b>{escape(title_text)}</b>"
    return escape(body_text)


def html_media_caption(title: str | None, body: str | None, caption: str | None = None) -> str:
    explicit_caption = text_value(caption)
    if explicit_caption:
        return escape(truncate_text(explicit_caption, TELEGRAM_MEDIA_CAPTION_LIMIT))

    title_text = truncate_text(text_value(title), 160)
    body_budget = TELEGRAM_MEDIA_CAPTION_LIMIT - len(title_text) - 8
    body_text = truncate_text(text_value(body), body_budget)
    return html_message(title_text, body_text)
