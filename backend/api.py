from datetime import datetime
import shutil

import jwt
from fastapi import BackgroundTasks, Depends, FastAPI, File, Header, HTTPException, Query, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from fastapi.staticfiles import StaticFiles
from sqlalchemy import delete, func, inspect, select, text
from telegram import Bot

from backend.admin_auth import (
    AdminCtx,
    bootstrap_env_admin_if_empty,
    confirm_2fa_setup,
    hash_password,
    load_admin_ctx,
    login_with_password,
    verify_2fa_login,
)
from backend.config import settings
from backend.database import Base, engine, session_scope
from backend.post_payment import deliver_after_payment
from backend.runtime import get_bot_application
from backend.leads_notify import notify_admins_about_lead
from backend.media import safe_upload_name
from backend.bot_manager import reload_bot
from backend.deps import mask_bot_token, resolve_bot_id
from backend.models import (
    AdminUser,
    AppSetting,
    AutomationRule,
    FollowUpMessage,
    FunnelBranch,
    FunnelEvent,
    FunnelStep,
    Lead,
    PaymentRecord,
    Segment,
    TelegramBot,
    User,
)
from backend.multi_bot_migrate import ensure_multi_bot_schema
from backend.seed import seed_bot_defaults
from backend.schemas import (
    AccountingSummary,
    AdminCreateIn,
    AdminUserOut,
    AuthConfirmSetupIn,
    AuthLoginIn,
    AuthMeOut,
    AuthVerifyTotpIn,
    AutomationRuleIn,
    AutomationRuleOut,
    ConversionReport,
    DashboardStats,
    EventOut,
    FollowUpIn,
    FollowUpOut,
    LeadCreateIn,
    LeadOut,
    LeadPatchIn,
    TelegramBotIn,
    TelegramBotOut,
    TelegramBotUpdateIn,
    FunnelBranchIn,
    FunnelBranchOut,
    FunnelStepIn,
    FunnelStepOut,
    SegmentIn,
    SegmentOut,
    UserOut,
)
from backend.seed import seed_defaults
from backend.services import get_accounting_summary, get_conversion_report, get_dashboard_stats, get_setting, log_event, set_setting

security_bearer = HTTPBearer(auto_error=False)
settings.upload_dir.mkdir(parents=True, exist_ok=True)
app = FastAPI(title=settings.app_name)
app.mount("/uploads", StaticFiles(directory=settings.upload_dir), name="uploads")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


PLATEGA_STATUS_MAP = {
    "CONFIRMED": "paid",
    "SUCCESS": "paid",
    "SUCCEEDED": "paid",
    "PAID": "paid",
    "COMPLETED": "paid",
    "COMPLETE": "paid",
    "APPROVED": "paid",
    "PENDING": "pending",
    "CANCELED": "failed",
    "CANCELLED": "failed",
    "FAILED": "failed",
    "DECLINED": "failed",
    "CHARGEBACKED": "refunded",
    "REFUNDED": "refunded",
}


def ensure_runtime_columns() -> None:
    inspector = inspect(engine)
    if "funnel_steps" not in inspector.get_table_names():
        return
    columns = {column["name"] for column in inspector.get_columns("funnel_steps")}
    if "trigger_keywords" not in columns:
        with engine.begin() as connection:
            connection.execute(text("ALTER TABLE funnel_steps ADD COLUMN trigger_keywords TEXT"))
    if "funnel_phase" not in columns:
        with engine.begin() as connection:
            connection.execute(text("ALTER TABLE funnel_steps ADD COLUMN funnel_phase VARCHAR(32) DEFAULT 'main'"))
            connection.execute(text("UPDATE funnel_steps SET funnel_phase = 'main' WHERE funnel_phase IS NULL OR funnel_phase = ''"))


def payment_payload_meta(payload: dict | None) -> dict:
    data = payload or {}
    local = data.get("local")
    if isinstance(local, dict):
        return local
    raw = str(data.get("payload") or "")
    result = {}
    for chunk in raw.split(";"):
        if "=" not in chunk:
            continue
        key, value = chunk.split("=", 1)
        result[key.strip()] = value.strip()
    return result


