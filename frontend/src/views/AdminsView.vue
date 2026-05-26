<script setup>
import { inject, onMounted } from "vue";
import { FUNNEL_ADMIN } from "../injectionKeys";
import { formatDateTime } from "../utils/formatting";

const {
  state,
  sessionUser,
  adminsList,
  newAdminForm,
  loadAdmins,
  createAdminUser,
  deleteAdminUser
} = inject(FUNNEL_ADMIN);

onMounted(() => {
  loadAdmins();
});
</script>

<template>
  <section class="stack">
    <article class="panel form-stack">
      <h2>Новый администратор</h2>
      <p class="muted small">
        После добавления человек входит своим логином и паролем. При первом входе система обязательно попросит настроить двухфакторную защиту (приложение с кодами).
      </p>
      <div class="two-cols">
        <label class="field">
          <span class="field-label">Логин</span>
          <input v-model="newAdminForm.username" autocomplete="off" placeholder="Например: maria" />
        </label>
        <label class="field">
          <span class="field-label">Пароль (не короче 8 символов)</span>
          <input v-model="newAdminForm.password" type="password" autocomplete="new-password" placeholder="Надёжный пароль" />
        </label>
      </div>
      <button type="button" class="btn btn--primary" :disabled="state.loading" @click="createAdminUser">Добавить</button>
    </article>

    <article class="panel">
      <h2>Список</h2>
      <p v-if="sessionUser" class="muted small">Вы вошли как <strong>{{ sessionUser.username }}</strong> (id {{ sessionUser.id }}).</p>
      <div v-if="!adminsList.length" class="empty-state">Пока нет записей.</div>
      <div v-else class="table-wrap">
        <div class="table table--admins">
          <div class="row row--head row--admins-head">
            <span>Логин</span><span>2FA</span><span>Статус</span><span>Создан</span><span></span>
          </div>
          <div v-for="row in adminsList" :key="row.id" class="row row--admins">
            <span>{{ row.username }}</span>
            <span>{{ row.totp_confirmed ? "Включена" : "Ждёт настройки" }}</span>
            <span>{{ row.is_active ? "Активен" : "Отключён" }}</span>
            <span>{{ formatDateTime(row.created_at) }}</span>
            <span class="chips">
              <button
                v-if="row.is_active && sessionUser && row.id !== sessionUser.id"
                type="button"
                class="btn btn--danger btn--ghost btn--sm"
                @click="deleteAdminUser(row.id)"
              >
                Отключить
              </button>
              <span v-else-if="sessionUser && row.id === sessionUser.id" class="muted small">Это вы</span>
            </span>
          </div>
        </div>
      </div>
    </article>
  </section>
</template>
