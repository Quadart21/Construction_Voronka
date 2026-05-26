<script setup>
import { ref } from "vue";
import { RouterLink } from "vue-router";
import { getApiBase } from "../utils/apiBase";

const form = ref({
  full_name: "",
  email: "",
  phone: "",
  company: "",
  message: ""
});

const submitting = ref(false);
const formMessage = ref("");
const formError = ref("");

async function submitLead() {
  formMessage.value = "";
  formError.value = "";
  submitting.value = true;
  try {
    const res = await fetch(`${getApiBase()}/public/leads`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        full_name: form.value.full_name.trim(),
        email: form.value.email.trim(),
        phone: form.value.phone.trim(),
        company: form.value.company.trim() || null,
        message: form.value.message.trim() || null
      })
    });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) {
      const detail = data.detail;
      formError.value = typeof detail === "string" ? detail : "Не удалось отправить заявку. Попробуйте позже.";
      return;
    }
    formMessage.value = "Спасибо! Мы свяжемся с вами в ближайшее время.";
    form.value = { full_name: "", email: "", phone: "", company: "", message: "" };
  } catch {
    formError.value = "Нет связи с сервером. Проверьте подключение и попробуйте снова.";
  } finally {
    submitting.value = false;
  }
}

const features = [
  {
    title: "Воронки под рекламу",
    text: "Сценарии от первого касания до оплаты: ветвления, таймеры, напоминания — без лишней сложности."
  },
  {
    title: "Telegram как витрина",
    text: "Пользователь остаётся в привычном мессенджере: меньше отвалов на пути к конверсии."
  },
  {
    title: "Аналитика и события",
    text: "Видно, где люди застревают и что приносит результат — чтобы быстро докручивать связки."
  },
  {
    title: "Платежи и доступ",
    text: "Приём оплат и выдача материалов встроены в логику шагов, а не «отдельным куском»."
  }
];

const cards = [
  { tag: "Скорость", title: "Запуск за дни", body: "Шаблоны шагов и веток помогают выкатывать тесты без долгой разработки." },
  { tag: "Контроль", title: "Единая панель", body: "Тексты, медиа, автоматизации и история — в одном интерфейсе для команды." },
  { tag: "Масштаб", title: "Под нагрузку", body: "Рассчитано на поток лидов из рекламы и органики без ручной рутины." }
];
</script>

<template>
  <div class="landing">
    <header class="landing-top">
      <div class="landing-inner landing-top__row">
        <div class="logo-block">
          <span class="logo-mark">F</span>
          <span class="logo-text">FunnelStack</span>
        </div>
        <nav class="top-nav">
          <a href="#features">Возможности</a>
          <a href="#request">Заявка</a>
          <RouterLink class="top-nav__admin" to="/admin">Войти в панель</RouterLink>
        </nav>
      </div>
    </header>

    <main>
      <section class="hero">
        <div class="landing-inner hero__grid">
          <div class="hero__copy">
            <p class="hero__eyebrow">Платформа рекламных воронок</p>
            <h1 class="hero__title">Стройте воронки, которые доводят до цели</h1>
            <p class="hero__lead">
              Технологичный конструктор сценариев для performance и бренда: от клика по объявлению до оплаты в Telegram — с прозрачной
              аналитикой и гибкой автоматизацией.
            </p>
            <div class="hero__cta">
              <a class="btn btn--primary btn--lg" href="#request">Оставить заявку</a>
              <a class="btn btn--ghost btn--lg" href="#features">Как это работает</a>
            </div>
            <p class="hero__note muted">Без регистрации на сайте — достаточно короткой формы, менеджер свяжется с вами.</p>
          </div>
          <div class="hero__visual" aria-hidden="true">
            <div class="hero-card">
              <p class="hero-card__label">Воронка «Реклама → бот»</p>
              <ul class="hero-card__steps">
                <li><span class="dot dot--on" /> Клик по креативу</li>
                <li><span class="dot dot--on" /> Старт в Telegram</li>
                <li><span class="dot dot--mid" /> Квалификация и оффер</li>
                <li><span class="dot dot--off" /> Оплата и выдача</li>
              </ul>
            </div>
          </div>
        </div>
      </section>

      <section id="features" class="section">
        <div class="landing-inner">
          <h2 class="section__title">Почему команды выбирают такой подход</h2>
          <p class="section__subtitle muted">Меньше ручной возни, больше предсказуемых конверсий — особенно когда трафик дорогой.</p>
          <div class="feature-grid">
            <article v-for="(f, i) in features" :key="i" class="feature-card">
              <h3>{{ f.title }}</h3>
              <p class="muted">{{ f.text }}</p>
            </article>
          </div>
        </div>
      </section>

      <section class="section section--muted">
        <div class="landing-inner">
          <h2 class="section__title">Три опоры продукта</h2>
          <div class="cards-row">
            <article v-for="(c, i) in cards" :key="i" class="info-card">
              <span class="info-card__tag">{{ c.tag }}</span>
              <h3>{{ c.title }}</h3>
              <p class="muted">{{ c.body }}</p>
            </article>
          </div>
        </div>
      </section>

      <section id="request" class="section section--cta">
        <div class="landing-inner cta-grid">
          <div>
            <h2 class="section__title">Подключение и демонстрация</h2>
            <p class="muted">
              Расскажите, какая у вас воронка и откуда трафик. Ответим с рабочими часами, пришлём детали по внедрению и доступу к панели.
            </p>
            <ul class="checklist">
              <li>Подбор сценария под ваш оффер</li>
              <li>Интеграция оплат и контента</li>
              <li>Сопровождение на запуске</li>
            </ul>
          </div>
          <form class="lead-form panel" @submit.prevent="submitLead">
            <h3 class="lead-form__title">Заявка</h3>
            <label class="field">
              <span class="field-label">Имя и фамилия</span>
              <input v-model="form.full_name" required autocomplete="name" placeholder="Иван Петров" />
            </label>
            <label class="field">
              <span class="field-label">Email</span>
              <input v-model="form.email" type="email" required autocomplete="email" placeholder="you@company.com" />
            </label>
            <label class="field">
              <span class="field-label">Телефон</span>
              <input v-model="form.phone" required autocomplete="tel" placeholder="+7 …" />
            </label>
            <label class="field">
              <span class="field-label">Компания или проект <span class="optional">необязательно</span></span>
              <input v-model="form.company" autocomplete="organization" placeholder="Название" />
            </label>
            <label class="field">
              <span class="field-label">Комментарий <span class="optional">необязательно</span></span>
              <textarea v-model="form.message" rows="4" placeholder="Ниша, источник трафика, что хотите автоматизировать" />
            </label>
            <div v-if="formError" class="banner banner--error" role="alert">{{ formError }}</div>
            <div v-if="formMessage" class="banner banner--success">{{ formMessage }}</div>
            <button type="submit" class="btn btn--primary btn--block" :disabled="submitting">
              {{ submitting ? "Отправляем…" : "Отправить заявку" }}
            </button>
            <p class="muted small form-hint">Нажимая кнопку, вы соглашаетесь на обработку данных для обратной связи.</p>
          </form>
        </div>
      </section>
    </main>

    <footer class="landing-footer">
      <div class="landing-inner landing-footer__row">
        <span class="muted small">© FunnelStack · платформа рекламных воронок</span>
        <RouterLink class="muted small footer-link" to="/admin">Панель администратора</RouterLink>
      </div>
    </footer>
  </div>