def inject_admin_ctx(
    credentials: HTTPAuthorizationCredentials | None = Depends(security_bearer),
) -> AdminCtx:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(status_code=401, detail="Unauthorized")
    try:
        return load_admin_ctx(credentials.credentials)
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Session expired, sign in again")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid or expired session")


@app.on_event("startup")
def startup() -> None:
    from backend.bootstrap import bootstrap_application

    bootstrap_application()
    with session_scope() as session:
        bootstrap_env_admin_if_empty(session)


@app.get("/api/health")
def health():
    from backend.bootstrap import active_bot_count

    return {
        "ok": True,
        "version": settings.app_version,
        "active_bots": active_bot_count(),
        "time": datetime.utcnow().isoformat(),
    }


def _bot_to_out(bot: TelegramBot) -> TelegramBotOut:
    return TelegramBotOut(
        id=bot.id,
        name=bot.name,
        username=bot.username,
        token_masked=mask_bot_token(bot.token),
        is_active=bot.is_active,
        sort_order=bot.sort_order,
        created_at=bot.created_at,
    )


async def _fetch_bot_username(token: str) -> str | None:
    token = token.strip()
    if not token:
        return None
    try:
        async with Bot(token) as bot:
            me = await bot.get_me()
            return me.username
    except Exception:
        return None


@app.get("/api/bots", response_model=list[TelegramBotOut], dependencies=[Depends(inject_admin_ctx)])
def list_bots():
    with session_scope() as session:
        bots = list(session.scalars(select(TelegramBot).order_by(TelegramBot.sort_order, TelegramBot.id)))
        return [_bot_to_out(bot) for bot in bots]


@app.post("/api/bots", response_model=TelegramBotOut, dependencies=[Depends(inject_admin_ctx)])
async def create_bot(payload: TelegramBotIn, background_tasks: BackgroundTasks):
    name = payload.name.strip()
    token = payload.token.strip()
    if len(name) < 2:
        raise HTTPException(status_code=400, detail="Укажите название бота")
    if len(token) < 20:
        raise HTTPException(status_code=400, detail="Укажите корректный токен от @BotFather")
    username = await _fetch_bot_username(token)
    with session_scope() as session:
        entity = TelegramBot(name=name[:128], token=token, username=username, is_active=payload.is_active, sort_order=payload.sort_order)
        session.add(entity)
        session.flush()
        bot_id = int(entity.id)
        seed_bot_defaults(bot_id)
        result = _bot_to_out(entity)
    background_tasks.add_task(reload_bot, bot_id)
    return result


@app.put("/api/bots/{bot_id}", response_model=TelegramBotOut, dependencies=[Depends(inject_admin_ctx)])
async def update_bot(bot_id: int, payload: TelegramBotUpdateIn, background_tasks: BackgroundTasks):
    with session_scope() as session:
        entity = session.get(TelegramBot, bot_id)
        if entity is None:
            raise HTTPException(status_code=404, detail="Бот не найден")
        if payload.name is not None:
            entity.name = payload.name.strip()[:128]
        if payload.token is not None:
            token = payload.token.strip()
            if len(token) < 20:
                raise HTTPException(status_code=400, detail="Укажите корректный токен")
            entity.token = token
            entity.username = await _fetch_bot_username(token)
        if payload.is_active is not None:
            entity.is_active = payload.is_active
        if payload.sort_order is not None:
            entity.sort_order = payload.sort_order
        session.flush()
        result = _bot_to_out(entity)
    background_tasks.add_task(reload_bot, bot_id)
    return result


@app.delete("/api/bots/{bot_id}", dependencies=[Depends(inject_admin_ctx)])
async def delete_bot(bot_id: int, background_tasks: BackgroundTasks):
    with session_scope() as session:
        entity = session.get(TelegramBot, bot_id)
        if entity is None:
            raise HTTPException(status_code=404, detail="Бот не найден")
        others = session.scalar(select(func.count(TelegramBot.id)).where(TelegramBot.id != bot_id)) or 0
        if others < 1:
            raise HTTPException(status_code=400, detail="Нельзя удалить последнего бота")
        entity.is_active = False
    background_tasks.add_task(reload_bot, bot_id)
    return {"ok": True}


