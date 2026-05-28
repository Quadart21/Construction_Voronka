<script setup>
import { computed, inject } from "vue";
import { FUNNEL_ADMIN } from "../injectionKeys";

const {
  state,
  chainBranchSourceCode,
  branchTypeRef,
  branchDraft,
  orderedSteps,
  stepTypeLabel,
  mediaTypeLabel,
  mediaPreviewUrl,
  isImagePreview,
  isVideoPreview,
  transitionLabel,
  resetStepDraft,
  editStep,
  createStepAfter,
  deleteStep,
  deleteAllSteps,
  moveStep,
  updateStepTransition,
  startBranchCreate,
  cancelChainBranchEdit,
  editBranch,
  saveBranch,
  deleteBranch,
  stepTitleByCode,
  branchesForStep,
  targetOptionsFor
} = inject(FUNNEL_ADMIN);

const isPostPayment = computed(() => state.funnelPhase === "post_payment");
</script>

<template>
  <section class="stack">
    <article class="panel">
      <div class="section-head">
        <div>
          <h2>{{ isPostPayment ? "Цепочка после оплаты" : "Цепочка по порядку" }}</h2>
          <p class="muted small">Стрелка «Выше / Ниже» меняет очередность. «Сохранить переход» фиксирует основную кнопку.</p>
        </div>
        <div class="chips">
          <button type="button" class="btn btn--secondary" @click="resetStepDraft(); state.activeTab = isPostPayment ? 'post_steps' : 'steps'">Новый шаг</button>
          <button v-if="orderedSteps.length" type="button" class="btn btn--danger btn--ghost" @click="deleteAllSteps">Очистить всё</button>
        </div>
      </div>
    </article>

    <article v-if="!orderedSteps.length" class="panel">
      <h2>Пока пусто</h2>
      <p class="muted">Сначала добавьте шаг с текстом — затем вернитесь сюда.</p>
      <button type="button" class="btn btn--primary" @click="resetStepDraft(); state.activeTab = isPostPayment ? 'post_steps' : 'steps'">Создать первый шаг</button>
    </article>

    <div v-else class="chain-board">
      <article v-for="(step, index) in orderedSteps" :key="step.id" class="chain-card">
        <div class="chain-order">
          <span class="chain-number">{{ index + 1 }}</span>
          <button type="button" class="btn btn--ghost btn--sm" :disabled="index === 0" @click="moveStep(step, -1)">Выше</button>
          <button type="button" class="btn btn--ghost btn--sm" :disabled="index === orderedSteps.length - 1" @click="moveStep(step, 1)">Ниже</button>
        </div>

        <div class="chain-main">
          <div class="chain-head">
            <div>
              <div class="chips">
                <span class="chip">{{ stepTypeLabel(step.step_type) }}</span>
              </div>
              <h3>{{ step.title }}</h3>
            </div>
            <div class="chips">
              <button type="button" class="btn btn--ghost btn--sm" @click="editStep(step)">Текст</button>
              <button type="button" class="btn btn--ghost btn--sm" @click="createStepAfter(step)">Шаг ниже</button>
              <button type="button" class="btn btn--danger btn--ghost btn--sm" @click="deleteStep(step)">Удалить</button>
            </div>
          </div>

          <p class="muted small">{{ step.body }}</p>
          <div v-if="step.media_url" class="media-preview compact">
            <img v-if="isImagePreview(step)" :src="mediaPreviewUrl(step.media_url)" alt="" />
            <video v-else-if="isVideoPreview(step)" :src="mediaPreviewUrl(step.media_url)" controls playsinline></video>
            <a v-else :href="mediaPreviewUrl(step.media_url)" target="_blank" rel="noreferrer">{{ mediaTypeLabel(step.media_type) }}</a>
            <span class="muted small">{{ mediaTypeLabel(step.media_type) }}</span>
          </div>

          <div class="chain-fields">
            <label class="field">
              <span class="field-label">Текст основной кнопки</span>
              <input v-model="step.cta_text" placeholder="Дальше" />
            </label>
            <label class="field">
              <span class="field-label">{{ transitionLabel(step) }}</span>
              <select v-model="step.next_step_code">
                <option value="">Завершить цепочку</option>
                <option v-for="item in targetOptionsFor(step.code)" :key="item.id" :value="item.code">{{ item.title }}</option>
              </select>
            </label>
          </div>
          <label class="field">
            <span class="field-label">Слова-триггеры для этого шага</span>
            <input v-model="step.trigger_keywords" placeholder="Например: Magic, магия, старт" />
            <span class="muted small">Пользователь пишет это слово — бот открывает этот шаг. Несколько слов разделяйте запятыми.</span>
          </label>
          <button type="button" class="btn btn--primary btn--sm" @click="updateStepTransition(step)">Сохранить переход</button>

          <div class="chain-branches">
            <div class="route-top">
              <strong>Дополнительные кнопки</strong>
              <button type="button" class="btn btn--ghost btn--sm" @click="startBranchCreate(step)">Добавить</button>
            </div>

            <div v-if="!branchesForStep(step.code).length" class="empty-line">Пока только основная кнопка.</div>

            <div v-for="branch in branchesForStep(step.code)" :key="branch.id" class="branch-row">
              <span>{{ branch.button_text }}</span>
              <span class="muted">{{ branch.url ? "↗ " + branch.url : "→ " + stepTitleByCode(branch.target_step_code) }}</span>
              <span class="chips">
                <button type="button" class="btn btn--ghost btn--sm" @click="editBranch(branch, isPostPayment ? 'post_chain' : 'chain')">Изменить</button>
                <button type="button" class="btn btn--ghost btn--sm" @click="deleteBranch(branch.id)">Удалить</button>
              </span>
            </div>

            <div v-if="chainBranchSourceCode === step.code" class="branch-editor">
              <div class="btn-type-toggle">
                <button type="button" :class="{ active: branchTypeRef === 'internal' }" @click="branchTypeRef = 'internal'">На шаг</button>
                <button type="button" :class="{ active: branchTypeRef === 'external' }" @click="branchTypeRef = 'external'">Ссылка</button>
              </div>
              <div class="chain-fields">
                <label class="field">
                  <span class="field-label">Текст кнопки</span>
                  <input v-model="branchDraft.button_text" placeholder="Вариант ответа" />
                </label>
                <label v-if="branchTypeRef === 'internal'" class="field">
                  <span class="field-label">Шаг</span>
                  <select v-model="branchDraft.target_step_code">
                    <option value="">Выберите</option>
                    <option v-for="item in targetOptionsFor(step.code)" :key="item.id" :value="item.code">{{ item.title }}</option>
                  </select>
                </label>
                <label v-else class="field">
                  <span class="field-label">URL</span>
                  <input v-model="branchDraft.url" placeholder="https://..." />
                </label>
              </div>
              <div class="chips">
                <button type="button" class="btn btn--primary btn--sm" @click="saveBranch(step.code)">
                  {{ branchDraft.id ? "Сохранить" : "Добавить" }}
                </button>
                <button type="button" class="btn btn--ghost btn--sm" @click="cancelChainBranchEdit">Отмена</button>
              </div>
            </div>
          </div>
        </div>
      </article>
    </div>
  </section>
</template>
