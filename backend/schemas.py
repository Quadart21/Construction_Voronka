from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class DashboardStats(BaseModel):
    total_users: int
    users_today: int
    conversions: int
    conversion_rate: float
    top_segments: list[dict]
    drop_off_steps: list[dict]
    recent_events: list[dict]


class ConversionStepStat(BaseModel):
    step_code: str
    step_title: str
    entered: int
    moved_forward: int
    stuck_now: int
    drop_off_rate: float


class ConversionReport(BaseModel):
    total_entered_funnel: int
    total_completed: int
    total_stuck: int
    completion_rate: float
    step_stats: list[ConversionStepStat]
    top_drop_off_steps: list[dict]


class AccountingSummary(BaseModel):
    total_revenue: int
    paid_orders: int
    pending_orders: int
    failed_orders: int
    average_check: float
    revenue_by_segment: list[dict]
    recent_payments: list[dict]


class SegmentIn(BaseModel):
    key: str
    title: str
    promise: str
    micro_value_title: str
    micro_value_body: str
    tripwire_title: str
    tripwire_body: str
    is_active: bool = True
    sort_order: int = 0


class SegmentOut(SegmentIn):
    id: int

    class Config:
        from_attributes = True


class FollowUpIn(BaseModel):
    code: str
    title: str
    body: str
    delay_hours: int
    kind: str = "text"
    is_active: bool = True


class FollowUpOut(FollowUpIn):
    id: int

    class Config:
        from_attributes = True


class FunnelStepIn(BaseModel):
    code: str
    title: str
    body: str
    step_type: str = "content"
    media_type: str | None = None
    media_url: str | None = None
    media_caption: str | None = None
    segment_key: str | None = None
    cta_text: str | None = None
    next_step_code: str | None = None
    trigger_keywords: str | None = None
    sort_order: int = 0
    is_active: bool = True


class FunnelStepOut(FunnelStepIn):
    id: int

    class Config:
        from_attributes = True


class FunnelBranchIn(BaseModel):
    source_step_code: str
    button_text: str
    target_step_code: Optional[str] = None
    url: Optional[str] = None
    sort_order: int = 0
    is_active: bool = True


class FunnelBranchOut(FunnelBranchIn):
    id: int

    class Config:
        from_attributes = True


class AutomationRuleIn(BaseModel):
    code: str
    trigger_type: str = "inactivity"
    trigger_step: str | None = None
    inactivity_hours: int = 24
    title: str
    body: str
    bonus_label: str | None = None
    target_step_code: str | None = None
    is_active: bool = True


class AutomationRuleOut(AutomationRuleIn):
    id: int

    class Config:
        from_attributes = True


class UserOut(BaseModel):
    id: int
    telegram_id: int
    username: str | None
    full_name: str
    segment_key: str | None
    current_step: str
    source: str
    is_customer: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class EventOut(BaseModel):
    id: int
    event_type: str
    step: str
    payload: dict
    created_at: datetime
    telegram_id: int
    full_name: str


class AdminUserOut(BaseModel):
    id: int
    username: str
    totp_confirmed: bool
    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True


class AdminCreateIn(BaseModel):
    username: str
    password: str


class AuthLoginIn(BaseModel):
    username: str
    password: str


class AuthVerifyTotpIn(BaseModel):
    partial_token: str
    code: str


class AuthConfirmSetupIn(BaseModel):
    setup_token: str
    code: str


class AuthMeOut(BaseModel):
    id: int
    username: str


class LeadCreateIn(BaseModel):
    full_name: str
    email: str
    phone: str
    company: str | None = None
    message: str | None = None


class LeadOut(BaseModel):
    id: int
    full_name: str
    email: str
    phone: str
    company: str | None
    message: str | None
    source: str
    status: str
    ip_address: str | None
    user_agent: str | None
    created_at: datetime

    class Config:
        from_attributes = True


class LeadPatchIn(BaseModel):
    status: str = "processed"
