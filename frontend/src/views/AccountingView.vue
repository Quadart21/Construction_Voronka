<script setup>
import { inject } from "vue";
import { FUNNEL_ADMIN } from "../injectionKeys";
import { formatDateTime, paymentStatusLabel } from "../utils/formatting";

const { state, paymentList } = inject(FUNNEL_ADMIN);
</script>

<template>
  <section class="stack">
    <section class="grid grid--stats">
      <article class="stat-card">
        <span>Выручка</span>
        <strong>{{ state.accounting?.total_revenue ?? 0 }}</strong>
      </article>
      <article class="stat-card">
        <span>Успешных оплат</span>
        <strong>{{ state.accounting?.paid_orders ?? 0 }}</strong>
      </article>
      <article class="stat-card">
        <span>В ожидании</span>
        <strong>{{ state.accounting?.pending_orders ?? 0 }}</strong>
      </article>
      <article class="stat-card">
        <span>Средний чек</span>
        <strong>{{ state.accounting?.average_check ?? 0 }}</strong>
      </article>
    </section>
    <article class="panel">
      <h2>Последние платежи</h2>
      <div v-if="!paymentList.length" class="empty-state">Оплат пока не было.</div>
      <div v-else class="table-wrap">
        <div class="table">
          <div class="row row--head"><span>Когда</span><span>Кто</span><span>Сумма</span><span>Статус</span></div>
          <div v-for="payment in paymentList" :key="payment.id" class="row">
            <span>{{ formatDateTime(payment.created_at) }}</span>
            <span>{{ payment.full_name }}</span>
            <span>{{ payment.amount }} {{ payment.currency }}</span>
            <span>{{ paymentStatusLabel(payment.status) }}</span>
          </div>
        </div>
      </div>
    </article>
  </section>
</template>
