<script setup>
import { inject } from "vue";
import { FUNNEL_ADMIN } from "../injectionKeys";
import { formatDateTime } from "../utils/formatting";

const { state, setLeadStatus } = inject(FUNNEL_ADMIN);

const STATUS_LABELS = {
  new: "Новая",
  processed: "В работе",
  rejected: "Отклонена"
};

function statusLabel(s) {
  if (s == null || s === "") return "—";
  const k = String(s).toLowerCase();
  return STATUS_LABELS[k] || s;
}
</script>

<template>
  <section class="stack">
    <article class="panel">
      <h2>Заявки с сайта</h2>
      <p class="muted small">Заявки с лендинга и уведомления в Telegram приходят при новой записи. Меняйте статус, чтобы отмечать обработку.</p>

      <p v-if="!state.leads.length" class="muted">Пока нет заявок.</p>

      <div v-else class="table-wrap">
        <table class="data-table">
          <thead>
            <tr>
              <th>Дата</th>
              <th>Имя</th>
              <th>Контакты</th>
              <th>Компания</th>
              <th>Сообщение</th>
              <th>Статус</th>
              <th>Действия</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="lead in state.leads" :key="lead.id">
              <td>{{ formatDateTime(lead.created_at) }}</td>
              <td>{{ lead.full_name }}</td>
              <td>
                <div class="cell-stack">
                  <a :href="`mailto:${lead.email}`">{{ lead.email }}</a>
                  <span class="muted small">{{ lead.phone }}</span>
                </div>
              </td>
              <td>{{ lead.company || "—" }}</td>
              <td class="cell-msg">{{ lead.message || "—" }}</td>
              <td>
                <span class="pill" :class="`pill--${lead.status}`">{{ statusLabel(lead.status) }}</span>
              </td>
              <td>
                <div class="row-actions">
                  <button
                    v-if="lead.status !== 'processed'"
                    type="button"
                    class="btn btn--ghost btn--small"
                    @click="setLeadStatus(lead.id, 'processed')"
                  >
                    В работу
                  </button>
                  <button
                    v-if="lead.status !== 'rejected'"
                    type="button"
                    class="btn btn--ghost btn--small"
                    @click="setLeadStatus(lead.id, 'rejected')"
                  >
                    Отклонить
                  </button>
                  <button
                    v-if="lead.status !== 'new'"
                    type="button"
                    class="btn btn--ghost btn--small"
                    @click="setLeadStatus(lead.id, 'new')"
                  >
                    Снова «новая»
                  </button>
                </div>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </article>
  </section>
</template>

<style scoped>
.table-wrap {
  overflow-x: auto;
  margin-top: 16px;
}
.data-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 0.875rem;
}
.data-table th,
.data-table td {
  text-align: left;
  padding: 10px 12px;
  border-bottom: 1px solid var(--line);
  vertical-align: top;
}
.data-table th {
  font-weight: 700;
  color: var(--muted);
  font-size: 0.75rem;
  text-transform: uppercase;
  letter-spacing: 0.03em;
}
.cell-stack {
  display: flex;
  flex-direction: column;
  gap: 4px;
}
.cell-stack a {
  color: var(--accent, #1e5a8a);
  word-break: break-all;
}
.cell-msg {
  max-width: 220px;
  white-space: pre-wrap;
  word-break: break-word;
}
.row-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}
.btn--small {
  padding: 6px 10px;
  font-size: 0.8125rem;
}
.pill {
  display: inline-block;
  padding: 4px 10px;
  border-radius: 999px;
  font-size: 0.75rem;
  font-weight: 700;
  background: var(--surface-muted);
}
.pill--new {
  background: rgba(198, 40, 40, 0.12);
  color: #b71c1c;
}
.pill--processed {
  background: rgba(30, 90, 138, 0.12);
  color: #1e5a8a;
}
.pill--rejected {
  background: rgba(80, 80, 80, 0.12);
  color: #424242;
}
</style>
