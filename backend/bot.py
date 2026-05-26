from telegram import InlineKeyboardButton, InlineKeyboardMarkup, MenuButtonCommands, Update
from telegram.constants import ParseMode
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from backend.config import settings
from backend.database import session_scope
from backend.formatting import html_media_caption, html_message
from backend.media import send_media
from backend.payments import create_platega_payment_link
from sqlalchemy import select

from backend.models import AutomationRule, FollowUpMessage, User
from backend.services import (
    create_payment_record,
    get_automation_rules,
    get_branch_by_id,
    get_branches_for_step,
    get_first_funnel_step,
    get_followups,
    get_or_create_user,
    get_segment_entry_step,
    get_setting,
    get_step_by_code,
    get_step_by_trigger,
    get_step_by_id,
    log_event,
    should_rate_limit,
)


def managed_messages(application: Application) -> dict[int, int]:
    store = application.bot_data.get("managed_messages")
    if store is None:
        store = {}
        application.bot_data["managed_messages"] = store
    return store


async def send_replacing_previous(
    *,
    application: Application,
    chat_id: int,
    text: str,
    reply_markup=None,
    parse_mode: str | None = None,
    protect_content: bool = False,
) -> None:
    store = managed_messages(application)
    previous_message_id = store.get(chat_id)
    if previous_message_id:
        try:
            await application.bot.delete_message(chat_id=chat_id, message_id=previous_message_id)
        except Exception:
            pass
    message = await application.bot.send_message(
        chat_id=chat_id,
        text=text,
        reply_markup=reply_markup,
        parse_mode=parse_mode,
        protect_content=protect_content,
    )
    store[chat_id] = message.message_id


async def send_media_with_cleanup(
    *,
    application: Application,
    chat_id: int,
    media_type: str,
    media_url: str,
    caption: str | None = None,
    reply_markup=None,
    parse_mode: str | None = None,
    protect_content: bool = False,
) -> None:
    store = managed_messages(application)
    previous_message_id = store.get(chat_id)
    if previous_message_id:
        try:
            await application.bot.delete_message(chat_id=chat_id, message_id=previous_message_id)
        except Exception:
            pass

    message = await send_media(
        application.bot,
        chat_id=chat_id,
        media_type=media_type,
        media_url=media_url,
        caption=caption,
        reply_markup=reply_markup,
        parse_mode=parse_mode,
        protect_content=protect_content,
    )
    store[chat_id] = message.message_id


def branch_keyboard(step, branches: list) -> InlineKeyboardMarkup | None:
    rows = []
    for branch in branches:
        if branch.url:
            # External button
            rows.append([InlineKeyboardButton(branch.button_text, url=branch.url)])
        elif branch.target_step_code:
            # Internal button
            rows.append([InlineKeyboardButton(branch.button_text, callback_data=f"branch:{branch.id}")])
        # If both are missing, skip (should not happen with validation)
    if step.step_type == "payment":
        rows.append([InlineKeyboardButton(step.cta_text or "Оплатить", callback_data=f"pay_step:{step.id}")])
    elif step.next_step_code:
        rows.append([InlineKeyboardButton(step.cta_text or "Продолжить", callback_data=f"next:{step.id}")])
    return InlineKeyboardMarkup(rows) if rows else None


async def render_first_step(application: Application, chat_id: int, telegram_user) -> None:
    with session_scope() as session:
        user = get_or_create_user(session, telegram_user)
        user.segment_key = None
        step = get_segment_entry_step(session) or get_first_funnel_step(session)
        if step is None:
            await send_replacing_previous(
                application=application,
                chat_id=chat_id,
                text="Цепочка пока пустая. Добавьте первый шаг в админке.",
                protect_content=settings.content_protection_enabled,
            )
            return
        branches = get_branches_for_step(session, step.code)
        log_event(session, user, "start", step.code, {"source": "telegram_start", "step_title": step.title})
        text = html_message(step.title, step.body)
        media_type = step.media_type
        media_url = step.media_url
        caption = html_media_caption(step.title, step.body, step.media_caption)
    keyboard = branch_keyboard(step, branches)
    if media_type and media_url:
        try:
            await send_media_with_cleanup(
                application=application,
                chat_id=chat_id,
                media_type=media_type,
                media_url=media_url,
                caption=caption,
                reply_markup=keyboard,
                parse_mode=ParseMode.HTML,
                protect_content=settings.content_protection_enabled,
            )
            return
        except Exception:
            pass
    await send_replacing_previous(
        application=application,
        chat_id=chat_id,
        text=text,
        reply_markup=keyboard,
        parse_mode=ParseMode.HTML,
        protect_content=settings.content_protection_enabled,
    )


