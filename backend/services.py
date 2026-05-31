from datetime import datetime, timedelta
import re

from sqlalchemy import func, select

from backend.database import session_scope
from backend.models import AppSetting, AutomationRule, FollowUpMessage, FunnelBranch, FunnelEvent, FunnelStep, PaymentRecord, Segment, User


def get_or_create_user(session, tg_user, bot_id: int) -> User:
    user = session.scalar(select(User).where(User.bot_id == bot_id, User.telegram_id == tg_user.id))
    full_name = " ".join(part for part in [tg_user.first_name, tg_user.last_name] if part).strip()
    if user is None:
        user = User(
            bot_id=bot_id,
            telegram_id=tg_user.id,
            username=tg_user.username,
            full_name=full_name,
        )
        session.add(user)
        session.flush()
    else:
        user.username = tg_user.username
        user.full_name = full_name
    return user


def log_event(session, user: User, event_type: str, step: str, payload: dict | None = None, *, update_current: bool = True) -> FunnelEvent:
    event = FunnelEvent(user_id=user.id, event_type=event_type, step=step, payload=payload or {})
    session.add(event)
    if update_current:
        user.current_step = step
    session.flush()
    return event


def get_segments(session, bot_id: int) -> list[Segment]:
    return list(
        session.scalars(
            select(Segment).where(Segment.bot_id == bot_id, Segment.is_active.is_(True)).order_by(Segment.sort_order, Segment.id)
        )
    )


def get_setting(session, key: str, bot_id: int, fallback: dict | None = None) -> dict:
    setting = session.scalar(select(AppSetting).where(AppSetting.bot_id == bot_id, AppSetting.key == key))
    return setting.value if setting else (fallback or {})


def set_setting(session, key: str, value: dict, bot_id: int) -> AppSetting:
    setting = session.scalar(select(AppSetting).where(AppSetting.bot_id == bot_id, AppSetting.key == key))
    if setting is None:
        setting = AppSetting(bot_id=bot_id, key=key, value=value)
        session.add(setting)
    else:
        setting.value = value
    session.flush()
    return setting


def get_dashboard_stats(bot_id: int) -> dict:
    with session_scope() as session:
        total_users = session.scalar(select(func.count(User.id)).where(User.bot_id == bot_id)) or 0
        start_of_day = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
        users_today = (
            session.scalar(select(func.count(User.id)).where(User.bot_id == bot_id, User.created_at >= start_of_day)) or 0
        )
        conversions = session.scalar(select(func.count(User.id)).where(User.bot_id == bot_id, User.is_customer.is_(True))) or 0
        conversion_rate = round((conversions / total_users) * 100, 2) if total_users else 0.0

        segment_rows = session.execute(
            select(User.segment_key, func.count(User.id)).where(User.bot_id == bot_id).group_by(User.segment_key)
        ).all()
        top_segments = [{"segment": row[0] or "unassigned", "users": row[1]} for row in segment_rows]

        drop_rows = session.execute(
            select(User.current_step, func.count(User.id))
            .where(User.bot_id == bot_id)
            .group_by(User.current_step)
            .order_by(func.count(User.id).desc())
        ).all()
        drop_off_steps = [{"step": row[0], "users": row[1]} for row in drop_rows[:6]]

        recent = session.execute(
            select(FunnelEvent, User.telegram_id, User.full_name)
            .join(User, User.id == FunnelEvent.user_id)
            .where(User.bot_id == bot_id)
            .order_by(FunnelEvent.created_at.desc())
            .limit(12)
        ).all()
        recent_events = [
            {
                "id": row[0].id,
                "event_type": row[0].event_type,
                "step": row[0].step,
                "payload": row[0].payload,
                "created_at": row[0].created_at.isoformat(),
                "telegram_id": row[1],
                "full_name": row[2],
            }
            for row in recent
        ]
        return {
            "total_users": total_users,
            "users_today": users_today,
            "conversions": conversions,
            "conversion_rate": conversion_rate,
            "top_segments": top_segments,
            "drop_off_steps": drop_off_steps,
            "recent_events": recent_events,
        }


def create_payment_record(
    session,
    *,
    user: User,
    transaction_id: str | None,
    status: str,
    amount: int,
    currency: str,
    description: str,
    payload: dict,
    provider: str = "platega",
) -> PaymentRecord:
    record = PaymentRecord(
        bot_id=user.bot_id,
        user_id=user.id,
        telegram_id=user.telegram_id,
        full_name=user.full_name,
        segment_key=user.segment_key,
        transaction_id=transaction_id,
        status=status,
        amount=amount,
        currency=currency,
        description=description,
        payload=payload,
        provider=provider,
    )
    session.add(record)
    session.flush()
    return record


def should_rate_limit(user: User, window_seconds: int, burst_limit: int) -> bool:
    now = datetime.utcnow()
    if user.anti_spam_last_hit_at and (now - user.anti_spam_last_hit_at) <= timedelta(seconds=window_seconds):
        user.anti_spam_hits += 1
    else:
        user.anti_spam_hits = 1
    user.anti_spam_last_hit_at = now
    return user.anti_spam_hits > burst_limit


