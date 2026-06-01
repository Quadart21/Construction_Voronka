import logging

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
from backend.invoice_control import check_crypto_invoice_creation, details_from_payment_record
from backend.noren import (
    NorenError,
    create_noren_invoice,
    crypto_provider_name,
    extract_invoice_details,
    noren_checkout_fiat,
    noren_price_label,
    format_noren_payment_text,
    get_admin_allowed_rates,
    is_allowed_crypto,
    invoice_payment_url,
    map_noren_status,
    new_merchant_order_id,
    rate_pair_key,
)
from backend.payment_settings import enabled_payment_methods, normalize_payment_settings
from backend.payments import create_platega_payment_link
from sqlalchemy import select

from backend.models import AutomationRule, FollowUpMessage, User
from backend.bot_context import bot_id_from
from backend.subscription_gate import (
    check_user_subscriptions,
    gate_is_active,
    normalize_gate,
    subscription_check_hint,
    subscription_keyboard,
)
from backend.services import (
    create_payment_record,
    get_automation_rules,
    get_branch_by_id,
    get_branches_for_step,
    get_first_funnel_step,
    get_first_post_payment_step,
    get_followups,
    get_or_create_user,
    get_segment_entry_step,
    get_setting,
    get_step_by_code,
    get_step_by_trigger,
    get_step_by_id,
    log_event,
    resolve_user_context_step,
    should_rate_limit,
    user_funnel_phase,
)


def is_valid_button_url(url: str | None) -> bool:
    value = str(url or "").strip()
    return value.startswith("http://") or value.startswith("https://")


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
        if branch.url and is_valid_button_url(branch.url):
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
    bot_id = bot_id_from(application)
    with session_scope() as session:
        user = get_or_create_user(session, telegram_user, bot_id)
        user.segment_key = None
        step = get_segment_entry_step(session, bot_id) or get_first_funnel_step(session, bot_id)
        if step is None:
            await send_replacing_previous(
                application=application,
                chat_id=chat_id,
                text="Цепочка пока пустая. Добавьте первый шаг в админке.",
                protect_content=settings.content_protection_enabled,
            )
            return
        branches = get_branches_for_step(session, step.code, bot_id)
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
    bot_id = bot_id_from(application)
    with session_scope() as session:
        user = get_or_create_user(session, telegram_user, bot_id)
        step = get_step_by_code(session, step_code, bot_id)
        if step is None:
            return
        branches = get_branches_for_step(session, step.code, bot_id)
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


async def subscription_gate_for_user(update: Update, context: ContextTypes.DEFAULT_TYPE) -> tuple[dict, bool]:
    bot_id = bot_id_from(context.application)
    with session_scope() as session:
        user = get_or_create_user(session, update.effective_user, bot_id)
        gate = normalize_gate(get_setting(session, "subscription_gate", bot_id))
        if not gate_is_active(gate):
            return gate, True
        if gate["skip_for_paid_users"] and user.is_customer:
            return gate, True
    subscribed, _missing = await check_user_subscriptions(
        context.application.bot,
        gate,
        update.effective_user.id,
    )
    return gate, subscribed


