<script setup>
import { computed, inject } from "vue";
import { FUNNEL_ADMIN } from "../injectionKeys";

const {
  state,
  stepDraft,
  branchDraft,
  branchTypeRef,
  orderedSteps,
  nextStepOptions,
  branchesForCurrentStep,
  resetStepDraft,
  resetBranchDraft,
  stepTypeLabel,
  mediaTypeLabel,
  mediaPreviewUrl,
  isImagePreview,
  isVideoPreview,
  transitionLabel,
  buttonsLabel,
  uploadAdminFile,
  editStep,
  createStepAfter,
  editBranch,
  saveStep,
  saveBranch,
  deleteBranch,
  deleteStep,
  stepTitleByCode
} = inject(FUNNEL_ADMIN);

const isPostPayment = computed(() => state.funnelPhase === "post_payment");
</script>

<template>
  <section class="stack">
    <article class="panel form-stack simple-editor">
      <div class="section-head">
        <div>
          <h2>{{ stepDraft.id ? "Редактировать шаг" : isPostPayment ? "Новый шаг после оплаты" : "Новый шаг" }}</h2>
          <p class="muted small">
            {{
              isPostPayment
                ? "Эти сообщения увидят только те, кто уже оплатил. Соберите цепочку в разделе «Порядок после оплаты»."
                : "Пользователь увидит только текст, кнопки и медиа — технические поля спрятаны ниже."
            }}
          </p>
        </div>
        <button v-if="stepDraft.id" type="button" class="btn btn--ghost" @click="resetStepDraft">Очистить и создать новый</button>
      </div>

      <div class="editor-block">
        <span class="editor-number">1</span>
        <div>
          <h3>Сообщение</h3>
          <label class="field">
            <span class="field-label">Название для себя</span>
            <input v-model="stepDraft.title" placeholder="Например: Полезный чек-лист" />
          </label>
          <label class="field">
            <span class="field-label">Текст в Telegram</span>
            <textarea v-model="stepDraft.body" placeholder="Пишите так, как говорили бы вслух"></textarea>
          </label>
          <label class="field">
            <span class="field-label">Слова-триггеры</span>
            <input v-model="stepDraft.trigger_keywords" placeholder="Например: Magic, магия, бонус" />
            <span class="muted small">Если человек напишет одно из этих слов, бот сразу покажет этот шаг.</span>
          </label>
        </div>
      </div>

      <div class="editor-block">
        <span class="editor-number">2</span>
        <div>
          <h3>Главная кнопка под сообщением</h3>
          <div class="two-cols">
            <label class="field">
              <span class="field-label">Надпись на кнопке</span>
              <input v-model="stepDraft.cta_text" placeholder="Например: Дальше" />
            </label>
            <label class="field">
              <span class="field-label">Куда вести после нажатия</span>
              <select v-model="stepDraft.next_step_code">
                <option value="">Закончить цепочку здесь</option>
                <option v-for="item in nextStepOptions" :key="item.id" :value="item.code">{{ item.title }}</option>
              </select>
            </label>
          </div>
        </div>
      </div>

      <div class="editor-block">
        <span class="editor-number">3</span>
        <div>
          <h3>Тип шага</h3>
          <div class="two-cols">
            <label class="field">
              <span class="field-label">Роль шага</span>
              <select v-model="stepDraft.step_type">
                <option v-if="!isPostPayment" value="segment_entry">Старт</option>
                <option value="content">Польза / контент</option>
                <option value="offer">Предложение / выдача</option>
                <option v-if="!isPostPayment" value="payment">Оплата</option>
              </select>
            </label>
            <label class="field">
              <span class="field-label">Показывать пользователям</span>
              <select v-model="stepDraft.is_active">
                <option :value="true">Да</option>
                <option :value="false">Скрыть</option>
              </select>
            </label>
          </div>
        </div>
      </div>

      <details class="panel soft-panel">
        <summary>Фото, видео, порядок и служебный код</summary>
        <div class="form-stack details-body">
          <div class="two-cols">
            <label class="field">
              <span class="field-label">Тип медиа</span>
              <select v-model="stepDraft.media_type">
                <option value="">Без вложения</option>
                <option value="photo">Фото</option>
                <option value="video">Видео</option>
                <option value="animation">GIF</option>
                <option value="document">Файл</option>
              </select>
            </label>
            <label class="field">
              <span class="field-label">Файл или ссылка</span>
              <input v-model="stepDraft.media_url" placeholder="Загрузите файл или вставьте ссылку" />
              <input type="file" class="file-input" @change="uploadAdminFile($event, stepDraft)" />
              <div v-if="stepDraft.media_url" class="media-preview">
                <img v-if="isImagePreview(stepDraft)" :src="mediaPreviewUrl(stepDraft.media_url)" alt="Предпросмотр" />
                <video v-else-if="isVideoPreview(stepDraft)" :src="mediaPreviewUrl(stepDraft.media_url)" controls playsinline></video>
                <a v-else :href="mediaPreviewUrl(stepDraft.media_url)" target="_blank" rel="noreferrer">{{ mediaTypeLabel(stepDraft.media_type) }}</a>
                <span class="muted small">{{ mediaTypeLabel(stepDraft.media_type) }}</span>
              </div>
            </label>
          </div>
          <label class="field">
            <span class="field-label">Подпись к медиа</span>
            <textarea v-model="stepDraft.media_caption" placeholder="Если пусто — бот использует заголовок и текст шага"></textarea>
          </label>
          <div class="two-cols">
            <label class="field">
              <span class="field-label">Номер в списке (порядок)</span>
              <input v-model.number="stepDraft.sort_order" type="number" />
            </label>
            <label class="field">
              <span class="field-label">Внутренний код (необязательно)</span>
              <input v-model="stepDraft.code" placeholder="Создастся автоматически из названия" />
            </label>
          </div>
        </div>
      </details>

      <div class="editor-actions">
        <button type="button" class="btn btn--primary" @click="saveStep">{{ stepDraft.id ? "Сохранить" : "Добавить шаг" }}</button>
        <button type="button" class="btn btn--ghost" @click="resetStepDraft">Сбросить форму</button>
      </div>
    </article>

    <article v-if="stepDraft.code" class="panel form-stack">
      <div class="section-head">
        <div>
          <h2>Дополнительные кнопки</h2>
          <p class="muted small">Несколько вариантов выбора: один ведёт в другой шаг, другой — на сайт.</p>
        </div>
      </div>
      <div class="btn-type-toggle">
        <button type="button" :class="{ active: branchTypeRef === 'internal' }" @click="branchTypeRef = 'internal'">На другой шаг</button>
        <button type="button" :class="{ active: branchTypeRef === 'external' }" @click="branchTypeRef = 'external'">Ссылка в интернет</button>
      </div>
      <div class="two-cols">
        <label class="field">
          <span class="field-label">Текст кнопки</span>
          <input v-model="branchDraft.button_text" placeholder="Например: Забрать бонус" />
        </label>
        <label v-if="branchTypeRef === 'internal'" class="field">
          <span class="field-label">Целевой шаг</span>
          <select v-model="branchDraft.target_step_code">
            <option value="">Выберите шаг</option>
            <option v-for="item in nextStepOptions" :key="item.id" :value="item.code">{{ item.title }}</option>
          </select>
        </label>
        <label v-else class="field">
          <span class="field-label">Ссылка</span>
          <input v-model="branchDraft.url" placeholder="https://..." />
        </label>
      </div>
      <div class="chips">
        <button type="button" class="btn btn--primary" @click="saveBranch">{{ branchDraft.id ? "Сохранить кнопку" : "Добавить кнопку" }}</button>
        <button v-if="branchDraft.id" type="button" class="btn btn--ghost" @click="resetBranchDraft">Отмена</button>
      </div>
      <div v-if="!branchesForCurrentStep.length" class="empty-state">Дополнительных кнопок пока нет.</div>
      <div v-else class="table-wrap">
        <div class="table">
          <div class="row row--head">
            <span>Кнопка</span><span>Куда ведёт</span><span>Порядок</span><span></span>
          </div>
          <div v-for="branch in branchesForCurrentStep" :key="branch.id" class="row">
            <span>{{ branch.button_text }}</span>
            <span>{{ branch.url ? branch.url : stepTitleByCode(branch.target_step_code) }}</span>
            <span>{{ branch.sort_order }}</span>
            <span class="chips">
              <button type="button" class="btn btn--ghost btn--sm" @click="editBranch(branch)">Изменить</button>
              <button type="button" class="btn btn--danger btn--ghost btn--sm" @click="deleteBranch(branch.id)">Удалить</button>
            </span>
          </div>
        </div>
      </div>
    </article>

    <article class="panel">
      <div class="section-head">
        <div>
          <h2>Все шаги</h2>
          <p class="muted small">Менять порядок и переходы удобнее в разделе «Порядок и кнопки».</p>
        </div>
        <button type="button" class="btn btn--secondary" @click="state.activeTab = isPostPayment ? 'post_chain' : 'chain'">Открыть порядок</button>
      </div>
      <div v-if="!orderedSteps.length" class="empty-state">Шагов ещё нет — создайте первый выше.</div>
      <div v-else class="step-cards">
        <div v-for="step in orderedSteps" :key="step.id" class="step-card">
          <div class="step-card-top">
            <span class="chip">{{ stepTypeLabel(step.step_type) }}</span>
            <span class="muted small">№ {{ step.sort_order }}</span>
          </div>
          <h3>{{ step.title }}</h3>
          <div v-if="step.media_url" class="card-media">
            <img v-if="isImagePreview(step)" :src="mediaPreviewUrl(step.media_url)" alt="" />
            <video v-else-if="isVideoPreview(step)" :src="mediaPreviewUrl(step.media_url)" controls playsinline></video>
            <a v-else :href="mediaPreviewUrl(step.media_url)" target="_blank" rel="noreferrer">{{ mediaTypeLabel(step.media_type) }}</a>
          </div>
          <p class="step-body">{{ step.body }}</p>
          <div class="step-meta">
            <span>{{ transitionLabel(step) }}: {{ stepTitleByCode(step.next_step_code) }}</span>
            <span v-if="step.trigger_keywords">Триггеры: {{ step.trigger_keywords }}</span>
            <span>{{ buttonsLabel(step) }}</span>
          </div>
          <div class="chips">
            <button type="button" class="btn btn--primary btn--sm" @click="editStep(step)">Редактировать</button>
            <button type="button" class="btn btn--secondary btn--sm" @click="createStepAfter(step)">Шаг после этого</button>
            <button type="button" class="btn btn--danger btn--ghost btn--sm" @click="deleteStep(step)">Удалить</button>
          </div>
        </div>
      </div>
    </article>
  </section>
</template>
