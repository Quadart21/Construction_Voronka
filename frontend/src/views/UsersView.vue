<script setup>
import { inject } from "vue";
import { FUNNEL_ADMIN } from "../injectionKeys";
import { customerLabel } from "../utils/formatting";

const { userSearch, filteredUsers, stepTitleByCode } = inject(FUNNEL_ADMIN);
</script>

<template>
  <section class="panel form-stack">
    <h2>Подписчики</h2>
    <p class="muted small">Показаны последние 200 человек из базы.</p>
    <label class="field">
      <span class="field-label">Поиск по имени или ID</span>
      <input v-model="userSearch" placeholder="Начните вводить…" />
    </label>
    <div v-if="!filteredUsers.length" class="empty-state">Никого не нашли — попробуйте другой запрос</div>
    <div v-else class="table-wrap">
      <div class="table">
        <div class="row row--head"><span>В Telegram</span><span>Имя</span><span>Сейчас на шаге</span><span>Клиент</span></div>
        <div v-for="user in filteredUsers" :key="user.id" class="row">
          <span>{{ user.telegram_id }}</span>
          <span>{{ user.full_name }}</span>
          <span>{{ stepTitleByCode(user.current_step) }}</span>
          <span>{{ customerLabel(user.is_customer) }}</span>
        </div>
      </div>
    </div>
  </section>
</template>