async def ensure_subscribed(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    gate, subscribed = await subscription_gate_for_user(update, context)
    if subscribed:
        return True
    await send_replacing_previous(
        application=context.application,
        chat_id=update.effective_chat.id,
        text=html_message("Нужна подписка", gate["message"]),
        reply_markup=subscription_keyboard(gate),
        parse_mode=ParseMode.HTML,
        protect_content=settings.content_protection_enabled,
    )
    return False


async def enter_funnel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    bot_id = bot_id_from(context.application)
    post_step_code = None
    with session_scope() as session:
        user = get_or_create_user(session, update.effective_user, bot_id)
        telegram_id = user.telegram_id
        if user.is_customer:
            post_step = get_first_post_payment_step(session, bot_id)
            if post_step is not None:
                post_step_code = post_step.code
    if post_step_code:
        await schedule_nurture_for_user(context.application, telegram_id)
        await render_step(
            context.application,
            update.effective_chat.id,
            post_step_code,
            update.effective_user,
            event_type="start",
        )
        return
    await schedule_nurture_for_user(context.application, telegram_id)
    await render_first_step(context.application, update.effective_chat.id, update.effective_user)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await ensure_subscribed(update, context):
        return
    await enter_funnel(update, context)


async def on_check_subscription(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    gate, subscribed = await subscription_gate_for_user(update, context)
    if subscribed:
        await query.answer("Подписка подтверждена. Открываю бот.")
        await enter_funnel(update, context)
        return
    _, missing = await check_user_subscriptions(context.application.bot, gate, update.effective_user.id)
    hint = subscription_check_hint(gate, missing)
    await query.answer(hint[:200], show_alert=True)


async def navigation_user_id(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int | None:
    bot_id = bot_id_from(context.application)
    with session_scope() as session:
        user = get_or_create_user(session, update.effective_user, bot_id)
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
    if not await ensure_subscribed(update, context):
        return
    try:
        branch_id = int(query.data.split(":", 1)[1])
    except (TypeError, ValueError):
        await send_unavailable_transition(update, context)
        return
    bot_id = bot_id_from(context.application)
    with session_scope() as session:
        branch = get_branch_by_id(session, branch_id, bot_id)
        target = get_step_by_code(session, branch.target_step_code, bot_id) if branch else None
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
    if not await ensure_subscribed(update, context):
        return
    try:
        step_id = int(query.data.split(":", 1)[1])
    except (TypeError, ValueError):
        await send_unavailable_transition(update, context)
        return
    bot_id = bot_id_from(context.application)
    with session_scope() as session:
        step = get_step_by_id(session, step_id, bot_id)
        target = get_step_by_code(session, step.next_step_code, bot_id) if step and step.next_step_code else None
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
    if not await ensure_subscribed(update, context):
        return
    step_code = query.data.split(":", 1)[1]
    bot_id = bot_id_from(context.application)
    with session_scope() as session:
        target = get_step_by_code(session, step_code, bot_id)
        resolved_step_code = target.code if target else None
    if not resolved_step_code:
        await send_unavailable_transition(update, context)
        return
    telegram_id = await navigation_user_id(update, context)
    if telegram_id is None:
        return
    await schedule_inactivity_automations(context.application, telegram_id, resolved_step_code)
    await render_step(context.application, update.effective_chat.id, resolved_step_code, update.effective_user, event_type="step_opened")


async def show_payment_method_choice(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    *,
    step_id: int,
) -> bool:
    bot_id = bot_id_from(context.application)
    with session_scope() as session:
        step = get_step_by_id(session, step_id, bot_id)
        if step is None:
            return False
        payment_cfg = normalize_payment_settings(get_setting(session, "payment", bot_id))
        offer = get_setting(session, "offer", bot_id)
        methods = enabled_payment_methods(payment_cfg)
        if not methods:
            await send_replacing_previous(
                application=context.application,
                chat_id=update.effective_chat.id,
                text=html_message(
                    "Оплата недоступна",
                    "Включите Platega или Noren в админке → Настройки → Способы оплаты.",
                ),
                parse_mode=ParseMode.HTML,
                protect_content=settings.content_protection_enabled,
            )
            return False
        if len(methods) == 1:
            only_method = methods[0]
        else:
            only_method = None
            rows = []
            if "platega" in methods:
                rows.append([InlineKeyboardButton("💳 Карта / СБП", callback_data=f"paym:platega:{step_id}")])
            if "noren" in methods:
                rows.append([InlineKeyboardButton("🪙 Криптовалюта", callback_data=f"paym:noren:{step_id}")])
            text = html_message(
                step.title,
                f"{offer.get('price_text', '')}\n\nВыберите способ оплаты:",
            )
    if only_method:
        return await start_payment_with_method(update, context, step_id=step_id, method=only_method)
    await send_replacing_previous(
        application=context.application,
        chat_id=update.effective_chat.id,
        text=text,
        reply_markup=InlineKeyboardMarkup(rows),
        parse_mode=ParseMode.HTML,
        protect_content=settings.content_protection_enabled,
    )
    return True


async def start_payment_with_method(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    *,
    step_id: int,
    method: str,
) -> bool:
    if method == "platega":
        return await send_platega_payment(update, context, step_id=step_id)
    if method == "noren":
        return await show_noren_crypto_choice(update, context, step_id=step_id)
    return False


async def show_noren_crypto_choice(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    *,
    step_id: int,
) -> bool:
    bot_id = bot_id_from(context.application)
    chat_id = update.effective_chat.id
    with session_scope() as session:
        step = get_step_by_id(session, step_id, bot_id)
        if step is None:
            return False
        step_title = step.title
        payment_cfg = normalize_payment_settings(get_setting(session, "payment", bot_id))
        offer = get_setting(session, "offer", bot_id)
        offer_price_text = str(offer.get("price_text") or "")
        noren = payment_cfg["noren"]

    try:
        rates = get_admin_allowed_rates(noren=noren)
    except NorenError as exc:
        await send_replacing_previous(
            application=context.application,
            chat_id=chat_id,
            text=html_message("Оплата криптой", str(exc)),
            parse_mode=ParseMode.HTML,
            protect_content=settings.content_protection_enabled,
        )
        return False
    if not rates:
        await send_replacing_previous(
            application=context.application,
            chat_id=chat_id,
            text=html_message(
                "Оплата криптой",
                "Админ не выбрал доступные криптовалюты. Отметьте их в админке → Настройки → Способы оплаты → Noren.",
            ),
            parse_mode=ParseMode.HTML,
            protect_content=settings.content_protection_enabled,
        )
        return False
    try:
        price_label = noren_price_label(noren)
    except NorenError as exc:
        await send_replacing_previous(
            application=context.application,
            chat_id=chat_id,
            text=html_message("Оплата криптой", str(exc)),
            parse_mode=ParseMode.HTML,
            protect_content=settings.content_protection_enabled,
        )
        return False
    if len(rates) == 1:
        rate = rates[0]
        return await send_noren_payment(
            update,
            context,
            step_id=step_id,
            crypto_currency=rate["currency"],
            network=rate["network"],
        )
    rows = [
        [
            InlineKeyboardButton(
                f"🪙 {rate['label']}",
                callback_data=f"payc:{step_id}:{rate_pair_key(rate['currency'], rate['network'])}",
            )
        ]
        for rate in rates
    ]
    text = html_message(
        step_title,
        f"{offer_price_text}\n\n"
        f"Сумма: <b>{price_label}</b>\n\n"
        "Выберите криптовалюту для оплаты:",
    )
    await send_replacing_previous(
        application=context.application,
        chat_id=chat_id,
        text=text,
        reply_markup=InlineKeyboardMarkup(rows),
        parse_mode=ParseMode.HTML,
        protect_content=settings.content_protection_enabled,
    )
    return True


async def send_platega_payment(update: Update, context: ContextTypes.DEFAULT_TYPE, *, step_id: int) -> bool:
    bot_id = bot_id_from(context.application)
    with session_scope() as session:
        user = get_or_create_user(session, update.effective_user, bot_id)
        step = get_step_by_id(session, step_id, bot_id)
        if step is None:
            return False
        resolved_step_code = step.code
        payment_payload = f"bot_id={bot_id};telegram_id={user.telegram_id};segment={user.segment_key};step={resolved_step_code}"
        offer = get_setting(session, "offer", bot_id)
        try:
            payment = create_platega_payment_link(
                amount=int(offer.get("amount", 9900)),
                currency=str(offer.get("currency", "RUB")),
                description=str(offer.get("description", "Оплата оффера")),
                payload=payment_payload,
                payment_method=int(offer.get("payment_method", 2)),
            )
        except RuntimeError as exc:
            await send_replacing_previous(
                application=context.application,
                chat_id=update.effective_chat.id,
                text=html_message("Оплата картой", str(exc)),
                parse_mode=ParseMode.HTML,
                protect_content=settings.content_protection_enabled,
            )
            return False
        create_payment_record(
            session,
            user=user,
            transaction_id=payment.get("transactionId"),
            status=str(payment.get("status", "pending")).lower(),
            amount=int(offer.get("amount", 9900)),
            currency=str(offer.get("currency", "RUB")),
            description=str(offer.get("description", "Оплата оффера")),
            payload={
                **payment,
                "provider": "platega",
                "local": {
                    "bot_id": bot_id,
                    "telegram_id": user.telegram_id,
                    "segment": user.segment_key,
                    "step": resolved_step_code,
                },
            },
            provider="platega",
        )
        log_event(session, user, "payment_started", resolved_step_code, {"transaction_id": payment.get("transactionId"), "provider": "platega"})
        text = html_message(
            step.title,
            f"{offer.get('price_text', '')}\n\nСумма: {offer.get('amount', 9900) / 100:.2f} {offer.get('currency', 'RUB')}",
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


def build_noren_payment_message(details: dict[str, str], *, reused: bool = False) -> tuple[str, InlineKeyboardMarkup | None]:
    title, _ = format_noren_payment_text(details)
    body = f"<b>{details['amount_crypto']} {details['crypto_currency']}</b> · {details['network']}"
    if details.get("amount_fiat") and details.get("fiat_currency"):
        body += f"\n≈ {details['amount_fiat']} {details['fiat_currency']}"
    if details.get("payment_address"):
        body += f"\nАдрес: <code>{details['payment_address']}</code>"
    if details.get("expires_label"):
        body += f"\nСрок: {details['expires_label']}"
    if reused:
        body += "\n\n<i>Активный счёт — новая заявка не создана.</i>"
    text = html_message(title, body)
    rows = []
    payment_url = invoice_payment_url(details)
    if payment_url:
        rows.append([InlineKeyboardButton("Перейти к оплате", url=payment_url)])
    qr_url = str(details.get("qr_url") or "").strip()
    page_url = str(details.get("payment_page_url") or "").strip()
    if qr_url.startswith(("http://", "https://")) and qr_url != page_url:
        rows.append([InlineKeyboardButton("Открыть QR", url=qr_url)])
    keyboard = InlineKeyboardMarkup(rows) if rows else None
    return text, keyboard


async def send_noren_payment(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    *,
    step_id: int,
    crypto_currency: str,
    network: str,
) -> bool:
    bot_id = bot_id_from(context.application)
    chat_id = update.effective_chat.id
    currency = str(crypto_currency or "").strip().upper()
    network_code = str(network or "").strip().upper()
    noren: dict
    resolved_step_code: str
    user_telegram_id: int
    user_segment: str | None
    with session_scope() as session:
        user = get_or_create_user(session, update.effective_user, bot_id)
        step = get_step_by_id(session, step_id, bot_id)
        if step is None:
            return False
        resolved_step_code = step.code
        user_telegram_id = user.telegram_id
        user_segment = user.segment_key
        payment_cfg = normalize_payment_settings(get_setting(session, "payment", bot_id))
        noren = payment_cfg["noren"]
        if not is_allowed_crypto(noren=noren, crypto_currency=currency, network=network_code):
            await send_replacing_previous(
                application=context.application,
                chat_id=chat_id,
                text=html_message("Оплата криптой", "Эта криптовалюта недоступна для оплаты."),
                parse_mode=ParseMode.HTML,
                protect_content=settings.content_protection_enabled,
            )
            return False
        try:
            amount_fiat, fiat_currency = noren_checkout_fiat(noren)
        except NorenError as exc:
            await send_replacing_previous(
                application=context.application,
                chat_id=chat_id,
                text=html_message("Оплата криптой", str(exc)),
                parse_mode=ParseMode.HTML,
                protect_content=settings.content_protection_enabled,
            )
            return False
        decision = check_crypto_invoice_creation(session, user=user, bot_id=bot_id, limits=noren)
        if decision.action == "blocked":
            await send_replacing_previous(
                application=context.application,
                chat_id=chat_id,
                text=html_message("Оплата криптой", decision.message),
                parse_mode=ParseMode.HTML,
                protect_content=settings.content_protection_enabled,
            )
            log_event(session, user, "invoice_blocked", resolved_step_code, {"reason": decision.message})
            return False
        if decision.action == "reuse" and decision.record is not None:
            try:
                details = details_from_payment_record(decision.record)
            except ValueError:
                details = None
            if details is not None:
                log_event(
                    session,
                    user,
                    "invoice_reused",
                    resolved_step_code,
                    {"transaction_id": details["merchant_order_id"]},
                )
                text, keyboard = build_noren_payment_message(details, reused=True)
                await send_replacing_previous(
                    application=context.application,
                    chat_id=chat_id,
                    text=text,
                    reply_markup=keyboard,
                    parse_mode=ParseMode.HTML,
                    protect_content=settings.content_protection_enabled,
                )
                return True

    merchant_order_id = new_merchant_order_id()
    local_meta = {
        "bot_id": bot_id,
        "telegram_id": user_telegram_id,
        "segment": user_segment,
        "step": resolved_step_code,
        "merchant_order_id": merchant_order_id,
        "crypto_currency": currency,
        "network": network_code,
    }
    try:
        invoice = create_noren_invoice(
            noren=noren,
            merchant_order_id=merchant_order_id,
            crypto_currency=currency,
            network=network_code,
            amount_fiat=amount_fiat,
            fiat_currency=fiat_currency,
            metadata=local_meta,
        )
    except NorenError as exc:
        await send_replacing_previous(
            application=context.application,
            chat_id=chat_id,
            text=html_message("Оплата криптой", str(exc)),
            parse_mode=ParseMode.HTML,
            protect_content=settings.content_protection_enabled,
        )
        return False
    try:
        details = extract_invoice_details(invoice)
    except NorenError as exc:
        await send_replacing_previous(
            application=context.application,
            chat_id=chat_id,
            text=html_message("Оплата криптой", str(exc)),
            parse_mode=ParseMode.HTML,
            protect_content=settings.content_protection_enabled,
        )
        return False
    provider = crypto_provider_name()
    order_id = details["merchant_order_id"]
    with session_scope() as session:
        user = get_or_create_user(session, update.effective_user, bot_id)
        create_payment_record(
            session,
            user=user,
            transaction_id=order_id,
            status=map_noren_status(str(invoice.get("status"))),
            amount=0,
            currency=details["crypto_currency"],
            description=order_id,
            payload={
                "provider": provider,
                "invoice": invoice,
                "invoice_id": details["invoice_id"],
                "merchant_order_id": order_id,
                "amount_crypto": details["amount_crypto"],
                "crypto_currency": details["crypto_currency"],
                "network": details["network"],
                "payment_address": details["payment_address"],
                "qr_url": details["qr_url"],
                "payment_page_url": details["payment_page_url"],
                "amount_fiat": details["amount_fiat"],
                "fiat_currency": details["fiat_currency"],
                "expires_at": details["expires_at"],
                "local": local_meta,
            },
            provider=provider,
        )
        log_event(
            session,
            user,
            "payment_started",
            resolved_step_code,
            {"transaction_id": order_id, "provider": provider, "merchant_order_id": order_id},
        )
    text, keyboard = build_noren_payment_message(details)
    await send_replacing_previous(
        application=context.application,
        chat_id=chat_id,
        text=text,
        reply_markup=keyboard,
        parse_mode=ParseMode.HTML,
        protect_content=settings.content_protection_enabled,
    )
    return True


async def send_payment_link(update: Update, context: ContextTypes.DEFAULT_TYPE, *, step_code: str | None = None, step_id: int | None = None) -> bool:
    bot_id = bot_id_from(context.application)
    with session_scope() as session:
        step = get_step_by_id(session, step_id, bot_id) if step_id is not None else get_step_by_code(session, step_code or "", bot_id)
        if step is None:
            return False
        resolved_step_id = step.id
    return await show_payment_method_choice(update, context, step_id=resolved_step_id)


async def on_noren_crypto_choice(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    if not await ensure_subscribed(update, context):
        return
    try:
        parts = query.data.split(":")
        if len(parts) >= 4 and parts[0] == "payc":
            step_id = int(parts[1])
            crypto_currency = parts[2]
            network = ":".join(parts[3:])
        elif len(parts) == 3 and parts[0] == "payc":
            step_id = int(parts[1])
            crypto_currency, network = parts[2].split("|", 1)
        else:
            raise ValueError("invalid callback")
    except (TypeError, ValueError):
        await send_unavailable_transition(update, context)
        return
    if not crypto_currency.strip() or not network.strip():
        await send_unavailable_transition(update, context)
        return
    if not await send_noren_payment(
        update,
        context,
        step_id=step_id,
        crypto_currency=crypto_currency,
        network=network,
    ):
        await send_unavailable_transition(update, context)


async def on_payment_method(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    if not await ensure_subscribed(update, context):
        return
    try:
        _, method, step_id_raw = query.data.split(":", 2)
        step_id = int(step_id_raw)
    except (TypeError, ValueError):
        await send_unavailable_transition(update, context)
        return
    if method not in {"platega", "noren"}:
        await send_unavailable_transition(update, context)
        return
    if not await start_payment_with_method(update, context, step_id=step_id, method=method):
        await send_unavailable_transition(update, context)


async def on_payment_by_step_id(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    if not await ensure_subscribed(update, context):
        return
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
    if not await ensure_subscribed(update, context):
        return
    if not await send_payment_link(update, context, step_code=query.data.split(":", 1)[1]):
        await send_unavailable_transition(update, context)


async def on_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    incoming_text = update.effective_message.text or ""
    if not await ensure_subscribed(update, context):
        return
    bot_id = bot_id_from(context.application)
    with session_scope() as session:
        user = get_or_create_user(session, update.effective_user, bot_id)
        if should_rate_limit(user, settings.anti_spam_window_seconds, settings.anti_spam_burst_limit):
            log_event(session, user, "anti_spam_triggered", "rate_limited", {"text": incoming_text[:80]}, update_current=False)
            await send_replacing_previous(
                application=context.application,
                chat_id=update.effective_chat.id,
                text="Слишком много сообщений подряд. Подожди несколько секунд.",
                protect_content=settings.content_protection_enabled,
            )
            return
        phase = user_funnel_phase(user)
        trigger_step = get_step_by_trigger(session, incoming_text, bot_id, funnel_phase=phase)
        if trigger_step is not None:
            step_code = trigger_step.code
            telegram_id = user.telegram_id
            trigger_payload = {"text": incoming_text[:200], "trigger_keywords": trigger_step.trigger_keywords}
        else:
            step_code = None
            telegram_id = user.telegram_id
            trigger_payload = None
            current_step = resolve_user_context_step(session, user, bot_id)
            branches = get_branches_for_step(session, current_step.code, bot_id) if current_step is not None else []
            copy = get_setting(session, "funnel_copy", bot_id)
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
    bot_id = int(context.job.data["bot_id"])
    with session_scope() as session:
        user = session.scalar(select(User).where(User.bot_id == bot_id, User.telegram_id == telegram_id))
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
    bot_id = bot_id_from(application)
    for job in application.job_queue.jobs():
        if job.name and job.name.startswith(f"followup:{bot_id}:{telegram_id}:"):
            job.schedule_removal()
    with session_scope() as session:
        followups = get_followups(session, bot_id)
    for item in followups:
        application.job_queue.run_once(
            send_follow_up,
            when=item.delay_hours * 3600,
            data={"telegram_id": telegram_id, "follow_up_id": item.id, "bot_id": bot_id},
            name=f"followup:{bot_id}:{telegram_id}:{item.code}",
        )


async def send_inactivity_bonus(context: ContextTypes.DEFAULT_TYPE) -> None:
    telegram_id = context.job.data["telegram_id"]
    rule_id = context.job.data["rule_id"]
    bot_id = int(context.job.data["bot_id"])
    with session_scope() as session:
        user = session.scalar(select(User).where(User.bot_id == bot_id, User.telegram_id == telegram_id))
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
    bot_id = bot_id_from(application)
    for job in application.job_queue.jobs():
        if job.name and job.name.startswith(f"inactivity:{bot_id}:{telegram_id}:"):
            job.schedule_removal()
    with session_scope() as session:
        rules = [
            rule
            for rule in get_automation_rules(session, bot_id)
            if rule.trigger_type == "inactivity" and (rule.trigger_step is None or rule.trigger_step == current_step)
        ]
    for rule in rules:
        application.job_queue.run_once(
            send_inactivity_bonus,
            when=rule.inactivity_hours * 3600,
            data={
                "telegram_id": telegram_id,
                "rule_id": rule.id,
                "bot_id": bot_id,
            },
            name=f"inactivity:{bot_id}:{telegram_id}:{rule.code}",
        )


async def post_init(application: Application, bot_id: int) -> None:
    application.bot_data["bot_id"] = int(bot_id)
    await application.bot.set_chat_menu_button(menu_button=MenuButtonCommands())


logger = logging.getLogger(__name__)


async def on_handler_error(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    logger.exception("Telegram handler error", exc_info=context.error)
    if not isinstance(update, Update):
        return
    chat_id = update.effective_chat.id if update.effective_chat else None
    if chat_id is None:
        return
    if update.callback_query:
        try:
            await update.callback_query.answer("Ошибка. Попробуйте снова или /start", show_alert=True)
        except Exception:
            pass
    try:
        await send_replacing_previous(
            application=context.application,
            chat_id=chat_id,
            text=html_message("Ошибка", "Что-то пошло не так. Нажмите /start или попробуйте позже."),
            parse_mode=ParseMode.HTML,
            protect_content=settings.content_protection_enabled,
        )
    except Exception:
        pass


def build_bot_application(token: str, bot_id: int) -> Application:
    app = Application.builder().token(token).post_init(lambda application: post_init(application, bot_id)).build()
    app.bot_data["bot_id"] = int(bot_id)
    app.add_error_handler(on_handler_error)
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(on_check_subscription, pattern=r"^check_sub$"))
    app.add_handler(CallbackQueryHandler(on_branch_navigation, pattern=r"^branch:"))
    app.add_handler(CallbackQueryHandler(on_next_navigation, pattern=r"^next:"))
    app.add_handler(CallbackQueryHandler(on_step_navigation, pattern=r"^goto:"))
    app.add_handler(CallbackQueryHandler(on_payment_method, pattern=r"^paym:"))
    app.add_handler(CallbackQueryHandler(on_noren_crypto_choice, pattern=r"^payc:"))
    app.add_handler(CallbackQueryHandler(on_payment_by_step_id, pattern=r"^pay_step:"))
    app.add_handler(CallbackQueryHandler(on_payment, pattern=r"^pay:"))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, on_text))
    return app