def get_followups(session, bot_id: int) -> list[FollowUpMessage]:
    return list(
        session.scalars(
            select(FollowUpMessage)
            .where(FollowUpMessage.bot_id == bot_id, FollowUpMessage.is_active.is_(True))
            .order_by(FollowUpMessage.delay_hours)
        )
    )


def get_step_by_code(session, code: str, bot_id: int) -> FunnelStep | None:
    if not code:
        return None
    return session.scalar(
        select(FunnelStep).where(FunnelStep.bot_id == bot_id, FunnelStep.code == code, FunnelStep.is_active.is_(True))
    )


def get_step_by_id(session, step_id: int, bot_id: int) -> FunnelStep | None:
    return session.scalar(
        select(FunnelStep).where(FunnelStep.bot_id == bot_id, FunnelStep.id == step_id, FunnelStep.is_active.is_(True))
    )


def _normalize_trigger_text(value: str | None) -> str:
    cleaned = re.sub(r"[^\w\s-]+", " ", (value or "").casefold())
    return " ".join(cleaned.strip().split())


def _split_trigger_keywords(value: str | None) -> list[str]:
    if not value:
        return []
    normalized = value.replace("\r", "\n").replace(";", "\n").replace(",", "\n")
    return [_normalize_trigger_text(item) for item in normalized.splitlines() if _normalize_trigger_text(item)]


def get_step_by_trigger(session, text: str | None, bot_id: int, *, funnel_phase: str | None = None) -> FunnelStep | None:
    incoming = _normalize_trigger_text(text)
    if not incoming:
        return None
    query = select(FunnelStep).where(FunnelStep.bot_id == bot_id, FunnelStep.is_active.is_(True))
    if funnel_phase:
        query = query.where(FunnelStep.funnel_phase == funnel_phase)
    steps = session.scalars(query.order_by(FunnelStep.sort_order, FunnelStep.id))
    for step in steps:
        if incoming in _split_trigger_keywords(step.trigger_keywords):
            return step
    return None


def get_segment_entry_step(session, bot_id: int) -> FunnelStep | None:
    return session.scalar(
        select(FunnelStep)
        .where(
            FunnelStep.bot_id == bot_id,
            FunnelStep.is_active.is_(True),
            FunnelStep.step_type == "segment_entry",
            FunnelStep.funnel_phase == "main",
        )
        .order_by(FunnelStep.sort_order, FunnelStep.id)
    )


def get_first_funnel_step(session, bot_id: int, segment_key: str | None = None) -> FunnelStep | None:
    return session.scalar(
        select(FunnelStep)
        .where(
            FunnelStep.bot_id == bot_id,
            FunnelStep.is_active.is_(True),
            FunnelStep.funnel_phase == "main",
            FunnelStep.step_type != "segment_entry",
            (FunnelStep.segment_key.is_(None) if segment_key is None else (FunnelStep.segment_key == segment_key) | (FunnelStep.segment_key.is_(None))),
        )
        .order_by(FunnelStep.sort_order, FunnelStep.id)
    )


def get_first_post_payment_step(session, bot_id: int) -> FunnelStep | None:
    return session.scalar(
        select(FunnelStep)
        .where(FunnelStep.bot_id == bot_id, FunnelStep.is_active.is_(True), FunnelStep.funnel_phase == "post_payment")
        .order_by(FunnelStep.sort_order, FunnelStep.id)
    )


def user_funnel_phase(user: User) -> str:
    return "post_payment" if user.is_customer else "main"


def resolve_user_context_step(session, user: User, bot_id: int) -> FunnelStep | None:
    phase = user_funnel_phase(user)
    step = get_step_by_code(session, user.current_step, bot_id)
    if step is not None and (step.funnel_phase or "main") == phase:
        return step
    if phase == "post_payment":
        return get_first_post_payment_step(session, bot_id)
    return get_segment_entry_step(session, bot_id) or get_first_funnel_step(session, bot_id)


def get_first_step_after_segment(session, bot_id: int, segment_key: str | None = None) -> FunnelStep | None:
    entry_step = get_segment_entry_step(session, bot_id)
    if entry_step and entry_step.next_step_code:
        target = get_step_by_code(session, entry_step.next_step_code, bot_id)
        if target and (target.segment_key is None or target.segment_key == segment_key):
            return target
    return get_first_funnel_step(session, bot_id, segment_key)


def get_branches_for_step(session, step_code: str, bot_id: int) -> list[FunnelBranch]:
    return list(
        session.scalars(
            select(FunnelBranch)
            .where(FunnelBranch.bot_id == bot_id, FunnelBranch.source_step_code == step_code, FunnelBranch.is_active.is_(True))
            .order_by(FunnelBranch.sort_order, FunnelBranch.id)
        )
    )


def get_branch_by_id(session, branch_id: int, bot_id: int) -> FunnelBranch | None:
    return session.scalar(
        select(FunnelBranch).where(FunnelBranch.bot_id == bot_id, FunnelBranch.id == branch_id, FunnelBranch.is_active.is_(True))
    )


