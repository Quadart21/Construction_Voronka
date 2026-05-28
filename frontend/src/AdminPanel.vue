<script setup>
import { provide } from "vue";
import { RouterLink } from "vue-router";
import { FUNNEL_ADMIN } from "./injectionKeys";
import { useFunnelAdmin } from "./composables/useFunnelAdmin";
import {
  DashboardView,
  ConversionsView,
  AccountingView,
  StepsView,
  ChainView,
  AutomationsView,
  UsersView,
  EventsView,
  SettingsView,
  AdminsView,
  LeadsView,
  BotsView
} from "./chunks/asyncViews";

const admin = useFunnelAdmin();
provide(FUNNEL_ADMIN, admin);

const {
  loginForm,
  isAuthenticated,
  sessionUser,
  authPhase,
  totpCode,
  setup2faQrUrl,
  setup2faSecret,
  tabGroups,
  state,
  activeTabMeta,
  tabLabel,
  loadAll,
  logout,
  handleLogin,
  submitTotp,
  submitSetup2fa,
  cancelTotpStep,
  newLeadsCount,
  activeBot,
  selectActiveBot
} = admin;

const viewByTab = {
  bots: BotsView,
  dashboard: DashboardView,
  conversions: ConversionsView,
  accounting: AccountingView,
  steps: StepsView,
  chain: ChainView,
  post_steps: StepsView,
  post_chain: ChainView,
  automations: AutomationsView,
  users: UsersView,
  events: EventsView,
  settings: SettingsView,
  admins: AdminsView,
  leads: LeadsView
};
</script>