async def render_step(
    application: Application,
    chat_id: int,
    step_code: str,
    telegram_user,
    *,
    event_type: str = "step_opened",
    event_payload: dict | None = None,
) -> None:
    with session_scope() as session:
        user = get_or_create_user(session, telegram_user)
        step = get_step_by_code(session, step_code)
        if step is None:
            return
        branches = get_branches_for_step(session, step.code)
        log_event(session, user, event_type, step.code, event_payload or {"step_title": step.title})
        text = html_message(step.title, step.body)
    keyboard = branch_keyboard(step, branches)
    if step.media_type and step.media_url:
        caption = html_media_caption(step.title, step.body, step.media_caption)
        try:
            await send_media_with_cleanup(
                application=application,
                chat_id=chat_id,
                media_type=step.media_type,
                media_url=step.media_url,
                caption=caption,
                reply_markup=keyboard,
                parse_mode=ParseMode.HTML,
                protect_content=settings.content_protection_enabled,
            )
            return
        except Exception:
            pass
    await send_replacing_previous(
        application=application,
        chat_id=chat_id,
        text=text,
        reply_markup=keyboard,
        parse_mode=ParseMode.HTML,
        protect_content=settings.content_protection_enabled,
    )


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    with session_scope() as session:
        user = get_or_create_user(session, update.effective_user)
        telegram_id = user.telegram_id
    await schedule_nurture_for_user(context.application, telegram_id)
    await render_first_step(context.application, update.effective_chat.id, update.effective_user)


