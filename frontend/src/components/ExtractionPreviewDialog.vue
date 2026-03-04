<!-- ExtractionPreviewDialog.vue - 世界观提取预览确认弹窗 -->
<script setup>
import { ref, computed, watch } from 'vue'

const props = defineProps({
  isOpen: Boolean,
  chapter: {
    type: Number,
    default: 0
  },
  extraction: {
    type: Object,
    default: () => null
  },
  loading: {
    type: Boolean,
    default: false
  }
})

const emit = defineEmits(['confirm', 'cancel'])

// 分类配置
const categories = [
  { key: 'new_characters', label: '新角色', icon: '👤', formatter: (item) => `${item.name} — ${item.identity || '未知'} (${item.realm || '未知'}, ${item.location || '未知'})` },
  { key: 'new_treasures', label: '新宝物', icon: '💎', formatter: (item) => `${item.name} — ${item.tier || '未知'} (${item.owner || '未知'})` },
  { key: 'new_techniques', label: '新功法', icon: '📜', formatter: (item) => `${item.name} — ${item.tier || '未知'} (${item.practitioner || '未知'})` },
  { key: 'new_organizations', label: '新势力', icon: '🏛', formatter: (item) => `${item.name} — ${item.type || '未知'} (${item.relation || '未知'})` },
  { key: 'new_locations', label: '新地点', icon: '📍', formatter: (item) => `${item.name} — ${item.type || '未知'}` },
  { key: 'status_changes', label: '状态变更', icon: '🔄', formatter: (item) => `${item.name} → ${item.change || item.status || '变更'}` },
  { key: 'entity_events', label: '实体事件', icon: '⚡', formatter: (item) => `${item.name}: ${item.event || ''}` },
  { key: 'exits', label: '角色下线', icon: '💀', formatter: (item) => `${item.name} — ${item.reason || '下线'}` },
]

// 每个 item 的选中状态：{ [categoryKey]: boolean[] }
const selected = ref({})
// status_file_updates 整体开关
const statusFileEnabled = ref(true)
// 折叠状态
const collapsed = ref({})

// 当 extraction 数据变化时，初始化选中状态（全选）
watch(() => props.extraction, (ext) => {
  if (!ext) return
  const sel = {}
  for (const cat of categories) {
    const items = ext[cat.key] || []
    sel[cat.key] = items.map(() => true)
  }
  selected.value = sel
  statusFileEnabled.value = true
  collapsed.value = {}
}, { immediate: true })

// 各分类有效数据
const categoryData = computed(() => {
  if (!props.extraction) return []
  return categories
    .map(cat => ({
      ...cat,
      items: props.extraction[cat.key] || [],
    }))
    .filter(cat => cat.items.length > 0)
})

// 是否有 status_file_updates
const hasStatusFileUpdates = computed(() => {
  if (!props.extraction) return false
  const sfu = props.extraction.status_file_updates
  return sfu && typeof sfu === 'object' && Object.keys(sfu).length > 0
})

const statusFileSummary = computed(() => {
  if (!hasStatusFileUpdates.value) return ''
  const sfu = props.extraction.status_file_updates
  return sfu.chapter_event || '状态文件更新'
})

// 统计
const totalItems = computed(() => {
  let count = 0
  for (const cat of categoryData.value) {
    count += cat.items.length
  }
  if (hasStatusFileUpdates.value) count += 1
  return count
})

const selectedCount = computed(() => {
  let count = 0
  for (const cat of categoryData.value) {
    const sel = selected.value[cat.key] || []
    count += sel.filter(Boolean).length
  }
  if (hasStatusFileUpdates.value && statusFileEnabled.value) count += 1
  return count
})

const isEmpty = computed(() => {
  return categoryData.value.length === 0 && !hasStatusFileUpdates.value
})

function toggleCategory(key) {
  const sel = selected.value[key] || []
  const allSelected = sel.every(Boolean)
  selected.value[key] = sel.map(() => !allSelected)
}

function toggleCollapse(key) {
  collapsed.value[key] = !collapsed.value[key]
}

function onConfirm() {
  if (!props.extraction) return
  // 构建过滤后的 extraction
  const filtered = {}
  for (const cat of categories) {
    const items = props.extraction[cat.key] || []
    const sel = selected.value[cat.key] || []
    filtered[cat.key] = items.filter((_, i) => sel[i])
  }
  // status_file_updates 整体开关
  if (hasStatusFileUpdates.value && statusFileEnabled.value) {
    filtered.status_file_updates = props.extraction.status_file_updates
  } else {
    filtered.status_file_updates = {}
  }
  emit('confirm', filtered)
}

function onCancel() {
  emit('cancel')
}
</script>

