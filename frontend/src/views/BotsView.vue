<script setup>
import { inject } from "vue";
import { FUNNEL_ADMIN } from "../injectionKeys";

const admin = inject(FUNNEL_ADMIN);
const { state, botForm, activeBot, selectActiveBot, saveBot, editBot, resetBotForm, deactivateBot } = admin;
</script>

<template>
  <section class="stack">
    <article class="panel form-stack">
      <div class="section-head">
        <div>
          <h2>Активный бот</h2>
          <p class="muted small">Воронка, настройки и статистика ниже относятся к выбранному боту.</p>
        </div>
      </div>

      <label v-if="state.bots.length" class="field">
        <span class="field-label">Сейчас редактируем</span>
        <select :value="state.activeBotId" @change="selectActiveBot(Number($event.target.value))">
          <option v-for="bot in state.bots" :key="bot.id" :value="bot.id">
            {{ bot.name }}{{ bot.username ? ` (@${bot.username})` : "" }}{{ bot.is_active ? "" : " — выкл." }}
          </option>
        </select>
      </label>

      <p v-else class="muted">Пока нет ботов. Добавьте первого по токену от @BotFather.</p>
      <p v-if="activeBot" class="muted small">
        Токен в базе: <code>{{ activeBot.token_masked }}</code>
      </p>
    </article>

    <article class="panel form-stack">
      <div class="section-head">
        <div>
          <h2>{{ botForm.id ? "Изменить бота" : "Новый бот" }}</h2>
          <p class="muted small">Токен берите у @BotFather. После сохранения бот сразу запускается на сервере.</p>
        </div>
        <button v-if="botForm.id" type="button" class="btn btn--ghost" @click="resetBotForm">Отмена</button>
      </div>

      <label class="field">
        <span class="field-label">Название в панели</span>
        <input v-model="botForm.name" placeholder="Например: Воронка Instagram" />
      </label>

      <label class="field">
        <span class="field-label">Токен Telegram</span>
        <input v-model="botForm.token" type="password" autocomplete="off" :placeholder="botForm.id ? 'Оставьте пустым, чтобы не менять' : '123456789:AAH…'" />
      </label>

      <div class="two-cols">
        <label class="field field--inline-check">
          <span class="field-label">Статус</span>
          <select v-model="botForm.is_active">
            <option :value="true">Включён</option>
            <option :value="false">Выключен</option>
          </select>
        </label>
        <label class="field">
          <span class="field-label">Порядок в списке</span>
          <input v-model.number="botForm.sort_order" type="number" min="0" />
        </label>
      </div>

      <button type="button" class="btn btn--primary" :disabled="state.loading" @click="saveBot">
        {{ botForm.id ? "Сохранить изменения" : "Добавить бота" }}
      </button>
    </article>

    <article v-if="state.bots.length" class="panel">
      <h2>Все боты</h2>
      <ul class="bot-list">
        <li v-for="bot in state.bots" :key="bot.id" class="bot-list__item">
          <div>
            <strong>{{ bot.name }}</strong>
            <span v-if="bot.username" class="muted small"> @{{ bot.username }}</span>
            <span v-if="!bot.is_active" class="muted small"> · выключен</span>
            <p class="muted small">Токен: {{ bot.token_masked }}</p>
          </div>
          <div class="bot-list__actions">
            <button type="button" class="btn btn--ghost btn--sm" @click="editBot(bot)">Изменить</button>
            <button
              v-if="state.bots.length > 1 && bot.is_active"
              type="button"
              class="btn btn--ghost btn--sm"
              @click="deactivateBot(bot)"
            >
              Отключить
            </button>
          </div>
        </li>
      </ul>
    </article>
  </section>
</template>

<style scoped>
.bot-list {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.bot-list__item {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 16px;
  padding: 12px 0;
  border-bottom: 1px solid var(--line, #e8ebf0);
}
.bot-list__item:last-child {
  border-bottom: none;
}
.bot-list__actions {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}
</style>
