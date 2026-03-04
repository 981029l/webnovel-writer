<script setup>
defineProps({
  isOpen: Boolean,
  title: {
    type: String,
    default: '确认操作'
  },
  message: {
    type: String,
    default: ''
  },
  confirmText: {
    type: String,
    default: '确定'
  },
  cancelText: {
    type: String,
    default: '取消'
  },
  type: {
    type: String,
    default: 'primary', // primary, danger, warning
    validator: (value) => ['primary', 'danger', 'warning'].includes(value)
  },
  loading: {
    type: Boolean,
    default: false
  }
})

const emit = defineEmits(['confirm', 'cancel'])

function onConfirm() {
  emit('confirm')
}

function onCancel() {
  emit('cancel')
}
</script>

<template>
  <Transition name="fade">
    <div v-if="isOpen" class="dialog-overlay" @click.self="onCancel">
      <div class="dialog-content">
        <div class="dialog-header">
          <h3 class="dialog-title">{{ title }}</h3>
        </div>
        
        <div class="dialog-body">
          <p class="dialog-message">{{ message }}</p>
          <slot></slot>
        </div>
        
        <div class="dialog-footer">
          <button class="btn btn-ghost" @click="onCancel" :disabled="loading">
            {{ cancelText }}
          </button>
          <button 
            class="btn" 
            :class="type === 'danger' ? 'btn-danger' : 'btn-primary'" 
            @click="onConfirm"
            :disabled="loading"
          >
            <span v-if="loading" class="spinner-sm mr-2"></span>
            {{ confirmText }}
          </button>
        </div>
      </div>
    </div>
  </Transition>
</template>

<style scoped>
.dialog-overlay {
  position: fixed;
  top: 0;
  left: 0;
  width: 100vw;
  height: 100vh;
  background-color: rgba(0, 0, 0, 0.5);
  backdrop-filter: blur(4px);
  z-index: 100;
  display: flex;
  align-items: center;
  justify-content: center;
}

.dialog-content {
  background: var(--bg-card);
  border: 1px solid var(--border);
  border-radius: var(--radius-lg);
  width: 90%;
  max-width: 400px;
  box-shadow: var(--shadow-xl);
  animation: scaleIn 0.2s ease-out;
}

.dialog-header {
  padding: 1.25rem 1.5rem;
  border-bottom: 1px solid var(--border);
}

.dialog-title {
  margin: 0;
  font-size: 1.125rem;
  font-weight: 600;
  color: var(--text-primary);
}

.dialog-body {
  padding: 1.5rem;
  color: var(--text-secondary);
  line-height: 1.6;
}

.dialog-message {
  white-space: pre-line; /* Respect newlines in message */
  margin: 0;
}

.dialog-footer {
  padding: 1rem 1.5rem;
  background-color: var(--bg-secondary);
  border-bottom-left-radius: var(--radius-lg);
  border-bottom-right-radius: var(--radius-lg);
  display: flex;
  justify-content: flex-end;
  gap: 0.75rem;
}

@keyframes scaleIn {
  from { opacity: 0; transform: scale(0.95); }
  to { opacity: 1; transform: scale(1); }
}

.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.2s ease;
}

.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}
</style>
