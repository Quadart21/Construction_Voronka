<script setup>
import { inject } from "vue";
import { FUNNEL_ADMIN } from "../injectionKeys";
import { formatDateTime, eventTypeLabel } from "../utils/formatting";

const { state, recentEvents } = inject(FUNNEL_ADMIN);
</script>

<template>
  <section class="stack">
    <section class="grid grid--stats">
      <article class="stat-card">
        <span>Всего в воронке</span>
        <strong>{{ state.dashboard?.total_users ?? 0 }}</strong>
      </article>
      <article class="stat-card">
        <span>Новых сегодня</span>
        <strong>{{ state.dashboard?.users_today ?? 0 }}</strong>
      </article>
      <article class="stat-card">
        <span>Оплатили</span>
        <strong>{{ state.dashboard?.conversions ?? 0 }}</strong>
      </article>
      <article class="stat-card">
        <span>Доля оплат</span>
        <strong>{{ state.dashboard?.conversion_rate ?? 0 }}%</strong>
      </article>
    </section>
    <article v-if="recentEvents.length" class="panel">
      <h2>Последние события</h2>
      <p class="muted small">Короткая выжимка; полная история — в разделе «История».</p>
      <ul class="kv-list">
        <li v-for="ev in recentEvents.slice(0, 6)" :key="ev.id" class="kv-list__row">
          <span class="kv-list__time">{{ formatDateTime(ev.created_at) }}</span>
          <span class="kv-list__main">{{ ev.full_name }} — {{ eventTypeLabel(ev.event_type) }}</span>
        </li>
      </ul>
    </article>
  </section>
</template>
