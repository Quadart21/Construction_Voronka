<template>
  <div class="chunk-fallback" role="status">
    <span class="chunk-fallback__dot" aria-hidden="true" />
    Загрузка раздела…
  </div>
</template>

<style scoped>
.chunk-fallback {
  display: flex;
  align-items: center;
  gap: 10px;
  margin: 16px 0;
  padding: 14px 16px;
  border: 1px dashed var(--line, #e0e4ec);
  border-radius: var(--radius-sm, 8px);
  background: var(--surface-muted, #f0f2f6);
  color: var(--muted, #5a6170);
  font-weight: 600;
  font-size: 0.9375rem;
}
.chunk-fallback__dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: var(--primary, #1e5a8a);
  animation: pulse 0.9s ease-in-out infinite alternate;
}
@keyframes pulse {
  from {
    opacity: 0.35;
    transform: scale(0.85);
  }
  to {
    opacity: 1;
    transform: scale(1);
  }
}
</style>
