<!-- Copyright (c) 2026 左岚. All rights reserved. -->
<!-- AiStatusBar.vue - 全局 AI 任务进度状态条 -->
<template>
  <transition name="popup-fade">
    <div v-if="isVisible" class="task-popup" :class="statusClass">
      <div class="status-content">
        <span class="status-icon" v-html="statusIcon"></span>
        <div class="status-copy">
          <div class="status-text">{{ aiTask.statusText }}</div>
          <div v-if="aiTask.isRunning && formattedTime" class="elapsed-time">已运行 {{ formattedTime }}</div>
          <div v-if="visibleSteps.length" class="status-steps">
            <div
              v-for="step in visibleSteps"
              :key="step.step"
              class="status-step"
              :class="step.status || 'pending'"
            >
              <span class="step-dot"></span>
              <span class="step-name">{{ step.name || step.step }}</span>
              <span class="step-state" :class="step.status || 'pending'">
                {{ getStepStatusLabel(step.status) }}
              </span>
            </div>
          </div>
        </div>
      </div>
      <div class="status-actions">
        <button v-if="aiTask.result?.path" class="btn-view" @click="goToResult">查看</button>
        <button class="btn-close" @click="dismiss">
          <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="2" stroke="currentColor" class="size-4">
            <path stroke-linecap="round" stroke-linejoin="round" d="M6 18 18 6M6 6l12 12" />
          </svg>
        </button>
      </div>
    </div>
  </transition>
</template>

<script setup>
import { computed, ref, onMounted, onUnmounted, watch } from 'vue'
import { useRouter } from 'vue-router'
import { useAiTaskStore } from '@/stores/aiTask'

const router = useRouter()
const aiTask = useAiTaskStore()

const timer = ref(null)
const now = ref(Date.now())
const dismissTimer = ref(null)

function clearDismissTimer() {
  if (dismissTimer.value) {
    clearTimeout(dismissTimer.value)
    dismissTimer.value = null
  }
}

onMounted(() => {
  timer.value = setInterval(() => { now.value = Date.now() }, 1000)
})
onUnmounted(() => {
  if (timer.value) clearInterval(timer.value)
  clearDismissTimer()
})

const isVisible = computed(() => aiTask.isRunning || aiTask.result)

const statusIcon = computed(() => {
  if (aiTask.isRunning) {
    return '<svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor" class="status-svg spin"><path stroke-linecap="round" stroke-linejoin="round" d="M16.023 9.348h4.992v-.001M2.985 19.644v-4.992m0 0h4.992m-4.993 0 3.181 3.183a8.25 8.25 0 0 0 13.803-3.7M4.031 9.865a8.25 8.25 0 0 1 13.803-3.7l3.181 3.182M2.985 19.644v-4.992" /></svg>'
  }
  if (aiTask.result?.success) {
    return '<svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="2" stroke="currentColor" class="status-svg"><path stroke-linecap="round" stroke-linejoin="round" d="m4.5 12.75 6 6 9-13.5" /></svg>'
  }
  return '<svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="2" stroke="currentColor" class="status-svg"><path stroke-linecap="round" stroke-linejoin="round" d="M12 9v3.75m-9.303 3.376c-.866 1.5.217 3.374 1.948 3.374h14.71c1.73 0 2.813-1.874 1.948-3.374L13.949 3.378c-.866-1.5-3.032-1.5-3.898 0L2.697 16.126ZM12 15.75h.007v.008H12v-.008Z" /></svg>'
})

const statusClass = computed(() => {
  if (aiTask.isRunning) return 'running'
  if (aiTask.result?.success) return 'success'
  return 'error'
})

const visibleSteps = computed(() => {
  const steps = Array.isArray(aiTask.initSteps) ? aiTask.initSteps : []
  return steps.slice(-5)
})

function getStepStatusLabel(status) {
  if (status === 'active' || status === 'processing') return '进行中'
  if (status === 'completed' || status === 'success') return '已完成'
  if (status === 'failed' || status === 'error') return '失败'
  return '等待中'
}

const formattedTime = computed(() => {
  if (!aiTask.startTime) return ''
  const seconds = Math.floor((now.value - aiTask.startTime) / 1000)
  const mins = Math.floor(seconds / 60)
  const secs = seconds % 60
  return mins > 0 ? `${mins}分${secs}秒` : `${secs}秒`
})

function goToResult() {
  if (aiTask.result?.path) {
    router.push(aiTask.result.path)
  }
  dismiss()
}

