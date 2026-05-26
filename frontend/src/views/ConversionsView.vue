<script setup>
import { inject } from "vue";
import { FUNNEL_ADMIN } from "../injectionKeys";

const { state, conversionTop } = inject(FUNNEL_ADMIN);
</script>

<template>
  <section class="stack">
    <section class="grid grid--stats">
      <article class="stat-card">
        <span>Вошли в воронку</span>
        <strong>{{ state.conversions?.total_entered_funnel ?? 0 }}</strong>
      </article>
      <article class="stat-card">
        <span>Дошли до конца</span>
        <strong>{{ state.conversions?.total_completed ?? 0 }}</strong>
      </article>
      <article class="stat-card">
        <span>Сейчас «зависли»</span>
        <strong>{{ state.conversions?.total_stuck ?? 0 }}</strong>
      </article>
      <article class="stat-card">
        <span>Завершили полностью</span>
        <strong>{{ state.conversions?.completion_rate ?? 0 }}%</strong>
      </article>
    </section>
    <article class="panel">
      <h2>Где чаще всего теряются люди</h2>
      <p class="muted small">Процент — доля тех, кто остановился на шаге и не пошёл дальше.</p>
      <div v-if="!conversionTop.length" class="empty-state">Пока мало данных — как только пойдут люди, здесь появятся подсказки.</div>
      <div v-else class="timeline">
        <div v-for="item in conversionTop" :key="item.step_code" class="timeline-item">
          <span class="chip">{{ item.drop_off_rate }}%</span>
          <div>
            <strong>{{ item.step_title }}</strong>
            <p class="muted small">На шаге: {{ item.entered }} · Пошли дальше: {{ item.moved_forward }} · Сейчас здесь: {{ item.stuck_now }}</p>
          </div>
        </div>
      </div>
    </article>
  </section>
</template>
