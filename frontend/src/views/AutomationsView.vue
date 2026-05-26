<script setup>
import { inject } from "vue";
import { FUNNEL_ADMIN } from "../injectionKeys";

const {
  automationDraft,
  triggerStepOptions,
  sortedAutomations,
  resetAutomationDraft,
  saveAutomation,
  editAutomation,
  stepTitleByCode
} = inject(FUNNEL_ADMIN);
</script>

<template>
  <section class="stack">
    <article class="panel form-stack">
      <div class="section-head">
        <div>
          <h2>{{ automationDraft.id ? "Редактировать напоминание" : "Новое напоминание" }}</h2>
          <p class="muted small">Если человек долго молчит, бот мягко напишет сам.</p>
        </div>
        <button v-if="automationDraft.id" type="button" class="btn btn--ghost" @click="resetAutomationDraft">Создать ещё одно</button>
      </div>
      <label class="field">
        <span class="field-label">Заголовок (для себя)</span>
        <input v-model="automationDraft.title" placeholder="Например: Напомнить про подарок" />
      </label>
      <label class="field">
        <span class="field-label">Текст сообщения</span>
        <textarea v-model="automationDraft.body" placeholder="Коротко и по делу"></textarea>
      </label>
      <div class="two-cols">
        <label class="field">
          <span class="field-label">Через сколько часов отправить</span>
          <input v-model.number="automationDraft.inactivity_hours" type="number" min="1" />
        </label>
        <label class="field">
          <span class="field-label">Считать бездействие после шага</span>
          <select v-model="automationDraft.trigger_step">
            <option value="">Любой шаг</option>
            <option v-for="item in triggerStepOptions" :key="item.id" :value="item.code">{{ item.title }}</option>
          </select>
        </label>
      </div>
      <div class="two-cols">
        <label class="field">
          <span class="field-label">Подпись к бонусу (если есть)</span>
          <input v-model="automationDraft.bonus_label" placeholder="Например: Видео-урок" />
        </label>
        <label class="field">
          <span class="field-label">Перевести на шаг после отправки</span>
          <select v-model="automationDraft.target_step_code">
            <option value="">Не менять шаг</option>
            <option v-for="item in triggerStepOptions" :key="item.id" :value="item.code">{{ item.title }}</option>
          </select>
        </label>
      </div>
      <details class="panel soft-panel">
        <summary>Служебный код сообщения</summary>
        <label class="field">
          <span class="field-label">Внутренний код</span>
          <input v-model="automationDraft.code" placeholder="Можно не заполнять" />
        </label>
      </details>
      <div class="chips">
        <button type="button" class="btn btn--primary" @click="saveAutomation">{{ automationDraft.id ? "Сохранить" : "Добавить" }}</button>
        <button v-if="automationDraft.id" type="button" class="btn btn--ghost" @click="resetAutomationDraft">Отмена</button>
      </div>
    </article>

    <article class="panel">
      <h2>Уже настроены</h2>
      <p class="muted small">Нажмите «Изменить», чтобы открыть правило в форме выше.</p>
      <div v-if="!sortedAutomations.length" class="empty-state">Автонапоминаний пока нет.</div>
      <ul v-else class="automation-list">
        <li v-for="rule in sortedAutomations" :key="rule.id" class="automation-list__item">
          <div>
            <strong>{{ rule.title || rule.code }}</strong>
            <p class="muted small">
              Через {{ rule.inactivity_hours }} ч.
              <template v-if="rule.trigger_step"> · после «{{ stepTitleByCode(rule.trigger_step) }}»</template>
              <template v-if="rule.target_step_code"> · далее «{{ stepTitleByCode(rule.target_step_code) }}»</template>
            </p>
          </div>
          <button type="button" class="btn btn--secondary btn--sm" @click="editAutomation(rule)">Изменить</button>
        </li>
      </ul>
    </article>
  </section>
</template>