@app.post("/api/public/leads", response_model=LeadOut)
async def public_create_lead(payload: LeadCreateIn, request: Request, background_tasks: BackgroundTasks):
    full_name = payload.full_name.strip()
    email = payload.email.strip()
    phone = payload.phone.strip()
    if len(full_name) < 2:
        raise HTTPException(status_code=400, detail="Укажите имя")
    if "@" not in email or len(email) < 5:
        raise HTTPException(status_code=400, detail="Укажите корректный email")
    if len(phone) < 6:
        raise HTTPException(status_code=400, detail="Укажите телефон")
    company = (payload.company or "").strip() or None
    message = (payload.message or "").strip() or None
    if company and len(company) > 250:
        company = company[:250]
    if message and len(message) > 4000:
        message = message[:4000]
    client_host = request.client.host if request.client else None
    ua = (request.headers.get("user-agent") or "")[:500]
    with session_scope() as session:
        lead = Lead(
            full_name=full_name[:255],
            email=email[:255],
            phone=phone[:64],
            company=company,
            message=message,
            source="landing",
            ip_address=client_host,
            user_agent=ua or None,
        )
        session.add(lead)
        session.flush()
        lead_id = lead.id
    background_tasks.add_task(notify_admins_about_lead, lead_id)
    with session_scope() as session:
        saved = session.get(Lead, lead_id)
        if saved is None:
            raise HTTPException(status_code=500, detail="Не удалось сохранить заявку")
        return saved


@app.get("/api/leads", response_model=list[LeadOut], dependencies=[Depends(inject_admin_ctx)])
def list_leads():
    with session_scope() as session:
        return list(session.scalars(select(Lead).order_by(Lead.created_at.desc()).limit(500)))


@app.patch("/api/leads/{lead_id}", response_model=LeadOut, dependencies=[Depends(inject_admin_ctx)])
def patch_lead(lead_id: int, payload: LeadPatchIn):
    st = (payload.status or "processed").strip()[:32]
    if not st:
        st = "processed"
    with session_scope() as session:
        lead = session.get(Lead, lead_id)
        if lead is None:
            raise HTTPException(status_code=404, detail="Не найдено")
        lead.status = st
        session.flush()
        return lead


@app.post("/api/auth/login")
def auth_login(payload: AuthLoginIn):
    with session_scope() as session:
        result = login_with_password(session, payload.username, payload.password)
    if result["status"] == "invalid":
        raise HTTPException(status_code=401, detail="Неверный логин или пароль")
    return result


@app.post("/api/auth/verify-2fa")
def auth_verify_2fa(payload: AuthVerifyTotpIn):
    try:
        with session_scope() as session:
            access_token = verify_2fa_login(session, payload.partial_token, payload.code)
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Сессия ввода кода истекла, войдите снова")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Неверный токен")
    except ValueError as exc:
        if str(exc) == "invalid_totp":
            raise HTTPException(status_code=400, detail="Неверный код из приложения")
        raise HTTPException(status_code=400, detail="Не удалось подтвердить вход")
    return {"access_token": access_token}


@app.post("/api/auth/confirm-2fa-setup")
def auth_confirm_2fa_setup(payload: AuthConfirmSetupIn):
    try:
        with session_scope() as session:
            access_token = confirm_2fa_setup(session, payload.setup_token, payload.code)
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Время настройки истекло, войдите снова")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Неверный токен настройки")
    except ValueError as exc:
        msg = str(exc)
        if msg == "invalid_totp":
            raise HTTPException(status_code=400, detail="Проверьте код из приложения")
        if msg in {"invalid_setup_token", "user_missing"}:
            raise HTTPException(status_code=400, detail="Сессия настройки недействительна, войдите снова")
        raise HTTPException(status_code=400, detail=msg)
    return {"access_token": access_token}


