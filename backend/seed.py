from sqlalchemy import select

from backend.database import session_scope
from backend.models import AppSetting, AutomationRule, FollowUpMessage, FunnelBranch, FunnelStep, Segment


DEFAULT_SEGMENTS = [
    {
        "key": "brand",
        "title": "Контент и личный бренд",
        "promise": "Чтобы начать расти уже сегодня, держи рабочую связку без лишней теории.",
        "micro_value_title": "Связка для Reels",
        "micro_value_body": "1. Вставь промпт в ChatGPT.\n2. Получи сценарий Reels на 30 секунд.\n3. Отдай текст в сервис озвучки.\n4. Собери ролик и выкладывай сегодня.",
        "tripwire_title": "Полный пакет автоматизации контента",
        "tripwire_body": "100+ шаблонов, контент-план, промпты для прогрева и сторис-воронка.",
        "sort_order": 1,
    },
    {
        "key": "freelance",
        "title": "Фриланс: тексты и дизайн",
        "promise": "Берем одну боль: быстрее делать результат, который можно продать клиенту.",
        "micro_value_title": "Связка для быстрой сдачи заказа",
        "micro_value_body": "1. Получи бриф через промпт.\n2. Собери первый драфт текста/дизайна.\n3. Дополни оффером и отправь клиенту.",
        "tripwire_title": "Набор исполнителя",
        "tripwire_body": "Шаблоны брифов, офферов, правок и 100+ продающих промптов.",
        "sort_order": 2,
    },
    {
        "key": "business",
        "title": "Экономить время в бизнесе",
        "promise": "Сразу даю практический сценарий, который экономит часы уже в первый день.",
        "micro_value_title": "Связка для операционки",
        "micro_value_body": "1. Сними рутину из переписок.\n2. Автоматизируй ответы и брифы.\n3. Используй шаблон для повторяющихся задач.",
        "tripwire_title": "Каталог автоматизации бизнеса",
        "tripwire_body": "Готовые сценарии для отдела продаж, поддержки, контента и операционки.",
        "sort_order": 3,
    },
]

DEFAULT_FOLLOWUPS = [
    {"code": "video_demo", "title": "Видео-демо", "body": "Вот короткая демонстрация, как это работает на экране смартфона. Ответь 'ХОЧУ', если нужен полный каталог.", "delay_hours": 2},
    {"code": "social_proof", "title": "Социальное доказательство", "body": "Кейс: пользователь собрал первую воронку за вечер и получил первые заявки без дизайнера и копирайтера.", "delay_hours": 24},
    {"code": "discount", "title": "Спецпредложение", "body": "Спецпредложение: скидка 20% действует 4 часа. Если хочешь доступ, нажми кнопку ниже.", "delay_hours": 48},
]

DEFAULT_STEPS = [
    {"code": "welcome", "title": "Старт", "body": "Привет! Начнем с первого полезного шага.", "step_type": "segment_entry", "next_step_code": "micro_value", "sort_order": 1},
    {"code": "micro_value", "title": "Рабочая связка", "body": "Первый практический результат без теории.", "step_type": "content", "sort_order": 2, "media_type": None, "media_url": None, "media_caption": None},
    {"code": "core_offer", "title": "Основное предложение", "body": "Tripwire-предложение и мягкий дожим к покупке.", "step_type": "offer", "sort_order": 3, "media_type": None, "media_url": None, "media_caption": None},
    {"code": "social_proof", "title": "Кейс и доказательство", "body": "Показываем результат другого клиента, чтобы снять сомнения.", "step_type": "content", "sort_order": 4, "media_type": None, "media_url": None, "media_caption": None},
    {"code": "payment", "title": "Оплата", "body": "Переводим человека на страницу оплаты.", "step_type": "payment", "cta_text": "Оплатить", "sort_order": 5, "media_type": None, "media_url": None, "media_caption": None},
]

DEFAULT_BRANCHES = [
    {"source_step_code": "micro_value", "button_text": "Хочу полный пакет", "target_step_code": "core_offer", "sort_order": 1},
    {"source_step_code": "micro_value", "button_text": "Покажи кейс", "target_step_code": "social_proof", "sort_order": 2},
    {"source_step_code": "social_proof", "button_text": "Теперь хочу пакет", "target_step_code": "core_offer", "sort_order": 1},
    {"source_step_code": "core_offer", "button_text": "Перейти к оплате", "target_step_code": "payment", "sort_order": 1},
]