def get_automation_rules(session, bot_id: int) -> list[AutomationRule]:
    return list(
        session.scalars(
            select(AutomationRule)
            .where(AutomationRule.bot_id == bot_id, AutomationRule.is_active.is_(True))
            .order_by(AutomationRule.inactivity_hours, AutomationRule.id)
        )
    )


def get_conversion_report(bot_id: int) -> dict:
    with session_scope() as session:
        steps = list(
            session.scalars(
                select(FunnelStep)
                .where(FunnelStep.bot_id == bot_id, FunnelStep.is_active.is_(True))
                .order_by(FunnelStep.sort_order, FunnelStep.id)
            )
        )
        user_ids = select(User.id).where(User.bot_id == bot_id)
        total_entered = (
            session.scalar(
                select(func.count(func.distinct(FunnelEvent.user_id))).where(
                    FunnelEvent.user_id.in_(user_ids), FunnelEvent.event_type.in_(["start", "step_opened"])
                )
            )
            or 0
        )
        total_completed = session.scalar(select(func.count(User.id)).where(User.bot_id == bot_id, User.is_customer.is_(True))) or 0
        total_stuck = (
            session.scalar(select(func.count(User.id)).where(User.bot_id == bot_id, User.is_customer.is_(False), User.current_step != "start"))
            or 0
        )
        step_stats = []
        for step in steps:
            entered = (
                session.scalar(
                    select(func.count(FunnelEvent.id)).where(
                        FunnelEvent.step == step.code, FunnelEvent.user_id.in_(user_ids)
                    )
                )
                or 0
            )
            moved_forward = (
                session.scalar(
                    select(func.count(User.id)).where(
                        User.bot_id == bot_id,
                        User.current_step != step.code,
                        User.id.in_(select(FunnelEvent.user_id).where(FunnelEvent.step == step.code)),
                    )
                )
                or 0
            )
            stuck_now = session.scalar(select(func.count(User.id)).where(User.bot_id == bot_id, User.current_step == step.code)) or 0
            drop_rate = round((stuck_now / entered) * 100, 2) if entered else 0.0
            step_stats.append(
                {
                    "step_code": step.code,
                    "step_title": step.title,
                    "entered": entered,
                    "moved_forward": moved_forward,
                    "stuck_now": stuck_now,
                    "drop_off_rate": drop_rate,
                }
            )
        top_drop = sorted(step_stats, key=lambda item: item["stuck_now"], reverse=True)[:6]
        completion_rate = round((total_completed / total_entered) * 100, 2) if total_entered else 0.0
        return {
            "total_entered_funnel": total_entered,
            "total_completed": total_completed,
            "total_stuck": total_stuck,
            "completion_rate": completion_rate,
            "step_stats": step_stats,
            "top_drop_off_steps": top_drop,
        }


def get_accounting_summary(bot_id: int) -> dict:
    with session_scope() as session:
        paid_orders = (
            session.scalar(select(func.count(PaymentRecord.id)).where(PaymentRecord.bot_id == bot_id, PaymentRecord.status == "paid"))
            or 0
        )
        pending_orders = (
            session.scalar(select(func.count(PaymentRecord.id)).where(PaymentRecord.bot_id == bot_id, PaymentRecord.status == "pending"))
            or 0
        )
        failed_orders = (
            session.scalar(select(func.count(PaymentRecord.id)).where(PaymentRecord.bot_id == bot_id, PaymentRecord.status == "failed"))
            or 0
        )
        total_revenue = (
            session.scalar(
                select(func.coalesce(func.sum(PaymentRecord.amount), 0)).where(PaymentRecord.bot_id == bot_id, PaymentRecord.status == "paid")
            )
            or 0
        )
        average_check = round(total_revenue / paid_orders, 2) if paid_orders else 0.0
        revenue_rows = session.execute(
            select(PaymentRecord.segment_key, func.coalesce(func.sum(PaymentRecord.amount), 0))
            .where(PaymentRecord.bot_id == bot_id, PaymentRecord.status == "paid")
            .group_by(PaymentRecord.segment_key)
        ).all()
        recent_rows = list(
            session.scalars(select(PaymentRecord).where(PaymentRecord.bot_id == bot_id).order_by(PaymentRecord.created_at.desc()).limit(20))
        )
        return {
            "total_revenue": int(total_revenue),
            "paid_orders": paid_orders,
            "pending_orders": pending_orders,
            "failed_orders": failed_orders,
            "average_check": average_check,
            "revenue_by_segment": [{"segment": row[0] or "Без сегмента", "amount": int(row[1])} for row in revenue_rows],
            "recent_payments": [
                {
                    "id": row.id,
                    "telegram_id": row.telegram_id,
                    "full_name": row.full_name,
                    "segment_key": row.segment_key,
                    "transaction_id": row.transaction_id,
                    "status": row.status,
                    "amount": row.amount,
                    "currency": row.currency,
                    "created_at": row.created_at.isoformat(),
                }
                for row in recent_rows
            ],
        }