@app.get("/api/auth/me", response_model=AuthMeOut)
def auth_me(ctx: AdminCtx = Depends(inject_admin_ctx)):
    return AuthMeOut(id=ctx.id, username=ctx.username)


@app.get("/api/admins", response_model=list[AdminUserOut])
def list_admins(_ctx: AdminCtx = Depends(inject_admin_ctx)):
    with session_scope() as session:
        return list(session.scalars(select(AdminUser).order_by(AdminUser.id)))


@app.post("/api/admins", response_model=AdminUserOut)
def create_admin(payload: AdminCreateIn, _ctx: AdminCtx = Depends(inject_admin_ctx)):
    username = payload.username.strip()
    if len(username) < 2:
        raise HTTPException(status_code=400, detail="Слишком короткий логин")
    if len(payload.password) < 8:
        raise HTTPException(status_code=400, detail="Пароль не короче 8 символов")
    with session_scope() as session:
        if session.scalar(select(AdminUser.id).where(AdminUser.username == username)):
            raise HTTPException(status_code=409, detail="Такой логин уже есть")
        entity = AdminUser(
            username=username,
            password_hash=hash_password(payload.password),
            totp_secret=None,
            totp_confirmed=False,
            is_active=True,
        )
        session.add(entity)
        session.flush()
        return entity


@app.delete("/api/admins/{admin_id}")
def delete_admin(admin_id: int, ctx: AdminCtx = Depends(inject_admin_ctx)):
    if ctx.id == admin_id:
        raise HTTPException(status_code=400, detail="Нельзя удалить самого себя")
    with session_scope() as session:
        active_n = session.scalar(select(func.count(AdminUser.id)).where(AdminUser.is_active.is_(True))) or 0
        if active_n <= 1:
            raise HTTPException(status_code=400, detail="Нельзя удалить последнего администратора")
        admin = session.get(AdminUser, admin_id)
        if admin is None:
            raise HTTPException(status_code=404, detail="Not found")
        admin.is_active = False
    return {"ok": True}


@app.post("/api/uploads", dependencies=[Depends(inject_admin_ctx)])
async def upload_media(file: UploadFile = File(...)):
    filename = safe_upload_name(file.filename or "upload.bin")
    target = settings.upload_dir / filename
    with target.open("wb") as output:
        shutil.copyfileobj(file.file, output)
    await file.close()
    return {
        "filename": filename,
        "media_url": f"upload://{filename}",
        "public_url": f"/uploads/{filename}",
        "content_type": file.content_type,
    }


@app.get("/api/dashboard", response_model=DashboardStats, dependencies=[Depends(inject_admin_ctx)])
def dashboard(bot_id: int = Depends(resolve_bot_id)):
    return get_dashboard_stats(bot_id)


@app.get("/api/conversions", response_model=ConversionReport, dependencies=[Depends(inject_admin_ctx)])
def conversions(bot_id: int = Depends(resolve_bot_id)):
    return get_conversion_report(bot_id)


@app.get("/api/accounting", response_model=AccountingSummary, dependencies=[Depends(inject_admin_ctx)])
def accounting(bot_id: int = Depends(resolve_bot_id)):
    return get_accounting_summary(bot_id)