<template>
  <Transition name="fade">
    <div v-if="isOpen" class="epd-overlay" @click.self="onCancel">
      <div class="epd-content">
        <div class="epd-header">
          <h3 class="epd-title">设定同步预览 — 第{{ chapter }}章</h3>
          <button class="epd-close" @click="onCancel">&times;</button>
        </div>

        <div class="epd-body">
          <!-- 空结果 -->
          <div v-if="isEmpty" class="epd-empty">
            本章未提取到新设定
          </div>

          <template v-else>
            <!-- 统计行 -->
            <div class="epd-stats">
              提取到 {{ totalItems }} 个项目
            </div>

            <!-- 各分类 -->
            <div v-for="cat in categoryData" :key="cat.key" class="epd-category">
              <div class="epd-cat-header" @click="toggleCollapse(cat.key)">
                <span class="epd-cat-arrow" :class="{ collapsed: collapsed[cat.key] }">&#9660;</span>
                <label class="epd-cat-checkbox" @click.stop>
                  <input
                    type="checkbox"
                    :checked="(selected[cat.key] || []).every(Boolean)"
                    :indeterminate.prop="!(selected[cat.key] || []).every(Boolean) && (selected[cat.key] || []).some(Boolean)"
                    @change="toggleCategory(cat.key)"
                  />
                </label>
                <span class="epd-cat-icon">{{ cat.icon }}</span>
                <span class="epd-cat-label">{{ cat.label }}</span>
                <span class="epd-cat-count">({{ cat.items.length }})</span>
              </div>
              <div v-if="!collapsed[cat.key]" class="epd-cat-items">
                <label
                  v-for="(item, idx) in cat.items"
                  :key="idx"
                  class="epd-item"
                >
                  <input type="checkbox" v-model="selected[cat.key][idx]" />
                  <span class="epd-item-text">{{ cat.formatter(item) }}</span>
                </label>
              </div>
            </div>

            <!-- status_file_updates 整体开关 -->
            <div v-if="hasStatusFileUpdates" class="epd-category">
              <div class="epd-cat-header">
                <span class="epd-cat-arrow" style="visibility:hidden">&#9660;</span>
                <label class="epd-cat-checkbox" @click.stop>
                  <input type="checkbox" v-model="statusFileEnabled" />
                </label>
                <span class="epd-cat-icon">📊</span>
                <span class="epd-cat-label">实时状态更新</span>
                <span class="epd-cat-count">(1)</span>
              </div>
              <div class="epd-cat-items">
                <div class="epd-item epd-status-summary">
                  {{ statusFileSummary }}
                </div>
              </div>
            </div>
          </template>
        </div>

        <div class="epd-footer">
          <button class="btn btn-ghost" @click="onCancel" :disabled="loading">取消</button>
          <span class="epd-selected-info" v-if="!isEmpty">已选 {{ selectedCount }}/{{ totalItems }} 项</span>
          <button
            class="btn btn-primary"
            @click="onConfirm"
            :disabled="loading || isEmpty || selectedCount === 0"
          >
            <span v-if="loading" class="spinner-sm mr-2"></span>
            {{ loading ? '写入中...' : '确认写入' }}
          </button>
        </div>
      </div>
    </div>
  </Transition>
</template>

<style scoped>
.epd-overlay {
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

.epd-content {
  background: var(--bg-card);
  border: 1px solid var(--border);
  border-radius: var(--radius-lg);
  width: 90%;
  max-width: 780px;
  max-height: 85vh;
  display: flex;
  flex-direction: column;
  box-shadow: var(--shadow-xl);
  animation: epd-scale-in 0.2s ease-out;
}

@keyframes epd-scale-in {
  from { opacity: 0; transform: scale(0.95); }
  to { opacity: 1; transform: scale(1); }
}

.epd-header {
  padding: 1.25rem 1.5rem;
  border-bottom: 1px solid var(--border);
  display: flex;
  align-items: center;
  justify-content: space-between;
  flex-shrink: 0;
}

.epd-title {
  margin: 0;
  font-size: 1.125rem;
  font-weight: 600;
  color: var(--text-primary);
}

.epd-close {
  background: none;
  border: none;
  font-size: 1.5rem;
  cursor: pointer;
  color: var(--text-secondary);
  padding: 0 0.25rem;
  line-height: 1;
}
.epd-close:hover { color: var(--text-primary); }

.epd-body {
  padding: 1rem 1.5rem;
  overflow-y: auto;
  max-height: 70vh;
  flex: 1;
}

.epd-empty {
  text-align: center;
  color: var(--text-secondary);
  padding: 3rem 0;
  font-size: 1rem;
}

.epd-stats {
  color: var(--text-secondary);
  font-size: 0.875rem;
  margin-bottom: 0.75rem;
  padding-bottom: 0.5rem;
  border-bottom: 1px solid var(--border);
}

.epd-category {
  margin-bottom: 0.5rem;
}

.epd-cat-header {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  padding: 0.5rem 0;
  cursor: pointer;
  user-select: none;
  font-weight: 500;
  color: var(--text-primary);
}
.epd-cat-header:hover {
  background: var(--bg-secondary);
  border-radius: var(--radius-sm, 4px);
}

.epd-cat-arrow {
  font-size: 0.625rem;
  transition: transform 0.15s;
  width: 1rem;
  text-align: center;
  flex-shrink: 0;
}
.epd-cat-arrow.collapsed {
  transform: rotate(-90deg);
}

.epd-cat-checkbox {
  flex-shrink: 0;
  cursor: pointer;
}
.epd-cat-checkbox input { cursor: pointer; }

.epd-cat-icon {
  flex-shrink: 0;
}

.epd-cat-label {
  flex-shrink: 0;
}

.epd-cat-count {
  color: var(--text-secondary);
  font-size: 0.875rem;
  font-weight: normal;
}

.epd-cat-items {
  padding-left: 2.5rem;
}

.epd-item {
  display: flex;
  align-items: flex-start;
  gap: 0.5rem;
  padding: 0.25rem 0;
  cursor: pointer;
  font-size: 0.875rem;
  color: var(--text-secondary);
}
.epd-item:hover {
  color: var(--text-primary);
}
.epd-item input { margin-top: 0.15rem; cursor: pointer; flex-shrink: 0; }

.epd-item-text {
  word-break: break-all;
}

.epd-status-summary {
  font-style: italic;
  cursor: default;
  padding-left: 1.25rem;
}

.epd-footer {
  padding: 1rem 1.5rem;
  background-color: var(--bg-secondary);
  border-bottom-left-radius: var(--radius-lg);
  border-bottom-right-radius: var(--radius-lg);
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 0.75rem;
  flex-shrink: 0;
}

.epd-selected-info {
  color: var(--text-secondary);
  font-size: 0.875rem;
  margin-right: auto;
  margin-left: 0.5rem;
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
