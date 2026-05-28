from datetime import datetime
from typing import Optional

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.database import Base


class TelegramBot(Base):
    __tablename__ = "telegram_bots"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(128))
    token: Mapped[str] = mapped_column(String(255))
    username: Mapped[str | None] = mapped_column(String(128), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)


class AdminUser(Base):
    __tablename__ = "admin_users"

    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    totp_secret: Mapped[str | None] = mapped_column(String(64), nullable=True)
    totp_confirmed: Mapped[bool] = mapped_column(Boolean, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)


class User(Base):
    __tablename__ = "users"
    __table_args__ = (UniqueConstraint("bot_id", "telegram_id", name="uq_users_bot_telegram"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    bot_id: Mapped[int] = mapped_column(ForeignKey("telegram_bots.id"), index=True, default=1)
    telegram_id: Mapped[int] = mapped_column(Integer, index=True)
    username: Mapped[str | None] = mapped_column(String(128))
    full_name: Mapped[str] = mapped_column(String(255), default="")
    segment_key: Mapped[str | None] = mapped_column(String(64), index=True)
    current_step: Mapped[str] = mapped_column(String(64), default="start")
    source: Mapped[str] = mapped_column(String(64), default="instagram")
    is_customer: Mapped[bool] = mapped_column(Boolean, default=False)
    anti_spam_hits: Mapped[int] = mapped_column(Integer, default=0)
    anti_spam_last_hit_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)

    events: Mapped[list["FunnelEvent"]] = relationship(back_populates="user", cascade="all, delete-orphan")


class FunnelEvent(Base):
    __tablename__ = "funnel_events"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    event_type: Mapped[str] = mapped_column(String(64), index=True)
    step: Mapped[str] = mapped_column(String(64), index=True)
    payload: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, index=True)

    user: Mapped[User] = relationship(back_populates="events")