DEFAULT_AUTOMATIONS = [
    {
        "code": "inactive_bonus_2h",
        "trigger_step": "micro_value",
        "inactivity_hours": 2,
        "title": "Видео-бонус за бездействие",
        "body": "Ты остановился на первом шаге, поэтому держи бонус: короткое видео с демонстрацией связки на смартфоне.",
        "bonus_label": "Видео-бонус",
        "target_step_code": "core_offer",
    },
    {
        "code": "inactive_bonus_24h",
        "trigger_step": "core_offer",
        "inactivity_hours": 24,
        "title": "Кейс за бездействие",
        "body": "Если решение откладывается, смотри кейс и забирай дополнительный аргумент к покупке.",
        "bonus_label": "Кейс",
        "target_step_code": "payment",
    },
]

DEFAULT_SETTINGS = {
    "funnel_copy": {
        "welcome": "Привет! Твой выбор — {segment}. Чтобы начать уже сегодня, держи первый инструмент. Без теории. Только практика.",
        "invalid_input": "Я тебя не понял, нажми на одну из кнопок ниже 👇",
        "core_offer_hint": "Этот метод уже даёт результат, но для масштабирования нужна база из 100+ шаблонов. Она доступна в основном каталоге.",
    },
    "offer": {
        "price_label": "Tripwire offer",
        "price_text": "Полный пакет автоматизации за быстрый чек без долгих раздумий.",
        "discount_percent": 20,
        "discount_window_hours": 4,
        "amount": 9900,
        "currency": "RUB",
        "payment_method": 2,
        "description": "Оплата полного пакета автоматизации",
        "delivery": {
            "title": "Доступ открыт",
            "text": "Оплата прошла. Забирай купленные материалы ниже.",
            "media_type": "",
            "media_url": "",
            "media_caption": "",
            "buttons": [{"text": "Открыть материалы", "url": "https://example.com/materials"}],
        },
    },
    "payment": {
        "platega": {"enabled": True},
        "noren": {
            "enabled": False,
            "api_key": "",
            "api_secret": "",
            "project_id": "",
            "base_url": "https://noren.digital/api/v1/client",
            "amount": "",
            "crypto_currency": "USDT",
            "network": "TRC20",
            "webhook_secret": "",
            "invoice_reuse_active": True,
            "invoice_max_per_hour": 3,
            "invoice_cooldown_minutes": 5,
        },
    },
    "subscription_gate": {
        "enabled": False,
        "channels": [],
        "require_all": True,
        "message": "Чтобы пользоваться ботом, подпишитесь на наши каналы — там выходят материалы и анонсы.",
        "not_subscribed_hint": "Подписка пока не видна. Откройте каналы, подпишитесь и нажмите «Проверить».",
        "check_button_text": "Я подписался — проверить",
        "skip_for_paid_users": True,
    },
}


def seed_bot_defaults(bot_id: int) -> None:
    with session_scope() as session:
        if not session.scalar(select(Segment.id).where(Segment.bot_id == bot_id).limit(1)):
            for segment in DEFAULT_SEGMENTS:
                session.add(Segment(bot_id=bot_id, **segment))
        if not session.scalar(select(FollowUpMessage.id).where(FollowUpMessage.bot_id == bot_id).limit(1)):
            for item in DEFAULT_FOLLOWUPS:
                session.add(FollowUpMessage(bot_id=bot_id, **item))
        if not session.scalar(select(FunnelStep.id).where(FunnelStep.bot_id == bot_id).limit(1)):
            for item in DEFAULT_STEPS:
                session.add(FunnelStep(bot_id=bot_id, **item))
        if not session.scalar(select(FunnelBranch.id).where(FunnelBranch.bot_id == bot_id).limit(1)):
            for item in DEFAULT_BRANCHES:
                session.add(FunnelBranch(bot_id=bot_id, **item))
        if not session.scalar(select(AutomationRule.id).where(AutomationRule.bot_id == bot_id).limit(1)):
            for item in DEFAULT_AUTOMATIONS:
                session.add(AutomationRule(bot_id=bot_id, **item))
        for key, value in DEFAULT_SETTINGS.items():
            existing = session.scalar(select(AppSetting).where(AppSetting.bot_id == bot_id, AppSetting.key == key))
            if existing is None:
                session.add(AppSetting(bot_id=bot_id, key=key, value=value))
        welcome = session.scalar(
            select(FunnelStep).where(
                FunnelStep.bot_id == bot_id, FunnelStep.code == "welcome", FunnelStep.step_type == "segment_entry"
            )
        )
        if welcome is not None:
            if welcome.title == "Выбор направления":
                welcome.title = "Старт"
            if welcome.body in {"Сегментация входящего пользователя.", "Для каких целей тебе нейросети?"}:
                welcome.body = "Привет! Начнем с первого полезного шага."
            if not welcome.next_step_code:
                welcome.next_step_code = "micro_value"


def seed_defaults() -> None:
    from backend.models import TelegramBot
    from backend.multi_bot_migrate import ensure_multi_bot_schema

    ensure_multi_bot_schema()
    with session_scope() as session:
        for bot_id in session.scalars(select(TelegramBot.id)):
            seed_bot_defaults(int(bot_id))