async def navigation_user_id(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int | None:
    with session_scope() as session:
        user = get_or_create_user(session, update.effective_user)
        if should_rate_limit(user, settings.anti_spam_window_seconds, settings.anti_spam_burst_limit):
            log_event(session, user, "anti_spam_triggered", "rate_limited", {})
            rate_limited = True
        else:
            rate_limited = False
        telegram_id = user.telegram_id

    if rate_limited:
        await send_replacing_previous(
            application=context.application,
            chat_id=update.effective_chat.id,
            text="Слишком много действий подряд. Подожди несколько секунд.",
            protect_content=settings.content_protection_enabled,
        )
        return None
    return telegram_id


async def send_unavailable_transition(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await send_replacing_previous(
        application=context.application,
        chat_id=update.effective_chat.id,
        text="Этот переход уже изменен в админке. Нажми /start, чтобы открыть актуальную цепочку.",
        protect_content=settings.content_protection_enabled,
    )


async def on_branch_navigation(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    try:
        branch_id = int(query.data.split(":", 1)[1])
    except (TypeError, ValueError):
        await send_unavailable_transition(update, context)
        return
    with session_scope() as session:
        branch = get_branch_by_id(session, branch_id)
        target = get_step_by_code(session, branch.target_step_code) if branch else None
        step_code = target.code if target else None
    if not step_code:
        await send_unavailable_transition(update, context)
        return

    telegram_id = await navigation_user_id(update, context)
    if telegram_id is None:
        return
    await schedule_inactivity_automations(context.application, telegram_id, step_code)
    await render_step(context.application, update.effective_chat.id, step_code, update.effective_user, event_type="step_opened")


async def on_next_navigation(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    try:
        step_id = int(query.data.split(":", 1)[1])
    except (TypeError, ValueError):
        await send_unavailable_transition(update, context)
        return
    with session_scope() as session:
        step = get_step_by_id(session, step_id)
        target = get_step_by_code(session, step.next_step_code) if step and step.next_step_code else None
        step_code = target.code if target else None
    if not step_code:
        await send_unavailable_transition(update, context)
        return

    telegram_id = await navigation_user_id(update, context)
    if telegram_id is None:
        return
    await schedule_inactivity_automations(context.application, telegram_id, step_code)
    await render_step(context.application, update.effective_chat.id, step_code, update.effective_user, event_type="step_opened")


async def on_step_navigation(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    step_code = query.data.split(":", 1)[1]
    with session_scope() as session:
        target = get_step_by_code(session, step_code)
        resolved_step_code = target.code if target else None
    if not resolved_step_code:
        await send_unavailable_transition(update, context)
        return
    telegram_id = await navigation_user_id(update, context)
    if telegram_id is None:
        return
    await schedule_inactivity_automations(context.application, telegram_id, resolved_step_code)
    await render_step(context.application, update.effective_chat.id, resolved_step_code, update.effective_user, event_type="step_opened")


async def send_payment_link(update: Update, context: ContextTypes.DEFAULT_TYPE, *, step_code: str | None = None, step_id: int | None = None) -> bool:
    with session_scope() as session:
        user = get_or_create_user(session, update.effective_user)
        step = get_step_by_id(session, step_id) if step_id is not None else get_step_by_code(session, step_code or "")
        if step is None:
            return False
        resolved_step_code = step.code
        payment_payload = f"telegram_id={user.telegram_id};segment={user.segment_key};step={resolved_step_code}"
        offer = get_setting(session, "offer")
        payment = create_platega_payment_link(
            amount=int(offer.get("amount", 9900)),
            currency=str(offer.get("currency", "RUB")),
            description=str(offer.get("description", "Оплата оффера")),
            payload=payment_payload,
            payment_method=int(offer.get("payment_method", 2)),
        )
        create_payment_record(
            session,
            user=user,
            transaction_id=payment.get("transactionId"),
            status=str(payment.get("status", "pending")).lower(),
            amount=int(offer.get("amount", 9900)),
            currency=str(offer.get("currency", "RUB")),
            description=str(offer.get("description", "Оплата оффера")),
            payload={**payment, "local": {"telegram_id": user.telegram_id, "segment": user.segment_key, "step": resolved_step_code}},
        )
        log_event(session, user, "payment_started", resolved_step_code, {"transaction_id": payment.get("transactionId")})
        text = html_message(
            step.title if step else "Оплата",
            f"{offer.get('price_text', '')}\n\nСумма: {offer.get('amount', 9900)} {offer.get('currency', 'RUB')}",
        )
        keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("Перейти к оплате", url=payment["redirect"])]])
    await send_replacing_previous(
        application=context.application,
        chat_id=update.effective_chat.id,
        text=text,
        reply_markup=keyboard,
        parse_mode=ParseMode.HTML,
        protect_content=settings.content_protection_enabled,
    )
    return True


async def on_payment_by_step_id(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    try:
        step_id = int(query.data.split(":", 1)[1])
    except (TypeError, ValueError):
        await send_unavailable_transition(update, context)
        return
    if not await send_payment_link(update, context, step_id=step_id):
        await send_unavailable_transition(update, context)


async def on_payment(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    if not await send_payment_link(update, context, step_code=query.data.split(":", 1)[1]):
        await send_unavailable_transition(update, context)


async def on_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    incoming_text = update.effective_message.text or ""
    with session_scope() as session:
        user = get_or_create_user(session, update.effective_user)
        if should_rate_limit(user, settings.anti_spam_window_seconds, settings.anti_spam_burst_limit):
            log_event(session, user, "anti_spam_triggered", "rate_limited", {"text": incoming_text[:80]}, update_current=False)
            await send_replacing_previous(
                application=context.application,
                chat_id=update.effective_chat.id,
                text="Слишком много сообщений подряд. Подожди несколько секунд.",
                protect_content=settings.content_protection_enabled,
            )
            return
        trigger_step = get_step_by_trigger(session, incoming_text)
        if trigger_step is not None:
            step_code = trigger_step.code
            telegram_id = user.telegram_id
            trigger_payload = {"text": incoming_text[:200], "trigger_keywords": trigger_step.trigger_keywords}
        else:
            step_code = None
            telegram_id = user.telegram_id
            trigger_payload = None
            current_step = get_step_by_code(session, user.current_step) or get_segment_entry_step(session) or get_first_funnel_step(session)
            branches = get_branches_for_step(session, current_step.code) if current_step is not None else []
            copy = get_setting(session, "funnel_copy")
            text = copy.get("invalid_input", "Я тебя не понял, нажми на одну из кнопок ниже 👇")
            keyboard = branch_keyboard(current_step, branches) if current_step is not None else None
            log_event(
                session,
                user,
                "invalid_input",
                current_step.code if current_step is not None else (user.current_step or "fallback"),
                {"text": incoming_text[:200]},
                update_current=False,
            )
    if step_code:
        await schedule_inactivity_automations(context.application, telegram_id, step_code)
        await render_step(
            context.application,
            update.effective_chat.id,
            step_code,
            update.effective_user,
            event_type="keyword_trigger",
            event_payload=trigger_payload,
        )
        return
    await send_replacing_previous(
        application=context.application,
        chat_id=update.effective_chat.id,
        text=text,
        reply_markup=keyboard,
        protect_content=settings.content_protection_enabled,
    )


async def send_follow_up(context: ContextTypes.DEFAULT_TYPE) -> None:
    telegram_id = context.job.data["telegram_id"]
    follow_up_id = context.job.data["follow_up_id"]
    with session_scope() as session:
        user = session.scalar(select(User).where(User.telegram_id == telegram_id))
        if user is None:
            return
        message = session.scalar(select(FollowUpMessage).where(FollowUpMessage.id == follow_up_id))
        if message is None or user.is_customer:
            return
        log_event(session, user, "follow_up_sent", f"follow_up_{message.code}", {"code": message.code})
    await send_replacing_previous(
        application=context.application,
        chat_id=telegram_id,
        text=html_message(message.title, message.body),
        parse_mode=ParseMode.HTML,
        protect_content=settings.content_protection_enabled,
    )


async def schedule_nurture_for_user(application: Application, telegram_id: int) -> None:
    if not settings.nurture_enabled:
        return
    for job in application.job_queue.jobs():
        if job.name and job.name.startswith(f"followup:{telegram_id}:"):
            job.schedule_removal()
    with session_scope() as session:
        followups = get_followups(session)
    for item in followups:
        application.job_queue.run_once(
            send_follow_up,
            when=item.delay_hours * 3600,
            data={"telegram_id": telegram_id, "follow_up_id": item.id},
            name=f"followup:{telegram_id}:{item.code}",
        )


async def send_inactivity_bonus(context: ContextTypes.DEFAULT_TYPE) -> None:
    telegram_id = context.job.data["telegram_id"]
    rule_id = context.job.data["rule_id"]
    with session_scope() as session:
        user = session.scalar(select(User).where(User.telegram_id == telegram_id))
        if user is None or user.is_customer:
            return
        rule = session.scalar(select(AutomationRule).where(AutomationRule.id == rule_id, AutomationRule.is_active.is_(True)))
        if rule is None:
            return
        if rule.trigger_step and user.current_step != rule.trigger_step:
            return
        log_event(session, user, "inactivity_bonus_sent", rule.target_step_code or user.current_step, {"rule": rule.code})
    await send_replacing_previous(
        application=context.application,
        chat_id=telegram_id,
        text=html_message(rule.title, rule.body),
        parse_mode=ParseMode.HTML,
        protect_content=settings.content_protection_enabled,
    )


async def schedule_inactivity_automations(application: Application, telegram_id: int, current_step: str) -> None:
    for job in application.job_queue.jobs():
        if job.name and job.name.startswith(f"inactivity:{telegram_id}:"):
            job.schedule_removal()
    with session_scope() as session:
        rules = [
            rule for rule in get_automation_rules(session)
            if rule.trigger_type == "inactivity" and (rule.trigger_step is None or rule.trigger_step == current_step)
        ]
    for rule in rules:
        application.job_queue.run_once(
            send_inactivity_bonus,
            when=rule.inactivity_hours * 3600,
            data={
                "telegram_id": telegram_id,
                "rule_id": rule.id,
            },
            name=f"inactivity:{telegram_id}:{rule.code}",
        )


async def post_init(application: Application) -> None:
    await application.bot.set_chat_menu_button(menu_button=MenuButtonCommands())


def build_bot_application() -> Application:
    app = Application.builder().token(settings.bot_token).post_init(post_init).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(on_branch_navigation, pattern=r"^branch:"))
    app.add_handler(CallbackQueryHandler(on_next_navigation, pattern=r"^next:"))
    app.add_handler(CallbackQueryHandler(on_step_navigation, pattern=r"^goto:"))
    app.add_handler(CallbackQueryHandler(on_payment_by_step_id, pattern=r"^pay_step:"))
    app.add_handler(CallbackQueryHandler(on_payment, pattern=r"^pay:"))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, on_text))
    return app