class Segment(Base):
    __tablename__ = "segments"
    __table_args__ = (UniqueConstraint("bot_id", "key", name="uq_segments_bot_key"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    bot_id: Mapped[int] = mapped_column(ForeignKey("telegram_bots.id"), index=True, default=1)
    key: Mapped[str] = mapped_column(String(64), index=True)
    title: Mapped[str] = mapped_column(String(255))
    promise: Mapped[str] = mapped_column(Text)
    micro_value_title: Mapped[str] = mapped_column(String(255))
    micro_value_body: Mapped[str] = mapped_column(Text)
    tripwire_title: Mapped[str] = mapped_column(String(255))
    tripwire_body: Mapped[str] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)


class FollowUpMessage(Base):
    __tablename__ = "follow_up_messages"
    __table_args__ = (UniqueConstraint("bot_id", "code", name="uq_followups_bot_code"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    bot_id: Mapped[int] = mapped_column(ForeignKey("telegram_bots.id"), index=True, default=1)
    code: Mapped[str] = mapped_column(String(64), index=True)
    title: Mapped[str] = mapped_column(String(255))
    body: Mapped[str] = mapped_column(Text)
    delay_hours: Mapped[int] = mapped_column(Integer)
    kind: Mapped[str] = mapped_column(String(32), default="text")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class FunnelStep(Base):
    __tablename__ = "funnel_steps"
    __table_args__ = (UniqueConstraint("bot_id", "code", name="uq_funnel_steps_bot_code"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    bot_id: Mapped[int] = mapped_column(ForeignKey("telegram_bots.id"), index=True, default=1)
    code: Mapped[str] = mapped_column(String(64), index=True)
    title: Mapped[str] = mapped_column(String(255))
    body: Mapped[str] = mapped_column(Text)
    step_type: Mapped[str] = mapped_column(String(32), default="content")
    media_type: Mapped[str | None] = mapped_column(String(32))
    media_url: Mapped[str | None] = mapped_column(Text)
    media_caption: Mapped[str | None] = mapped_column(Text)
    segment_key: Mapped[str | None] = mapped_column(String(64), index=True)
    cta_text: Mapped[str | None] = mapped_column(String(128))
    next_step_code: Mapped[str | None] = mapped_column(String(64), index=True)
    trigger_keywords: Mapped[str | None] = mapped_column(Text)
    funnel_phase: Mapped[str] = mapped_column(String(32), default="main", index=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class FunnelBranch(Base):
    __tablename__ = "funnel_branches"

    id: Mapped[int] = mapped_column(primary_key=True)
    bot_id: Mapped[int] = mapped_column(ForeignKey("telegram_bots.id"), index=True, default=1)
    source_step_code: Mapped[str] = mapped_column(String(64), index=True)
    button_text: Mapped[str] = mapped_column(String(128))
    target_step_code: Mapped[Optional[str]] = mapped_column(String(64), index=True, nullable=True)
    url: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class AutomationRule(Base):
    __tablename__ = "automation_rules"
    __table_args__ = (UniqueConstraint("bot_id", "code", name="uq_automations_bot_code"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    bot_id: Mapped[int] = mapped_column(ForeignKey("telegram_bots.id"), index=True, default=1)
    code: Mapped[str] = mapped_column(String(64), index=True)
    trigger_type: Mapped[str] = mapped_column(String(32), default="inactivity")
    trigger_step: Mapped[str | None] = mapped_column(String(64), index=True)
    inactivity_hours: Mapped[int] = mapped_column(Integer, default=24)
    title: Mapped[str] = mapped_column(String(255))
    body: Mapped[str] = mapped_column(Text)
    bonus_label: Mapped[str | None] = mapped_column(String(255))
    target_step_code: Mapped[str | None] = mapped_column(String(64))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class PaymentRecord(Base):
    __tablename__ = "payment_records"

    id: Mapped[int] = mapped_column(primary_key=True)
    bot_id: Mapped[int] = mapped_column(ForeignKey("telegram_bots.id"), index=True, default=1)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), index=True)
    telegram_id: Mapped[int] = mapped_column(Integer, index=True)
    full_name: Mapped[str] = mapped_column(String(255), default="")
    segment_key: Mapped[str | None] = mapped_column(String(64), index=True)
    transaction_id: Mapped[str | None] = mapped_column(String(128), unique=True, index=True)
    status: Mapped[str] = mapped_column(String(32), default="pending", index=True)
    amount: Mapped[int] = mapped_column(Integer, default=0)
    currency: Mapped[str] = mapped_column(String(16), default="RUB")
    provider: Mapped[str] = mapped_column(String(32), default="platega")
    description: Mapped[str] = mapped_column(Text, default="")
    payload: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)


class AppSetting(Base):
    __tablename__ = "app_settings"
    __table_args__ = (UniqueConstraint("bot_id", "key", name="uq_app_settings_bot_key"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    bot_id: Mapped[int] = mapped_column(ForeignKey("telegram_bots.id"), index=True, default=1)
    key: Mapped[str] = mapped_column(String(128), index=True)
    value: Mapped[dict] = mapped_column(JSON, default=dict)


class Lead(Base):
    __tablename__ = "leads"

    id: Mapped[int] = mapped_column(primary_key=True)
    full_name: Mapped[str] = mapped_column(String(255))
    email: Mapped[str] = mapped_column(String(255), index=True)
    phone: Mapped[str] = mapped_column(String(64))
    company: Mapped[str | None] = mapped_column(String(255), nullable=True)
    message: Mapped[str | None] = mapped_column(Text, nullable=True)
    source: Mapped[str] = mapped_column(String(64), default="landing")
    status: Mapped[str] = mapped_column(String(32), default="new", index=True)
    ip_address: Mapped[str | None] = mapped_column(String(64), nullable=True)
    user_agent: Mapped[str | None] = mapped_column(String(512), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, index=True)