@app.post("/api/webhooks/platega")
async def platega_webhook(
    request: Request,
    x_merchant_id: str | None = Header(default=None, alias="X-MerchantId"),
    x_secret: str | None = Header(default=None, alias="X-Secret"),
):
    if settings.platega_merchant_id and x_merchant_id != settings.platega_merchant_id:
        raise HTTPException(status_code=401, detail="Invalid merchant")
    if settings.platega_secret and x_secret != settings.platega_secret:
        raise HTTPException(status_code=401, detail="Invalid secret")

    payload = await request.json()
    transaction_id = str(payload.get("id") or payload.get("transactionId") or "").strip()
    external_status = str(payload.get("status") or "").upper()
    status = PLATEGA_STATUS_MAP.get(external_status, external_status.lower() or "unknown")
    delivery_target: int | None = None
    delivery_bot_id: int | None = None

    with session_scope() as session:
        record = session.scalar(select(PaymentRecord).where(PaymentRecord.transaction_id == transaction_id)) if transaction_id else None
        if record is None:
            return {"ok": True, "matched": False}

        previous_status = record.status
        record.status = status
        record.amount = int(payload.get("amount") or record.amount or 0)
        record.currency = str(payload.get("currency") or record.currency or "RUB")
        record.payload = {**(record.payload or {}), "webhook": payload}

        record_bot_id = int(record.bot_id or 1)
        payment_meta = payment_payload_meta(record.payload)
        if payment_meta.get("bot_id"):
            record_bot_id = int(payment_meta["bot_id"])
        user = (
            session.get(User, record.user_id)
            if record.user_id
            else session.scalar(select(User).where(User.bot_id == record_bot_id, User.telegram_id == record.telegram_id))
        )
        paid_step = str(payment_meta.get("step") or user.current_step if user else "payment").strip() or "payment"
        if user and status == "paid":
            user.is_customer = True
            if previous_status != "paid":
                log_event(session, user, "payment_paid", paid_step, {"transaction_id": transaction_id})
            if not (record.payload or {}).get("delivery_sent_at"):
                delivery_target = user.telegram_id
                delivery_bot_id = record_bot_id
        elif user and status in {"failed", "refunded"} and previous_status != status:
            log_event(session, user, f"payment_{status}", paid_step, {"transaction_id": transaction_id})
            delivery_bot_id = None
        else:
            delivery_bot_id = None

        offer = get_setting(session, "offer", record_bot_id) if delivery_target else {}

    if delivery_target and delivery_bot_id:
        application = get_bot_application(delivery_bot_id)
        bot_token = None
        if application is None:
            with session_scope() as session:
                bot_row = session.get(TelegramBot, delivery_bot_id)
                bot_token = bot_row.token if bot_row else settings.bot_token
        if application is not None:
            await deliver_after_payment(application=application, chat_id=delivery_target, telegram_id=delivery_target, offer=offer)
        elif bot_token:
            from backend.delivery import send_paid_delivery

            async with Bot(bot_token) as bot:
                await send_paid_delivery(bot, chat_id=delivery_target, offer=offer)
        with session_scope() as session:
            record = session.scalar(select(PaymentRecord).where(PaymentRecord.transaction_id == transaction_id))
            user = session.scalar(select(User).where(User.bot_id == delivery_bot_id, User.telegram_id == delivery_target))
            if record is not None:
                record.payload = {**(record.payload or {}), "delivery_sent_at": datetime.utcnow().isoformat()}
            if user is not None:
                paid_step = str(payment_payload_meta(record.payload if record else {}).get("step") or user.current_step or "payment")
                log_event(session, user, "paid_delivery_sent", paid_step, {"transaction_id": transaction_id})

    return {"ok": True, "matched": True, "status": status}


@app.get("/api/segments", response_model=list[SegmentOut], dependencies=[Depends(inject_admin_ctx)])
def list_segments(bot_id: int = Depends(resolve_bot_id)):
    with session_scope() as session:
        return list(session.scalars(select(Segment).where(Segment.bot_id == bot_id).order_by(Segment.sort_order, Segment.id)))


@app.post("/api/segments", response_model=SegmentOut, dependencies=[Depends(inject_admin_ctx)])
def create_segment(payload: SegmentIn, bot_id: int = Depends(resolve_bot_id)):
    with session_scope() as session:
        entity = Segment(bot_id=bot_id, **payload.model_dump())
        session.add(entity)
        session.flush()
        return entity


@app.put("/api/segments/{segment_id}", response_model=SegmentOut, dependencies=[Depends(inject_admin_ctx)])
def update_segment(segment_id: int, payload: SegmentIn, bot_id: int = Depends(resolve_bot_id)):
    with session_scope() as session:
        entity = session.get(Segment, segment_id)
        if entity is None or entity.bot_id != bot_id:
            raise HTTPException(status_code=404, detail="Segment not found")
        for key, value in payload.model_dump().items():
            setattr(entity, key, value)
        session.flush()
        return entity


