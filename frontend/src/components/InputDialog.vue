<script setup>
import { ref, watch, nextTick } from 'vue'

const props = defineProps({
  isOpen: Boolean,
  title: {
    type: String,
    default: '输入信息'
  },
  label: {
    type: String,
    default: ''
  },
  defaultValue: {
    type: [String, Number],
    default: ''
  },
  placeholder: {
    type: String,
    default: ''
  },
  inputType: {
    type: String,
    default: 'text' // text, number, textarea
  },
  confirmText: {
    type: String,
    default: '确定'
  },
  cancelText: {
    type: String,
    default: '取消'
  },
  loading: {
    type: Boolean,
    default: false
  }
})

const emit = defineEmits(['confirm', 'cancel', 'update:modelValue'])

const inputValue = ref(props.defaultValue)
const inputRef = ref(null)

watch(() => props.isOpen, (newVal) => {
  if (newVal) {
    inputValue.value = props.defaultValue
    nextTick(() => {
      inputRef.value?.focus()
    })
  }
})

function onConfirm() {
  if (!inputValue.value && props.inputType === 'number') return
  emit('confirm', inputValue.value)
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
          <label v-if="label" class="dialog-label">{{ label }}</label>
          
          <textarea
            v-if="inputType === 'textarea'"
            ref="inputRef"
            v-model="inputValue"
            class="input textarea"
            :placeholder="placeholder"
            rows="4"
            @keyup.enter.ctrl="onConfirm"
          ></textarea>
          
          <input 
            v-else
            ref="inputRef"
            v-model="inputValue"
            :type="inputType"
            class="input" 
            :placeholder="placeholder"
            @keyup.enter="onConfirm"
          />
        </div>
        
        <div class="dialog-footer">
          <button class="btn btn-ghost" @click="onCancel" :disabled="loading">
            {{ cancelText }}
          </button>
          <button 
            class="btn btn-primary" 
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
  z-index: 101; /* Higher than confirm dialog */
  display: flex;
  align-items: center;
  justify-content: center;
}

.dialog-content {
  background: var(--bg-card);
  border: 1px solid var(--border);
  border-radius: var(--radius-lg);
  width: 90%;
  max-width: 480px;
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
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
}

.dialog-label {
  font-size: 0.875rem;
  font-weight: 500;
  color: var(--text-secondary);
}

.input {
  width: 100%;
  padding: 0.75rem 1rem;
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  background: var(--bg-background);
  color: var(--text-primary);
  font-size: 1rem;
  transition: all 0.2s;
}

.input:focus {
  border-color: var(--primary);
  box-shadow: 0 0 0 2px rgba(99, 102, 241, 0.1);
  outline: none;
}

.textarea {
  resize: vertical;
  min-height: 100px;
  line-height: 1.5;
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
