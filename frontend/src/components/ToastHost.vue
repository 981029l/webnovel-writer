<!-- Copyright (c) 2026 左岚. All rights reserved. -->
<!-- ToastHost.vue - 全局 toast 容器 -->
<script setup>
import { CheckCircle2, AlertCircle, Info, X } from 'lucide-vue-next'
import { toasts, dismiss } from '../composables/useToast'

const icons = { success: CheckCircle2, error: AlertCircle, info: Info }
</script>

<template>
  <div class="toast-region" aria-live="polite">
    <TransitionGroup name="toast">
      <div v-for="t in toasts" :key="t.id" class="toast" :class="`toast-${t.type}`" role="status">
        <component :is="icons[t.type]" class="toast-icon" :size="18" :stroke-width="1.5" />
        <p class="toast-message">{{ t.message }}</p>
        <button class="toast-close" @click="dismiss(t.id)" aria-label="关闭提示">
          <X :size="14" :stroke-width="2" />
        </button>
      </div>
    </TransitionGroup>
  </div>
</template>

<style scoped>
.toast-region {
  position: fixed;
  top: 1.25rem;
  right: 1.25rem;
  display: flex;
  flex-direction: column;
  gap: 0.625rem;
  z-index: var(--z-toast, 700);
  pointer-events: none;
  max-width: min(380px, calc(100vw - 2.5rem));
}

.toast {
  pointer-events: auto;
  display: flex;
  align-items: flex-start;
  gap: 0.625rem;
  padding: 0.875rem 1rem;
  background: var(--card);
  border: 1px solid var(--border);
  border-radius: var(--radius-lg);
  box-shadow: var(--shadow-lg);
  color: var(--ink-primary);
}

.toast-icon {
  flex-shrink: 0;
  margin-top: 1px;
}

.toast-success .toast-icon { color: var(--success); }
.toast-error .toast-icon { color: var(--danger); }
.toast-info .toast-icon { color: var(--primary-text); }

.toast-message {
  flex: 1;
  margin: 0;
  font-size: 0.875rem;
  line-height: 1.5;
  overflow-wrap: anywhere;
}

.toast-close {
  flex-shrink: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  background: none;
  border: none;
  padding: 0.25rem;
  margin: -0.125rem -0.25rem 0 0;
  border-radius: var(--radius-sm);
  color: var(--ink-muted);
  cursor: pointer;
  transition: color 0.15s, background-color 0.15s;
}

.toast-close:hover {
  color: var(--ink-primary);
  background: var(--bg-hover);
}

.toast-enter-active,
.toast-leave-active {
  transition: opacity 0.2s cubic-bezier(0.4, 0, 0.2, 1), transform 0.2s cubic-bezier(0.4, 0, 0.2, 1);
}

.toast-enter-from {
  opacity: 0;
  transform: translateY(-8px);
}

.toast-leave-to {
  opacity: 0;
}

@media (prefers-reduced-motion: reduce) {
  .toast-enter-active,
  .toast-leave-active {
    transition: opacity 0.01ms;
  }
  .toast-enter-from {
    transform: none;
  }
}
</style>