@app.get("/api/follow-ups", response_model=list[FollowUpOut], dependencies=[Depends(inject_admin_ctx)])
def list_followups(bot_id: int = Depends(resolve_bot_id)):
    with session_scope() as session:
        return list(
            session.scalars(
                select(FollowUpMessage).where(FollowUpMessage.bot_id == bot_id).order_by(FollowUpMessage.delay_hours, FollowUpMessage.id)
            )
        )


@app.post("/api/follow-ups", response_model=FollowUpOut, dependencies=[Depends(inject_admin_ctx)])
def create_followup(payload: FollowUpIn, bot_id: int = Depends(resolve_bot_id)):
    with session_scope() as session:
        entity = FollowUpMessage(bot_id=bot_id, **payload.model_dump())
        session.add(entity)
        session.flush()
        return entity


@app.put("/api/follow-ups/{follow_up_id}", response_model=FollowUpOut, dependencies=[Depends(inject_admin_ctx)])
def update_followup(follow_up_id: int, payload: FollowUpIn, bot_id: int = Depends(resolve_bot_id)):
    with session_scope() as session:
        entity = session.get(FollowUpMessage, follow_up_id)
        if entity is None or entity.bot_id != bot_id:
            raise HTTPException(status_code=404, detail="Follow-up not found")
        for key, value in payload.model_dump().items():
            setattr(entity, key, value)
        session.flush()
        return entity


@app.get("/api/funnel-steps", response_model=list[FunnelStepOut], dependencies=[Depends(inject_admin_ctx)])
def list_funnel_steps(bot_id: int = Depends(resolve_bot_id)):
    with session_scope() as session:
        return list(
            session.scalars(select(FunnelStep).where(FunnelStep.bot_id == bot_id).order_by(FunnelStep.sort_order, FunnelStep.id))
        )


@app.post("/api/funnel-steps", response_model=FunnelStepOut, dependencies=[Depends(inject_admin_ctx)])
def create_funnel_step(payload: FunnelStepIn, bot_id: int = Depends(resolve_bot_id)):
    with session_scope() as session:
        if session.scalar(select(FunnelStep.id).where(FunnelStep.bot_id == bot_id, FunnelStep.code == payload.code)):
            raise HTTPException(status_code=409, detail="Funnel step code already exists")
        entity = FunnelStep(bot_id=bot_id, **payload.model_dump())
        session.add(entity)
        session.flush()
        return entity


@app.put("/api/funnel-steps/{step_id}", response_model=FunnelStepOut, dependencies=[Depends(inject_admin_ctx)])
def update_funnel_step(step_id: int, payload: FunnelStepIn, bot_id: int = Depends(resolve_bot_id)):
    with session_scope() as session:
        entity = session.get(FunnelStep, step_id)
        if entity is None or entity.bot_id != bot_id:
            raise HTTPException(status_code=404, detail="Funnel step not found")
        if session.scalar(
            select(FunnelStep.id).where(FunnelStep.bot_id == bot_id, FunnelStep.code == payload.code, FunnelStep.id != step_id)
        ):
            raise HTTPException(status_code=409, detail="Funnel step code already exists")
        old_code = entity.code
        for key, value in payload.model_dump().items():
            setattr(entity, key, value)
        if old_code != entity.code:
            for branch in session.scalars(
                select(FunnelBranch).where(FunnelBranch.bot_id == bot_id, FunnelBranch.source_step_code == old_code)
            ):
                branch.source_step_code = entity.code
            for branch in session.scalars(
                select(FunnelBranch).where(FunnelBranch.bot_id == bot_id, FunnelBranch.target_step_code == old_code)
            ):
                branch.target_step_code = entity.code
            for rule in session.scalars(
                select(AutomationRule).where(AutomationRule.bot_id == bot_id, AutomationRule.trigger_step == old_code)
            ):
                rule.trigger_step = entity.code
            for rule in session.scalars(
                select(AutomationRule).where(AutomationRule.bot_id == bot_id, AutomationRule.target_step_code == old_code)
            ):
                rule.target_step_code = entity.code
            for user in session.scalars(select(User).where(User.bot_id == bot_id, User.current_step == old_code)):
                user.current_step = entity.code
            for event in session.scalars(
                select(FunnelEvent)
                .join(User, User.id == FunnelEvent.user_id)
                .where(User.bot_id == bot_id, FunnelEvent.step == old_code)
            ):
                event.step = entity.code
        session.flush()
        return entity


