<script setup>
import { inject } from "vue";
import { FUNNEL_ADMIN } from "../injectionKeys";

const { state, saveSetting, uploadAdminFile, isImagePreview, isVideoPreview, mediaPreviewUrl, mediaTypeLabel, addDeliveryButton, removeDeliveryButton } =
  inject(FUNNEL_ADMIN);
</script>

<template>
  <section class="stack">
    <article class="panel form-stack">
      <h2>Тексты бота</h2>
      <p class="muted small">Сообщения, которые люди видят до входа в основную цепочку или при ошибке.</p>
      <label class="field">
        <span class="field-label">Приветствие</span>
        <textarea v-model="state.settings.funnel_copy.welcome" placeholder="Первое сообщение"></textarea>
      </label>
      <label class="field">
        <span class="field-label">Если написал не в ту ветку</span>
        <textarea v-model="state.settings.funnel_copy.invalid_input" placeholder="Мягкая подсказка"></textarea>
      </label>
      <label class="field">
        <span class="field-label">Затравка к предложению</span>
        <textarea v-model="state.settings.funnel_copy.core_offer_hint" placeholder="Перед блоком с ценой"></textarea>
      </label>
      <button type="button" class="btn btn--primary" @click="saveSetting('funnel_copy')">Сохранить тексты</button>
    </article>

    <article class="panel form-stack">
      <h2>Оплата</h2>
      <p class="muted small">Эти поля уходят в платёжную систему — сумму и валюту меняйте осознанно.</p>
      <label class="field">
        <span class="field-label">Короткое название offера</span>
        <input v-model="state.settings.offer.price_label" placeholder="Например: Полный доступ" />
      </label>
      <label class="field">
        <span class="field-label">Текст перед оплатой</span>
        <textarea v-model="state.settings.offer.price_text" placeholder="Что человек получит"></textarea>
      </label>
      <div class="two-cols">
        <label class="field">
          <span class="field-label">Сумма</span>
          <input v-model.number="state.settings.offer.amount" type="number" min="0" />
        </label>
        <label class="field">
          <span class="field-label">Валюта</span>
          <input v-model="state.settings.offer.currency" placeholder="RUB" />
        </label>
      </div>
      <details class="panel soft-panel">
        <summary>Технические поля Platega</summary>
        <label class="field">
          <span class="field-label">Способ оплаты (число из кабинета)</span>
          <input v-model.number="state.settings.offer.payment_method" type="number" />
        </label>
        <label class="field">
          <span class="field-label">Описание платежа</span>
          <input v-model="state.settings.offer.description" placeholder="Видно в платёжке" />
        </label>
      </details>
      <button type="button" class="btn btn--primary" @click="saveSetting('offer')">Сохранить оплату</button>
    </article>

    <article class="panel form-stack">
      <div class="section-head">
        <div>
          <h2>После успешной оплаты</h2>
          <p class="muted small">Бот отправит это сообщение, когда оплата подтверждена.</p>
        </div>
        <button type="button" class="btn btn--secondary" @click="saveSetting('offer')">Сохранить выдачу</button>
      </div>

      <label class="field">
        <span class="field-label">Заголовок</span>
        <input v-model="state.settings.offer.delivery.title" placeholder="Спасибо за оплату" />
      </label>
      <label class="field">
        <span class="field-label">Основной текст</span>
        <textarea v-model="state.settings.offer.delivery.text" placeholder="Что получил и что делать дальше"></textarea>
      </label>

      <div class="two-cols">
        <label class="field">
          <span class="field-label">Тип файла / медиа</span>
          <select v-model="state.settings.offer.delivery.media_type">
            <option value="">Без вложения</option>
            <option value="photo">Фото</option>
            <option value="video">Видео</option>
            <option value="animation">GIF</option>
            <option value="document">Файл</option>
          </select>
        </label>
        <label class="field">
          <span class="field-label">Файл или ссылка</span>
          <input v-model="state.settings.offer.delivery.media_url" placeholder="Загрузить или вставить URL" />
          <input type="file" class="file-input" @change="uploadAdminFile($event, state.settings.offer.delivery)" />
          <div v-if="state.settings.offer.delivery.media_url" class="media-preview">
            <img
              v-if="isImagePreview(state.settings.offer.delivery)"
              :src="mediaPreviewUrl(state.settings.offer.delivery.media_url)"
              alt=""
            />
            <video
              v-else-if="isVideoPreview(state.settings.offer.delivery)"
              :src="mediaPreviewUrl(state.settings.offer.delivery.media_url)"
              controls
              playsinline
            ></video>
            <a v-else :href="mediaPreviewUrl(state.settings.offer.delivery.media_url)" target="_blank" rel="noreferrer">{{
              mediaTypeLabel(state.settings.offer.delivery.media_type)
            }}</a>
            <span class="muted small">{{ mediaTypeLabel(state.settings.offer.delivery.media_type) }}</span>
          </div>
        </label>
      </div>

      <label class="field">
        <span class="field-label">Подпись к медиа</span>
        <textarea v-model="state.settings.offer.delivery.media_caption" placeholder="Необязательно"></textarea>
      </label>

      <div class="delivery-buttons">
        <div class="route-top">
          <strong>Кнопки со ссылками</strong>
          <button type="button" class="btn btn--ghost btn--sm" @click="addDeliveryButton">Добавить</button>
        </div>
        <div v-if="!state.settings.offer.delivery.buttons.length" class="empty-line">Кнопок нет — можно добавить чат или материал.</div>
        <div v-for="(button, index) in state.settings.offer.delivery.buttons" :key="index" class="delivery-button-row">
          <input v-model="button.text" placeholder="Текст кнопки" />
          <input v-model="button.url" placeholder="https://..." />
          <button type="button" class="btn btn--ghost btn--sm" @click="removeDeliveryButton(index)">Удалить</button>
        </div>
      </div>

      <details class="panel soft-panel">
        <summary>Webhook для Platega</summary>
        <p class="muted small">URL в кабинете: <code>/api/webhooks/platega</code> на вашем домене или IP.</p>
      </details>
    </article>
  </section>
</template>
