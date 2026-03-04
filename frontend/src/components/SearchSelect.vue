<!-- Copyright (c) 2026 左岚. All rights reserved. -->
<script setup>
import { ref, computed, watch, onMounted, onUnmounted } from 'vue'

const props = defineProps({
  modelValue: { type: String, default: '' },
  options: { type: Array, default: () => [] },
  placeholder: { type: String, default: '请选择...' },
  loading: { type: Boolean, default: false },
  allowCustom: { type: Boolean, default: true }
})

const emit = defineEmits(['update:modelValue', 'refresh'])

const isOpen = ref(false)
const inputRef = ref(null)
const dropdownRef = ref(null)
const searchQuery = ref('')
const activeIndex = ref(-1)

watch(() => props.modelValue, (val) => {
  if (!isOpen.value) searchQuery.value = val
}, { immediate: true })

const filteredOptions = computed(() => props.options)

function toggleDropdown() {
  if (props.loading) return
  isOpen.value = !isOpen.value
  if (isOpen.value) {
    inputRef.value.focus()
    activeIndex.value = -1
  }
}

function selectOption(option) {
  emit('update:modelValue', option)
  searchQuery.value = option
  isOpen.value = false
}

function onInput() {
  isOpen.value = true
  if (props.allowCustom) emit('update:modelValue', searchQuery.value)
}

function handleRefresh(e) {
  e.stopPropagation()
  emit('refresh')
}

function onKeydown(e) {
  if (!isOpen.value) {
    if (e.key === 'ArrowDown' || e.key === 'Enter') {
      isOpen.value = true
      e.preventDefault()
    }
    return
  }

  switch (e.key) {
    case 'ArrowDown':
      e.preventDefault()
      activeIndex.value = activeIndex.value < filteredOptions.value.length - 1 ? activeIndex.value + 1 : 0
      break
    case 'ArrowUp':
      e.preventDefault()
      activeIndex.value = activeIndex.value > 0 ? activeIndex.value - 1 : filteredOptions.value.length - 1
      break
    case 'Enter':
      e.preventDefault()
      if (activeIndex.value >= 0 && filteredOptions.value[activeIndex.value]) {
        selectOption(filteredOptions.value[activeIndex.value])
      } else if (props.allowCustom) {
        isOpen.value = false
      }
      break
    case 'Escape':
      isOpen.value = false
      inputRef.value.blur()
      break
  }
}

function handleClickOutside(e) {
  if (dropdownRef.value && !dropdownRef.value.contains(e.target)) {
    isOpen.value = false
    searchQuery.value = props.modelValue
  }
}

onMounted(() => document.addEventListener('click', handleClickOutside))
onUnmounted(() => document.removeEventListener('click', handleClickOutside))
</script>

<template>
  <div class="search-select" ref="dropdownRef">
    <div class="select-wrapper" :class="{ 'is-open': isOpen, 'is-loading': loading }">
      <div class="input-container" @click="toggleDropdown">
        <input
          ref="inputRef"
          type="text"
          class="select-input"
          v-model="searchQuery"
          :placeholder="placeholder"
          @input="onInput"
          @keydown="onKeydown"
          :disabled="loading"
        />
        
        <div class="actions">
          <button v-if="loading" class="icon-btn loading-icon">
            <span class="spinner"></span>
          </button>
          
          <button v-else class="icon-btn refresh-btn" @click="handleRefresh" title="刷新列表">
            ↻
          </button>
          
          <span class="chevron">↓</span>
        </div>
      </div>
      
      <transition name="fade-slide">
        <div v-if="isOpen" class="options-list">
          <div v-if="filteredOptions.length === 0" class="no-options">
            {{ loading ? '加载中...' : '无匹配选项' }}
          </div>
          
          <div
            v-else
            v-for="(option, index) in filteredOptions"
            :key="option"
            class="option-item"
            :class="{ 'is-active': index === activeIndex, 'is-selected': option === modelValue }"
            @click="selectOption(option)"
            @mouseenter="activeIndex = index"
          >
            <!-- Highlight Match -->
            <span v-if="searchQuery && isOpen" v-html="option.toString().replace(new RegExp(searchQuery, 'gi'), match => `<span class='highlight'>${match}</span>`)"></span>
            <span v-else>{{ option }}</span>
            
            <span v-if="option === modelValue" class="check-icon">✓</span>
          </div>
        </div>
      </transition>
    </div>
  </div>
