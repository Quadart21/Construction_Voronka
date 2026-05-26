<script setup>
import { inject } from "vue";
import { FUNNEL_ADMIN } from "../injectionKeys";
import { formatDateTime, eventTypeLabel, formatEventPayload } from "../utils/formatting";

const { eventSearch, filteredEvents, stepTitleByCode } = inject(FUNNEL_ADMIN);
</script>

<template>
  <section class="panel form-stack">
    <h2>История действий</h2>
    <p class="muted small">Показаны последние 200 событий. Можно искать по имени, типу или шагу.</p>
    <label class="field">
      <span class="field-label">Поиск</span>
      <input v-model="eventSearch" placeholder="Имя, тип события, шаг…" />
    </label>
    <div v-if="!filteredEvents.length" class="empty-state">Записей нет или ничего не подошло под поиск.</div>
    <div v-else class="table-wrap">
      <div class="table table--events">
        <div class="row row--head row--events-head">
          <span>Когда</span><span>Кто</span><span>Событие</span><span>Шаг</span><span>Детали</span>
        </div>
        <div v-for="event in filteredEvents" :key="event.id" class="row row--events">
          <span>{{ formatDateTime(event.created_at) }}</span>
          <span>{{ event.full_name }}</span>
          <span>{{ eventTypeLabel(event.event_type) }}</span>
          <span>{{ stepTitleByCode(event.step) }}</span>
          <span class="event-detail">{{ formatEventPayload(event.payload) }}</span>
        </div>
      </div>
    </div>
  </section>
</template>