<template>
  <div v-if="!isAuthenticated" class="login-screen">
    <div class="panel login-card">
      <template v-if="authPhase === 'password'">
        <p class="eyebrow">Панель управления ботом</p>
        <h1>Вход</h1>
        <p class="lead">Тот же адрес, что и у этой страницы — запросы идут на <code>/api</code>. Долгая сессия без повторного ввода пароля.</p>

        <label class="field">
          <span class="field-label">Логин</span>
          <input v-model="loginForm.username" autocomplete="username" placeholder="Логин администратора" @keyup.enter="handleLogin" />
        </label>
        <label class="field">
          <span class="field-label">Пароль</span>
          <input
            v-model="loginForm.password"
            type="password"
            autocomplete="current-password"
            placeholder="Пароль"
            @keyup.enter="handleLogin"
          />
        </label>

        <div v-if="state.error" class="banner banner--error" role="alert">{{ state.error }}</div>
        <button type="button" class="btn btn--primary" :disabled="state.loading" @click="handleLogin">
          {{ state.loading ? "Проверяем…" : "Далее" }}
        </button>
        <p class="muted small login-back">
          <RouterLink to="/">← На главную</RouterLink>
        </p>
      </template>

      <template v-else-if="authPhase === 'totp'">
        <p class="eyebrow">Двухфакторная защита</p>
        <h1>Код из приложения</h1>
        <p class="lead">Откройте приложение для кодов (Google Authenticator, Authy и т.п.) и введите 6 цифр.</p>
        <label class="field">
          <span class="field-label">Одноразовый код</span>
          <input v-model="totpCode" inputmode="numeric" autocomplete="one-time-code" placeholder="000000" @keyup.enter="submitTotp" />
        </label>
        <div v-if="state.error" class="banner banner--error" role="alert">{{ state.error }}</div>
        <div class="login-actions">
          <button type="button" class="btn btn--primary" :disabled="state.loading" @click="submitTotp">Войти</button>
          <button type="button" class="btn btn--ghost" :disabled="state.loading" @click="cancelTotpStep">Назад</button>
        </div>
      </template>

      <template v-else-if="authPhase === 'setup2fa'">
        <p class="eyebrow">Обязательная настройка</p>
        <h1>Включите 2FA</h1>
        <p class="lead">Отсканируйте QR в приложении для кодов или введите ключ вручную. Затем введите первый 6-значный код.</p>
        <div v-if="setup2faQrUrl" class="qr-wrap">
          <img :src="setup2faQrUrl" width="200" height="200" alt="QR для приложения" class="qr-img" />
        </div>
        <p v-if="setup2faSecret" class="muted small">
          Ключ вручную: <code class="secret-code">{{ setup2faSecret }}</code>
        </p>
        <label class="field">
          <span class="field-label">Код подтверждения</span>
          <input v-model="totpCode" inputmode="numeric" autocomplete="one-time-code" placeholder="000000" @keyup.enter="submitSetup2fa" />
        </label>
        <div v-if="state.error" class="banner banner--error" role="alert">{{ state.error }}</div>
        <div v-if="state.success" class="banner banner--success">{{ state.success }}</div>
        <div class="login-actions">
          <button type="button" class="btn btn--primary" :disabled="state.loading" @click="submitSetup2fa">Подтвердить и войти</button>
          <button type="button" class="btn btn--ghost" :disabled="state.loading" @click="cancelTotpStep">Назад</button>
        </div>
      </template>
    </div>
  </div>

  <div v-else class="shell">
    <aside class="sidebar" aria-label="Разделы">
      <div class="brand">
        <p class="eyebrow">Telegram-воронка</p>
        <h1 class="brand-title">Управление</h1>
        <p v-if="sessionUser" class="muted small">Вы вошли как <strong>{{ sessionUser.username }}</strong></p>
        <p v-else class="muted small">Всё в одном месте: от текстов до оплат.</p>
      </div>

      <div class="sidebar-toolbar">
        <RouterLink class="btn btn--ghost btn--block sidebar-link" to="/">На сайт</RouterLink>
        <button type="button" class="btn btn--primary btn--block" :disabled="state.loading" @click="loadAll">Обновить данные</button>
        <button type="button" class="btn btn--ghost btn--block" @click="logout">Выйти</button>
      </div>

      <nav class="nav">
        <div v-for="group in tabGroups" :key="group.title" class="nav-group">
          <div class="nav-group-head">
            <span class="nav-group-title">{{ group.title }}</span>
            <span class="nav-group-hint">{{ group.hint }}</span>
          </div>
          <button
            v-for="tab in group.items"
            :key="tab.key"
            type="button"
            class="nav-item"
            :class="{ 'nav-item--active': state.activeTab === tab.key }"
            :title="tab.description"
            @click="state.activeTab = tab.key"
          >
            <span class="nav-item-label-row">
              <span class="nav-item-label">{{ tab.label }}</span>
              <span v-if="tab.key === 'leads' && newLeadsCount > 0" class="nav-badge" :title="`Новых заявок: ${newLeadsCount}`">{{
                newLeadsCount
              }}</span>
            </span>
            <span class="nav-item-desc">{{ tab.description }}</span>
          </button>
        </div>
      </nav>
    </aside>

    <main class="content">
      <header class="page-head">
        <div>
          <p class="eyebrow">{{ tabLabel(state.activeTab) }}</p>
          <h1>{{ activeTabMeta.label }}</h1>
          <p class="muted">{{ activeTabMeta.description }}</p>
        </div>
      </header>

      <div v-if="state.error" class="banner banner--error" role="alert">{{ state.error }}</div>
      <div v-if="state.success" class="banner banner--success">{{ state.success }}</div>
      <div v-if="state.loading" class="banner banner--info">Загружаем…</div>

      <component :is="viewByTab[state.activeTab]" />
    </main>
  </div>
</template>

<style scoped>
.login-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  margin-top: 8px;
}
.login-back {
  margin-top: 16px;
}
.login-back a {
  color: var(--accent, #1e5a8a);
  text-decoration: none;
}
.login-back a:hover {
  text-decoration: underline;
}
.qr-wrap {
  display: flex;
  justify-content: center;
  margin: 12px 0;
}
.qr-img {
  border-radius: var(--radius-sm, 8px);
  border: 1px solid var(--line, #e0e4ec);
}
.secret-code {
  user-select: all;
  word-break: break-all;
}
.sidebar-link {
  text-decoration: none;
  text-align: center;
  box-sizing: border-box;
}
.nav-item-label-row {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}
.page-head {
  display: flex;
  flex-wrap: wrap;
  justify-content: space-between;
  align-items: flex-end;
  gap: 16px;
}
.bot-switcher {
  min-width: 200px;
  margin: 0;
}
.bot-context {
  margin-top: 8px;
}
.nav-badge {
  font-size: 0.6875rem;
  font-weight: 800;
  min-width: 1.25rem;
  padding: 2px 6px;
  border-radius: 999px;
  background: #c62828;
  color: #fff;
  line-height: 1.2;
}
</style>