</template>

<style scoped>
.landing {
  min-height: 100vh;
  display: flex;
  flex-direction: column;
  background: linear-gradient(180deg, #f6f8fc 0%, #fff 32%, #fff 100%);
  color: var(--text, #1a1d26);
  font-family: Manrope, system-ui, sans-serif;
}

.landing-inner {
  width: 100%;
  max-width: 1120px;
  margin: 0 auto;
  padding: 0 clamp(16px, 4vw, 28px);
}

.landing-top {
  position: sticky;
  top: 0;
  z-index: 20;
  background: rgba(255, 255, 255, 0.92);
  backdrop-filter: blur(10px);
  border-bottom: 1px solid var(--line, #e0e4ec);
}

.landing-top__row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  min-height: 64px;
}

.logo-block {
  display: flex;
  align-items: center;
  gap: 10px;
  font-weight: 800;
  letter-spacing: -0.02em;
}

.logo-mark {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 36px;
  height: 36px;
  border-radius: 10px;
  background: linear-gradient(135deg, #1e5a8a, #2a7ab8);
  color: #fff;
  font-size: 1.1rem;
}

.logo-text {
  font-family: "Space Grotesk", Manrope, sans-serif;
  font-size: 1.125rem;
}

.top-nav {
  display: flex;
  align-items: center;
  gap: clamp(12px, 3vw, 24px);
  font-size: 0.9375rem;
}

.top-nav a {
  color: inherit;
  text-decoration: none;
}

.top-nav a:hover {
  color: #1e5a8a;
}

.top-nav__admin {
  padding: 8px 14px;
  border-radius: 999px;
  border: 1px solid var(--line);
  font-weight: 600;
}

.top-nav__admin:hover {
  border-color: #1e5a8a;
  background: rgba(30, 90, 138, 0.06);
}

.hero {
  padding: clamp(32px, 6vw, 72px) 0 clamp(48px, 8vw, 88px);
}

.hero__grid {
  display: grid;
  gap: clamp(32px, 5vw, 56px);
  align-items: center;
  grid-template-columns: 1fr;
}

@media (min-width: 900px) {
  .hero__grid {
    grid-template-columns: 1.1fr 0.9fr;
  }
}

.hero__eyebrow {
  text-transform: uppercase;
  letter-spacing: 0.08em;
  font-size: 0.75rem;
  font-weight: 800;
  color: #1e5a8a;
  margin: 0 0 12px;
}

.hero__title {
  font-family: "Space Grotesk", Manrope, sans-serif;
  font-size: clamp(2rem, 4.5vw, 2.75rem);
  line-height: 1.12;
  letter-spacing: -0.03em;
  margin: 0 0 16px;
  max-width: 16ch;
}

.hero__lead {
  font-size: 1.0625rem;
  line-height: 1.55;
  max-width: 52ch;
  margin: 0 0 24px;
  color: #3d4454;
}

.hero__cta {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
  margin-bottom: 16px;
}

.btn--lg {
  padding: 12px 22px;
  font-size: 1rem;
}

.hero__note {
  font-size: 0.875rem;
  max-width: 48ch;
}

.hero__visual {
  display: flex;
  justify-content: center;
}

.hero-card {
  width: 100%;
  max-width: 380px;
  padding: 24px;
  border-radius: 16px;
  background: #fff;
  border: 1px solid var(--line);
  box-shadow: 0 18px 48px rgba(30, 60, 90, 0.08);
}

.hero-card__label {
  font-weight: 700;
  margin: 0 0 16px;
  font-size: 0.9375rem;
}

.hero-card__steps {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 12px;
  font-size: 0.9375rem;
}

.hero-card__steps li {
  display: flex;
  align-items: center;
  gap: 10px;
}

.dot {
  width: 10px;
  height: 10px;
  border-radius: 50%;
  flex-shrink: 0;
}

.dot--on {
  background: #2e7d32;
  box-shadow: 0 0 0 3px rgba(46, 125, 50, 0.25);
}

.dot--mid {
  background: #f9a825;
  box-shadow: 0 0 0 3px rgba(249, 168, 37, 0.25);
}

.dot--off {
  background: #cfd4dc;
}

.section {
  padding: clamp(40px, 7vw, 72px) 0;
}

.section--muted {
  background: #f0f3f9;
}

.section__title {
  font-family: "Space Grotesk", Manrope, sans-serif;
  font-size: clamp(1.5rem, 3vw, 2rem);
  margin: 0 0 12px;
  letter-spacing: -0.02em;
}

.section__subtitle {
  max-width: 60ch;
  margin: 0 0 32px;
  font-size: 1.05rem;
}

.feature-grid {
  display: grid;
  gap: 20px;
  grid-template-columns: 1fr;
}

@media (min-width: 720px) {
  .feature-grid {
    grid-template-columns: repeat(2, 1fr);
  }
}

.feature-card {
  padding: 22px;
  border-radius: 14px;
  background: #fff;
  border: 1px solid var(--line);
}

.feature-card h3 {
  margin: 0 0 8px;
  font-size: 1.0625rem;
}

.feature-card p {
  margin: 0;
  line-height: 1.5;
}

.cards-row {
  display: grid;
  gap: 20px;
  grid-template-columns: 1fr;
}

@media (min-width: 800px) {
  .cards-row {
    grid-template-columns: repeat(3, 1fr);
  }
}

.info-card {
  padding: 22px;
  border-radius: 14px;
  background: #fff;
  border: 1px solid var(--line);
}

.info-card__tag {
  display: inline-block;
  font-size: 0.6875rem;
  font-weight: 800;
  text-transform: uppercase;
  letter-spacing: 0.06em;
  color: #1e5a8a;
  margin-bottom: 10px;
}

.info-card h3 {
  margin: 0 0 8px;
  font-size: 1.125rem;
}

.info-card p {
  margin: 0;
  line-height: 1.5;
}

.section--cta {
  padding-bottom: clamp(56px, 10vw, 96px);
}

.cta-grid {
  display: grid;
  gap: 32px;
  align-items: start;
}

@media (min-width: 880px) {
  .cta-grid {
    grid-template-columns: 1fr 1fr;
    gap: 48px;
  }
}

.checklist {
  margin: 20px 0 0;
  padding-left: 1.2em;
  line-height: 1.7;
  color: #3d4454;
}

.lead-form {
  padding: clamp(20px, 4vw, 28px);
}

.lead-form__title {
  margin: 0 0 16px;
  font-size: 1.25rem;
}

.lead-form .field textarea {
  width: 100%;
  box-sizing: border-box;
  border-radius: var(--radius-sm, 8px);
  border: 1px solid var(--line);
  padding: 10px 12px;
  font: inherit;
  resize: vertical;
  min-height: 100px;
}

.optional {
  font-weight: 400;
  color: var(--muted);
  font-size: 0.8125rem;
}

.form-hint {
  margin: 12px 0 0;
}

.landing-footer {
  margin-top: auto;
  border-top: 1px solid var(--line);
  background: #fff;
  padding: 20px 0;
}

.landing-footer__row {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.footer-link {
  color: inherit;
  text-decoration: none;
}

.footer-link:hover {
  color: #1e5a8a;
  text-decoration: underline;
}
</style>