</template>

<style scoped>
.search-select {
  position: relative;
  width: 100%;
}

.input-container {
  display: flex;
  align-items: center;
  background: var(--bg-background);
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  transition: all 0.2s ease;
  cursor: text;
}

/* Focus state for the container */
.select-wrapper.is-open .input-container,
.input-container:focus-within {
  border-color: var(--primary);
  box-shadow: 0 0 0 3px rgba(139, 115, 85, 0.1); /* Softer ring */
}

/* Inner input - Force no border/outline to prevent double-border issues */
.select-input {
  flex: 1;
  background: transparent;
  border: none !important;
  outline: none !important;
  box-shadow: none !important;
  padding: 0.75rem 1rem;
  color: var(--text-primary);
  font-size: 0.875rem; /* Match global text size */
  width: 100%;
  min-width: 0; /* Prevent flex overflow */
}

.actions {
  display: flex;
  align-items: center;
  padding-right: 0.75rem;
  gap: 0.25rem;
}

.icon-btn {
  background: transparent;
  border: none !important; /* Force removal of global btn borders */
  cursor: pointer;
  padding: 0.25rem;
  border-radius: var(--radius-sm);
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--text-secondary);
  transition: all 0.2s;
  width: 24px;
  height: 24px;
}

.icon-btn:hover {
  background-color: var(--bg-hover);
  color: var(--text-primary);
}

.refresh-btn:hover {
  transform: rotate(180deg);
}

.chevron {
  font-size: 0.75rem;
  color: var(--text-muted);
  transition: transform 0.2s ease;
  pointer-events: none;
  margin-left: 0.25rem;
}

.select-wrapper.is-open .chevron {
  transform: rotate(180deg);
}

/* Floating Dropdown - Standard Modern Look */
.options-list {
  position: absolute;
  top: calc(100% + 4px); /* Slight gap */
  left: 0;
  right: 0;
  background: var(--bg-card);
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  box-shadow: 0 10px 15px -3px rgba(0, 0, 0, 0.1), 0 4px 6px -4px rgba(0, 0, 0, 0.05); /* Shadow LG local definition */
  max-height: 260px;
  overflow-y: auto;
  z-index: 1000;
  padding: 0.25rem; /* Inner padding for clearer separation */
  animation: slideDown 0.15s ease-out;
}

@keyframes slideDown {
  from { opacity: 0; transform: translateY(-8px); }
  to { opacity: 1; transform: translateY(0); }
}

.option-item {
  padding: 0.6rem 0.8rem;
  cursor: pointer;
  color: var(--text-secondary);
  font-size: 0.9rem;
  display: flex;
  justify-content: space-between;
  align-items: center;
  border-radius: var(--radius-sm);
  transition: all 0.15s ease;
  margin-bottom: 2px;
}

.option-item:hover,
.option-item.is-active {
  background-color: #f3f4f6;
  color: var(--text-primary);
}

.option-item.is-selected {
  background-color: #f0ebe3; /* lighter primary */
  color: var(--primary);
  font-weight: 600;
}

.no-options {
  padding: 1rem;
  text-align: center;
  color: var(--text-muted);
  font-size: 0.875rem;
}

.check-icon {
  font-size: 0.875rem;
  color: currentColor;
}

:deep(.highlight) {
  color: var(--primary);
  font-weight: 600;
  background: transparent;
}

/* Scrollbar */
.options-list::-webkit-scrollbar { width: 4px; }
.options-list::-webkit-scrollbar-track { background: transparent; }
.options-list::-webkit-scrollbar-thumb { background: var(--border); border-radius: 2px; }
.options-list::-webkit-scrollbar-thumb:hover { background: var(--text-muted); }

.spinner {
  width: 14px; height: 14px;
  border: 2px solid var(--border);
  border-top-color: var(--text-primary);
  border-radius: 50%;
  animation: spin 1s linear infinite;
}
@keyframes spin { to { transform: rotate(360deg); } }
</style>