@app.delete("/api/funnel-steps/{step_id}", dependencies=[Depends(inject_admin_ctx)])
def delete_funnel_step(step_id: int, bot_id: int = Depends(resolve_bot_id)):
    with session_scope() as session:
        entity = session.get(FunnelStep, step_id)
        if entity is None or entity.bot_id != bot_id:
            raise HTTPException(status_code=404, detail="Funnel step not found")
        code = entity.code
        session.execute(delete(FunnelBranch).where(FunnelBranch.bot_id == bot_id, FunnelBranch.source_step_code == code))
        session.execute(delete(FunnelBranch).where(FunnelBranch.bot_id == bot_id, FunnelBranch.target_step_code == code))
        for step in session.scalars(select(FunnelStep).where(FunnelStep.bot_id == bot_id, FunnelStep.next_step_code == code)):
            step.next_step_code = None
        session.delete(entity)
        return {"ok": True}


@app.delete("/api/funnel-steps", dependencies=[Depends(inject_admin_ctx)])
def delete_all_funnel_steps(funnel_phase: str | None = None, bot_id: int = Depends(resolve_bot_id)):
    phase = (funnel_phase or "").strip() or None
    with session_scope() as session:
        if phase:
            steps = list(session.scalars(select(FunnelStep).where(FunnelStep.bot_id == bot_id, FunnelStep.funnel_phase == phase)))
            codes = [step.code for step in steps]
            if codes:
                session.execute(
                    delete(FunnelBranch).where(FunnelBranch.bot_id == bot_id, FunnelBranch.source_step_code.in_(codes))
                )
                session.execute(
                    delete(FunnelBranch).where(FunnelBranch.bot_id == bot_id, FunnelBranch.target_step_code.in_(codes))
                )
            session.execute(delete(FunnelStep).where(FunnelStep.bot_id == bot_id, FunnelStep.funnel_phase == phase))
        else:
            session.execute(delete(FunnelBranch).where(FunnelBranch.bot_id == bot_id))
            session.execute(delete(FunnelStep).where(FunnelStep.bot_id == bot_id))
        return {"ok": True}


@app.get("/api/funnel-branches", response_model=list[FunnelBranchOut], dependencies=[Depends(inject_admin_ctx)])
def list_funnel_branches(bot_id: int = Depends(resolve_bot_id)):
    with session_scope() as session:
        return list(
            session.scalars(
                select(FunnelBranch)
                .where(FunnelBranch.bot_id == bot_id)
                .order_by(FunnelBranch.source_step_code, FunnelBranch.sort_order, FunnelBranch.id)
            )
        )


@app.post("/api/funnel-branches", response_model=FunnelBranchOut, dependencies=[Depends(inject_admin_ctx)])
def create_funnel_branch(payload: FunnelBranchIn, bot_id: int = Depends(resolve_bot_id)):
    if payload.url and not str(payload.url).strip().startswith(("http://", "https://")):
        raise HTTPException(status_code=400, detail="Ссылка должна начинаться с http:// или https://")
    with session_scope() as session:
        entity = FunnelBranch(bot_id=bot_id, **payload.model_dump())
        session.add(entity)
        session.flush()
        return entity