function dismiss() {
  aiTask.clearTask()
}

watch(() => aiTask.result, (result) => {
  clearDismissTimer()
  if (!result) return
  dismissTimer.value = setTimeout(() => {
    if (aiTask.result === result) {
      dismiss()
    }
  }, 4000)
}, { deep: true })
</script>

<style scoped>
.task-popup {
  position: fixed;
  right: 20px;
  bottom: 20px;
  z-index: var(--z-toast);
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 14px;
  width: min(420px, calc(100vw - 24px));
  padding: 14px 16px;
  border-radius: var(--radius-lg);
  font-size: 14px;
  font-weight: 500;
  box-shadow: var(--shadow-lg);
  border: 1px solid var(--border);
  background: var(--card);
  color: var(--ink-primary);
}

.task-popup.success {
  background: var(--success-tint);
  color: var(--success);
  border-color: transparent;
}

.task-popup.error {
  background: var(--danger-tint);
  color: var(--danger);
  border-color: transparent;
}

.status-content {
  display: flex;
  align-items: flex-start;
  gap: 10px;
  min-width: 0;
}

.status-icon {
  display: flex;
  align-items: center;
  flex-shrink: 0;
}

.status-icon :deep(.status-svg) {
  width: 18px;
  height: 18px;
}

.status-icon :deep(.status-svg.spin) {
  animation: spin 1.2s linear infinite;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

.status-text {
  font-size: 13px;
  line-height: 1.45;
  word-break: break-word;
}

.elapsed-time {
  opacity: 0.72;
  font-size: 12px;
  margin-top: 2px;
  font-family: var(--font-mono);
  font-feature-settings: "tnum";
}

.status-copy {
  min-width: 0;
  flex: 1;
}

.status-steps {
  display: flex;
  flex-direction: column;
  gap: 0.35rem;
  margin-top: 0.6rem;
}

.status-step {
  display: flex;
  align-items: center;
  gap: 0.45rem;
  font-size: 12px;
  line-height: 1.35;
  color: var(--ink-secondary);
}

.status-step .step-dot {
  width: 7px;
  height: 7px;
  border-radius: 50%;
  background: var(--border-strong);
  flex-shrink: 0;
}

.status-step.active .step-dot {
  background: var(--warning);
  box-shadow: 0 0 0 3px var(--warning-tint);
}

.status-step.active .step-name {
  color: var(--ink-primary);
  font-weight: 600;
}

.status-step.completed .step-dot {
  background: var(--success);
}

.status-step.failed .step-dot,
.status-step.error .step-dot {
  background: var(--danger);
}

.step-name {
  min-width: 0;
  flex: 1;
  word-break: break-word;
}

.step-state {
  flex-shrink: 0;
  padding: 1px 7px;
  border-radius: var(--radius-sm);
  font-size: 11px;
  font-weight: 600;
  background: var(--surface);
  color: var(--ink-muted);
  border: 1px solid var(--border);
}

.step-state.active,
.step-state.processing {
  background: var(--warning-tint);
  color: var(--warning-strong);
  border-color: transparent;
}

.step-state.completed,
.step-state.success {
  background: var(--success-tint);
  color: var(--success);
  border-color: transparent;
}

.step-state.failed,
.step-state.error {
  background: var(--danger-tint);
  color: var(--danger);
  border-color: transparent;
}

.status-actions {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-shrink: 0;
}

.btn-view, .btn-close {
  background: var(--surface);
  border: 1px solid var(--border);
  color: var(--ink-secondary);
  padding: 4px 12px;
  border-radius: var(--radius-sm);
  cursor: pointer;
  font-size: 13px;
  transition: background-color var(--dur-fast) var(--ease-standard), color var(--dur-fast) var(--ease-standard);
  display: flex;
  align-items: center;
}

.btn-view:hover, .btn-close:hover {
  background: var(--hover);
  color: var(--ink-primary);
}

.btn-close {
  padding: 4px 6px;
}

/* 动画 */
.popup-fade-enter-active, .popup-fade-leave-active {
  transition: all 0.22s ease;
}
.popup-fade-enter-from, .popup-fade-leave-to {
  transform: translateY(10px) scale(0.98);
  opacity: 0;
}

@media (max-width: 640px) {
  .task-popup {
    right: 12px;
    bottom: 12px;
    width: min(360px, calc(100vw - 24px));
    padding: 12px 14px;
  }
}
</style>
