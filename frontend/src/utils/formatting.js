const PAYMENT_STATUS_RU = {
  paid: "Оплачено",
  pending: "В ожидании",
  failed: "Отклонено",
  refunded: "Возврат",
  unknown: "Неизвестно"
};

const EVENT_TYPE_RU = {
  start: "Старт в боте",
  step_opened: "Открыл шаг",
  payment_started: "Начал оплату",
  payment_paid: "Оплатил",
  payment_pending: "Оплата в процессе",
  payment_failed: "Оплата не прошла",
  payment_refunded: "Возврат оплаты",
  paid_delivery_sent: "Получил материал после оплаты",
  anti_spam_triggered: "Сработала защита от спама",
  invalid_input: "Некорректное сообщение",
  follow_up_sent: "Отправлено доп. сообщение",
  inactivity_bonus_sent: "Автонапоминание отправлено"
};

export function formatDateTime(value) {
  if (value == null || value === "") return "—";
  const d = new Date(value);
  if (Number.isNaN(d.getTime())) return String(value);
  return d.toLocaleString("ru-RU", { dateStyle: "short", timeStyle: "short" });
}

export function paymentStatusLabel(status) {
  if (status == null || status === "") return "—";
  const key = String(status).toLowerCase();
  return PAYMENT_STATUS_RU[key] || String(status);
}

export function eventTypeLabel(type) {
  if (type == null || type === "") return "—";
  return EVENT_TYPE_RU[type] || type;
}

export function formatEventPayload(payload) {
  if (payload == null || typeof payload !== "object") return "—";
  const entries = Object.entries(payload).filter(([, v]) => v != null && v !== "");
  if (!entries.length) return "—";
  return entries
    .map(([k, v]) => {
      if (typeof v === "object") return `${k}: ${JSON.stringify(v)}`;
      return `${k}: ${v}`;
    })
    .join(" · ");
}

export function customerLabel(isCustomer) {
  return isCustomer ? "Да, клиент" : "Пока нет";
}
