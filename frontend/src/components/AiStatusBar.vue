<!-- Copyright (c) 2026 左岚. All rights reserved. -->
<!-- AiStatusBar.vue - 全局 AI 任务进度状态条 -->
<template>
  <transition name="slide-down">
    <div v-if="isVisible" class="ai-status-bar" :class="statusClass">
      <div class="status-content">
        <span class="status-icon" v-html="statusIcon"></span>
        <span class="status-text">{{ aiTask.statusText }}</span>
        <span v-if="aiTask.isRunning && formattedTime" class="elapsed-time">{{ formattedTime }}</span>
      </div>
      <div class="status-actions">
        <button v-if="aiTask.result" class="btn-view" @click="goToResult">查看</button>
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
import { computed, ref, onMounted, onUnmounted } from 'vue'
import { useRouter } from 'vue-router'
import { useAiTaskStore } from '@/stores/aiTask'

const router = useRouter()
const aiTask = useAiTaskStore()

const timer = ref(null)
const now = ref(Date.now())

onMounted(() => {
  timer.value = setInterval(() => { now.value = Date.now() }, 1000)
})
onUnmounted(() => {
  if (timer.value) clearInterval(timer.value)
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

const formattedTime = computed(() => {
  if (!aiTask.startTime) return ''
  const seconds = Math.floor((now.value - aiTask.startTime) / 1000)
  const mins = Math.floor(seconds / 60)
  const secs = seconds % 60
  return mins > 0 ? `${mins}分${secs}秒` : `${secs}秒`
})

function goToResult() {
  if (aiTask.result?.path) {
    router.push('/workspace/write')
  }
  dismiss()
}

function dismiss() {
  aiTask.clearTask()
}
</script>

<style scoped>
.ai-status-bar {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  z-index: 9999;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 10px 20px;
  font-size: 14px;
  font-weight: 500;
  box-shadow: 0 2px 8px rgba(0,0,0,0.1);
}

.ai-status-bar.running {
  background: white;
  border-bottom: 2px solid var(--primary, #8b7355);
  color: var(--text-primary, #2c2825);
}

.ai-status-bar.success {
  background: white;
  border-bottom: 2px solid var(--cta, #10b981);
  color: var(--text-primary, #2c2825);
}

.ai-status-bar.error {
  background: white;
  border-bottom: 2px solid var(--danger, #ef4444);
  color: var(--text-primary, #2c2825);
}

.status-content {
  display: flex;
  align-items: center;
  gap: 10px;
}

.status-icon {
  display: flex;
  align-items: center;
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
}

.elapsed-time {
  opacity: 0.6;
  font-size: 12px;
}

.status-actions {
  display: flex;
  align-items: center;
  gap: 8px;
}

.btn-view, .btn-close {
  background: rgba(0,0,0,0.05);
  border: none;
  color: #64748b;
  padding: 4px 12px;
  border-radius: 4px;
  cursor: pointer;
  font-size: 13px;
  transition: all 0.2s;
  display: flex;
  align-items: center;
}

.btn-view:hover, .btn-close:hover {
  background: rgba(0,0,0,0.1);
  color: #0f172a;
}

.btn-close {
  padding: 4px 6px;
}

/* 动画 */
.slide-down-enter-active, .slide-down-leave-active {
  transition: all 0.3s ease;
}
.slide-down-enter-from, .slide-down-leave-to {
  transform: translateY(-100%);
  opacity: 0;
}
</style>
