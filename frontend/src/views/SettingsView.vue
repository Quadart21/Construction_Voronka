<script setup>
import { inject } from "vue";
import { FUNNEL_ADMIN } from "../injectionKeys";

const {
  state,
  saveSetting,
  uploadAdminFile,
  isImagePreview,
  isVideoPreview,
  mediaPreviewUrl,
  mediaTypeLabel,
  addDeliveryButton,
  removeDeliveryButton,
  addSubscriptionChannel,
  removeSubscriptionChannel,
  fetchNorenRates,
  isNorenCryptoAllowed,
  toggleNorenCrypto,
  norenRates,
  norenRatesLoading
} = inject(FUNNEL_ADMIN);
</script>

<template>
  <section class="stack">
    <article class="panel form-stack">
      <div class="section-head">
        <div>
          <h2>Обязательная подписка</h2>
          <p class="muted small">
            Настройка для <strong>текущего бота</strong> в переключателе сверху. Пока человек не подпишется на указанные каналы, бот не
            пустит в воронку. Бот должен быть <strong>администратором</strong> каждого канала.
          </p>
        </div>
        <button type="button" class="btn btn--primary" @click="saveSetting('subscription_gate')">Сохранить</button>
      </div>

      <label class="field field--inline-check">
        <span class="field-label">Включить проверку подписки</span>
        <select v-model="state.settings.subscription_gate.enabled">
          <option :value="false">Выключено</option>
          <option :value="true">Включено</option>
        </select>
      </label>

      <label class="field field--inline-check">
        <span class="field-label">Условие доступа</span>
        <select v-model="state.settings.subscription_gate.require_all">
          <option :value="true">Подписка на все каналы из списка</option>
          <option :value="false">Достаточно любого одного канала</option>
        </select>
      </label>

      <div class="channels-block">
        <div class="section-head">
          <h3 class="channels-block__title">Каналы для проверки</h3>
          <button type="button" class="btn btn--ghost btn--sm" @click="addSubscriptionChannel">+ Добавить канал</button>
        </div>

        <p v-if="!state.settings.subscription_gate.channels.length" class="muted small">
          Добавьте хотя бы один канал (@username или -100…), иначе проверка не включится.
        </p>

        <div
          v-for="(channel, index) in state.settings.subscription_gate.channels"
          :key="index"
          class="channel-card panel panel--nested"
        >
          <div class="section-head">
            <strong>Канал {{ index + 1 }}</strong>
            <button type="button" class="btn btn--ghost btn--sm" @click="removeSubscriptionChannel(index)">Удалить</button>
          </div>

          <label class="field">
            <span class="field-label">ID канала</span>
            <input v-model="channel.channel_id" placeholder="@your_channel или -1001234567890" />
            <span class="muted small">Username или числовой ID. Бот — админ в этом канале.</span>
          </label>

          <label class="field">
            <span class="field-label">Подпись на кнопке</span>
            <input v-model="channel.title" placeholder="Например: Новости проекта" />
          </label>

          <label class="field">
            <span class="field-label">Ссылка (необязательно)</span>
            <input v-model="channel.subscribe_url" placeholder="https://t.me/your_channel" />
            <span class="muted small">Если пусто — соберём из @username канала.</span>
          </label>
        </div>
      </div>

      <label class="field">
        <span class="field-label">Текст экрана подписки</span>
        <textarea v-model="state.settings.subscription_gate.message" rows="3" placeholder="Подпишитесь, чтобы открыть бот"></textarea>
      </label>

      <label class="field">
        <span class="field-label">Подсказка, если подписка не найдена</span>
        <input v-model="state.settings.subscription_gate.not_subscribed_hint" placeholder="Всплывающее сообщение при проверке" />
        <span class="muted small">К списку неподписанных каналов добавится автоматически.</span>
      </label>

      <label class="field">
        <span class="field-label">Текст кнопки «Проверить»</span>
        <input v-model="state.settings.subscription_gate.check_button_text" placeholder="Я подписался — проверить" />
      </label>

      <label class="field field--inline-check">
        <span class="field-label">Не требовать подписку у тех, кто уже оплатил</span>
        <select v-model="state.settings.subscription_gate.skip_for_paid_users">
          <option :value="true">Да — оплатившие проходят без проверки</option>
          <option :value="false">Нет — проверять всех</option>
        </select>
      </label>
    </article>

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
      <h2>Оффер и оплата</h2>
      <p class="muted small">Цена, валюта и что показать после успешной оплаты.</p>

      <div class="two-cols">
        <label class="field">
          <span class="field-label">Сумма (копейки/центы)</span>
          <input v-model.number="state.settings.offer.amount" type="number" min="0" />
        </label>
        <label class="field">
          <span class="field-label">Валюта</span>
          <input v-model="state.settings.offer.currency" placeholder="RUB" />
        </label>
      </div>

      <label class="field">
        <span class="field-label">Описание платежа</span>
        <input v-model="state.settings.offer.description" placeholder="Текст в платёжной системе" />
      </label>

      <label class="field">
        <span class="field-label">Текст перед ценой</span>
        <textarea v-model="state.settings.offer.price_text" rows="2"></textarea>
      </label>

      <h3 class="subhead">Выдача после оплаты</h3>
      <p class="muted small">
        Если настроена цепочка «После оплаты», она идёт после короткого сообщения ниже (если включено). Иначе — только это сообщение.
      </p>

      <label class="field field--inline-check">
        <span class="field-label">Сначала короткое сообщение, потом цепочка</span>
        <select v-model="state.settings.offer.delivery.send_before_chain">
          <option :value="false">Нет — сразу цепочка после оплаты</option>
          <option :value="true">Да — короткое сообщение, затем цепочка</option>
        </select>
      </label>

      <label class="field">
        <span class="field-label">Заголовок</span>
        <input v-model="state.settings.offer.delivery.title" placeholder="Доступ открыт" />
      </label>
      <label class="field">
        <span class="field-label">Текст</span>
        <textarea v-model="state.settings.offer.delivery.text" rows="3"></textarea>
      </label>

      <div class="two-cols">
        <label class="field">
          <span class="field-label">Тип медиа</span>
          <select v-model="state.settings.offer.delivery.media_type">
            <option value="">Без медиа</option>
            <option value="photo">Фото</option>
            <option value="video">Видео</option>
            <option value="animation">GIF</option>
          </select>
        </label>
        <label class="field">
          <span class="field-label">Подпись к медиа</span>
          <input v-model="state.settings.offer.delivery.media_caption" />
        </label>
      </div>

      <label v-if="state.settings.offer.delivery.media_type" class="field">
        <span class="field-label">Медиа ({{ mediaTypeLabel(state.settings.offer.delivery) }})</span>
        <input v-model="state.settings.offer.delivery.media_url" placeholder="upload://… или https://…" />
        <input type="file" accept="image/*,video/*" @change="uploadAdminFile($event, state.settings.offer.delivery)" />
        <img
          v-if="isImagePreview(state.settings.offer.delivery)"
          :src="mediaPreviewUrl(state.settings.offer.delivery.media_url)"
          alt=""
          class="media-preview"
        />
        <video
          v-else-if="isVideoPreview(state.settings.offer.delivery)"
          :src="mediaPreviewUrl(state.settings.offer.delivery.media_url)"
          controls
          class="media-preview"
        />
      </label>

      <div class="delivery-buttons">
        <div class="section-head">
          <h3 class="subhead">Кнопки с ссылками</h3>
          <button type="button" class="btn btn--ghost btn--sm" @click="addDeliveryButton">+ Кнопка</button>
        </div>
        <div v-for="(btn, idx) in state.settings.offer.delivery.buttons" :key="idx" class="two-cols delivery-btn-row">
          <label class="field">
            <span class="field-label">Текст</span>
            <input v-model="btn.text" />
          </label>
          <label class="field">
            <span class="field-label">URL</span>
            <div class="inline-field">
              <input v-model="btn.url" placeholder="https://…" />
              <button type="button" class="btn btn--ghost btn--sm" @click="removeDeliveryButton(idx)">×</button>
            </div>
          </label>
        </div>
      </div>

      <button type="button" class="btn btn--primary" @click="saveSetting('offer')">Сохранить оффер</button>
    </article>

    <article class="panel form-stack">
      <div class="section-head">
        <div>
          <h2>Способы оплаты</h2>
          <p class="muted small">
            Включите Platega (карта / СБП) и/или Noren (крипта). Если оба включены — пользователь выбирает способ в боте.
            Webhook Noren: <code>/api/webhooks/noren</code> или <code>/api/webhooks/crypto_cash</code>.
            Подпись: заголовок <code>X-Merset-Signature</code>.
          </p>
        </div>
        <button type="button" class="btn btn--primary" @click="saveSetting('payment')">Сохранить</button>
      </div>

      <label class="field field--inline-check">
        <span class="field-label">Platega — карта и СБП</span>
        <select v-model="state.settings.payment.platega.enabled">
          <option :value="false">Выключено</option>
          <option :value="true">Включено</option>
        </select>
      </label>
      <p class="muted small">Ключи Platega задаются в <code>.env</code> на сервере (PLATEGA_*).</p>

      <label class="field field--inline-check">
        <span class="field-label">Noren — криптовалюта</span>
        <select v-model="state.settings.payment.noren.enabled">
          <option :value="false">Выключено</option>
          <option :value="true">Включено</option>
        </select>
      </label>

      <template v-if="state.settings.payment.noren.enabled">
        <div class="two-cols">
          <label class="field">
            <span class="field-label">API Key</span>
            <input v-model="state.settings.payment.noren.api_key" autocomplete="off" />
          </label>
          <label class="field">
            <span class="field-label">API Secret</span>
            <input v-model="state.settings.payment.noren.api_secret" type="password" autocomplete="off" />
          </label>
        </div>

        <div class="two-cols">
          <label class="field">
            <span class="field-label">Project ID</span>
            <input v-model="state.settings.payment.noren.project_id" />
          </label>
          <label class="field">
            <span class="field-label">Webhook secret</span>
            <input v-model="state.settings.payment.noren.webhook_secret" type="password" autocomplete="off" />
          </label>
        </div>

        <label class="field">
          <span class="field-label">Base URL API</span>
          <input v-model="state.settings.payment.noren.base_url" placeholder="https://noren.digital/api/v1/client" />
        </label>

        <div class="section-head">
          <h3 class="subhead">Цена крипто-оплаты</h3>
        </div>
        <p class="muted small">
          Noren принимает только <strong>USD</strong>. Если указываете цену в рублях — укажите курс конвертации; в API уйдёт сумма в долларах.
          Оплата картой (Platega) по-прежнему берёт цену из блока «Оффер и оплата».
        </p>

        <div class="two-cols">
          <label class="field">
            <span class="field-label">Сумма</span>
            <input v-model="state.settings.payment.noren.price" placeholder="Например: 99 или 9900" />
          </label>
          <label class="field">
            <span class="field-label">Валюта суммы</span>
            <select v-model="state.settings.payment.noren.price_currency">
              <option value="USD">USD — отправится как есть</option>
              <option value="RUB">RUB — конвертируется в USD</option>
            </select>
          </label>
        </div>

        <label v-if="state.settings.payment.noren.price_currency === 'RUB'" class="field">
          <span class="field-label">Курс: RUB за 1 USD</span>
          <input v-model="state.settings.payment.noren.usd_rub_rate" placeholder="Например: 92.5" />
          <span class="muted small">Пример: цена 9900 RUB при курсе 99 → в Noren уйдёт 100 USD.</span>
        </label>

        <div class="section-head">
          <h3 class="subhead">Криптовалюты для пользователей</h3>
          <button type="button" class="btn btn--ghost btn--sm" :disabled="norenRatesLoading" @click="fetchNorenRates">
            {{ norenRatesLoading ? "Загрузка…" : "Загрузить из Noren" }}
          </button>
        </div>
        <p class="muted small">
          Загрузите список из Noren и отметьте, какими криптовалютами может платить пользователь. Сохраните настройки после выбора.
        </p>

        <div v-if="norenRates.length" class="panel panel--nested crypto-picker">
          <label v-for="rate in norenRates" :key="`${rate.currency}|${rate.network}`" class="field field--inline-check crypto-picker__item">
            <input
              type="checkbox"
              :checked="isNorenCryptoAllowed(rate)"
              @change="toggleNorenCrypto(rate, $event.target.checked)"
            />
            <span>{{ rate.label }}</span>
          </label>
        </div>
        <p v-else class="muted small">Сначала загрузите валюты из Noren, затем отметьте нужные.</p>
        <p v-if="state.settings.payment.noren.allowed_cryptos.length" class="muted small">
          Выбрано: {{ state.settings.payment.noren.allowed_cryptos.length }}
        </p>

        <h3 class="subhead">Защита от массовых заявок</h3>
        <p class="muted small">
          Ограничивает создание новых крипто-счетов одним пользователем. Если счёт ещё активен — показывается снова без нового запроса в Noren.
        </p>

        <label class="field field--inline-check">
          <span class="field-label">Показывать активный счёт повторно</span>
          <select v-model="state.settings.payment.noren.invoice_reuse_active">
            <option :value="true">Да — не создавать новый, пока не истёк</option>
            <option :value="false">Нет — каждый раз новая заявка (с лимитами ниже)</option>
          </select>
        </label>

        <div class="two-cols">
          <label class="field">
            <span class="field-label">Макс. новых счетов в час на пользователя</span>
            <input v-model.number="state.settings.payment.noren.invoice_max_per_hour" type="number" min="1" max="20" />
          </label>
          <label class="field">
            <span class="field-label">Пауза между новыми счетами (мин.)</span>
            <input v-model.number="state.settings.payment.noren.invoice_cooldown_minutes" type="number" min="0" max="1440" />
          </label>
        </div>
      </template>
    </article>
  </section>
</template>

<style scoped>
.channels-block {
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.channels-block__title {
  margin: 0;
  font-size: 1rem;
}
.channel-card {
  padding: 14px;
}
.panel--nested {
  background: var(--surface-2, #f6f7fa);
  border: 1px solid var(--line, #e0e4ec);
  border-radius: var(--radius-sm, 8px);
}
.delivery-btn-row {
  align-items: end;
}
.inline-field {
  display: flex;
  gap: 8px;
  align-items: center;
}
.inline-field input {
  flex: 1;
}
.media-preview {
  max-width: 100%;
  max-height: 200px;
  margin-top: 8px;
  border-radius: var(--radius-sm, 8px);
}
.subhead {
  margin: 16px 0 8px;
  font-size: 1rem;
}
.crypto-picker {
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding: 14px;
}
.crypto-picker__item {
  margin: 0;
  gap: 10px;
}
</style>