@app.put("/api/funnel-branches/{branch_id}", response_model=FunnelBranchOut, dependencies=[Depends(inject_admin_ctx)])
def update_funnel_branch(branch_id: int, payload: FunnelBranchIn, bot_id: int = Depends(resolve_bot_id)):
    if payload.url and not str(payload.url).strip().startswith(("http://", "https://")):
        raise HTTPException(status_code=400, detail="Ссылка должна начинаться с http:// или https://")
    with session_scope() as session:
        entity = session.get(FunnelBranch, branch_id)
        if entity is None or entity.bot_id != bot_id:
            raise HTTPException(status_code=404, detail="Funnel branch not found")
        for key, value in payload.model_dump().items():
            setattr(entity, key, value)
        session.flush()
        return entity


@app.delete("/api/funnel-branches/{branch_id}", dependencies=[Depends(inject_admin_ctx)])
def delete_funnel_branch(branch_id: int, bot_id: int = Depends(resolve_bot_id)):
    with session_scope() as session:
        entity = session.get(FunnelBranch, branch_id)
        if entity is None or entity.bot_id != bot_id:
            raise HTTPException(status_code=404, detail="Funnel branch not found")
        session.delete(entity)
        return {"ok": True}


@app.get("/api/automations", response_model=list[AutomationRuleOut], dependencies=[Depends(inject_admin_ctx)])
def list_automations(bot_id: int = Depends(resolve_bot_id)):
    with session_scope() as session:
        return list(
            session.scalars(
                select(AutomationRule).where(AutomationRule.bot_id == bot_id).order_by(AutomationRule.inactivity_hours, AutomationRule.id)
            )
        )


@app.post("/api/automations", response_model=AutomationRuleOut, dependencies=[Depends(inject_admin_ctx)])
def create_automation(payload: AutomationRuleIn, bot_id: int = Depends(resolve_bot_id)):
    with session_scope() as session:
        entity = AutomationRule(bot_id=bot_id, **payload.model_dump())
        session.add(entity)
        session.flush()
        return entity


@app.put("/api/automations/{automation_id}", response_model=AutomationRuleOut, dependencies=[Depends(inject_admin_ctx)])
def update_automation(automation_id: int, payload: AutomationRuleIn, bot_id: int = Depends(resolve_bot_id)):
    with session_scope() as session:
        entity = session.get(AutomationRule, automation_id)
        if entity is None or entity.bot_id != bot_id:
            raise HTTPException(status_code=404, detail="Automation not found")
        for key, value in payload.model_dump().items():
            setattr(entity, key, value)
        session.flush()
        return entity


@app.get("/api/users", response_model=list[UserOut], dependencies=[Depends(inject_admin_ctx)])
def list_users(bot_id: int = Depends(resolve_bot_id)):
    with session_scope() as session:
        return list(session.scalars(select(User).where(User.bot_id == bot_id).order_by(User.created_at.desc()).limit(200)))


@app.get("/api/events", response_model=list[EventOut], dependencies=[Depends(inject_admin_ctx)])
def list_events(bot_id: int = Depends(resolve_bot_id)):
    with session_scope() as session:
        rows = session.execute(
            select(FunnelEvent, User.telegram_id, User.full_name)
            .join(User, User.id == FunnelEvent.user_id)
            .where(User.bot_id == bot_id)
            .order_by(FunnelEvent.created_at.desc())
            .limit(200)
        ).all()
        return [
            EventOut(
                id=row[0].id,
                event_type=row[0].event_type,
                step=row[0].step,
                payload=row[0].payload,
                created_at=row[0].created_at,
                telegram_id=row[1],
                full_name=row[2],
            )
            for row in rows
        ]


@app.get("/api/settings", dependencies=[Depends(inject_admin_ctx)])
def get_settings(bot_id: int = Depends(resolve_bot_id)):
    with session_scope() as session:
        settings_rows = list(session.scalars(select(AppSetting).where(AppSetting.bot_id == bot_id).order_by(AppSetting.key)))
        return {row.key: row.value for row in settings_rows}


@app.put("/api/settings/{key}", dependencies=[Depends(inject_admin_ctx)])
def update_settings(key: str, value: dict, bot_id: int = Depends(resolve_bot_id)):
    with session_scope() as session:
        entity = set_setting(session, key, value, bot_id)
        return {"key": entity.key, "value": entity.value}
