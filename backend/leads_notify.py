import html

from telegram import Bot

from backend.config import settings
from backend.database import session_scope
from backend.models import Lead


async def notify_admins_about_lead(lead_id: int) -> None:
    if not settings.bot_token.strip() or not settings.admin_id_list:
        return
    with session_scope() as session:
        lead = session.get(Lead, lead_id)
        if lead is None:
            return
        lines = [
            "📩 <b>Новая заявка с лендинга</b>",
            f"#{lead.id}",
            f"👤 {html.escape(lead.full_name)}",
            f"✉️ {html.escape(lead.email)}",
            f"📞 {html.escape(lead.phone)}",
        ]
        if lead.company:
            lines.append(f"🏢 {html.escape(lead.company)}")
        if lead.message:
            raw = lead.message.strip()
            msg = raw[:900] + ("…" if len(raw) > 900 else "")
            lines.append(f"💬 {html.escape(msg)}")
        text = "\n".join(lines)
    async with Bot(settings.bot_token) as bot:
        for aid in settings.admin_id_list:
            try:
                await bot.send_message(chat_id=aid, text=text, parse_mode="HTML")
            except Exception:
                continue
