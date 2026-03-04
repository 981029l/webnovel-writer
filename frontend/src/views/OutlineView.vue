<!-- Copyright (c) 2026 左岚. All rights reserved. -->
<!-- OutlineView.vue - 现代化大纲编辑页面 -->
<script setup>
import { ref, onMounted, watch, computed } from 'vue'
import { outlinesApi, aiApi } from '../api'
import { useAiTaskStore } from '../stores/aiTask'
import { useProjectStore } from '../stores/project'
import ConfirmDialog from '../components/ConfirmDialog.vue'
import InputDialog from '../components/InputDialog.vue'

const outlines = ref([])
const totalOutline = ref(null)
const selectedVolume = ref(null)
const editContent = ref('')
const loading = ref(false)
const saving = ref(false)
const aiPlanning = ref(false)
const message = ref('')
const showSidebar = ref(true)

// View Mode: 'text' or 'kanban'
const viewMode = ref('text')
const cards = ref([])
const dragIndex = ref(null)

// Dialog State
const showConfirmDialog = ref(false)
const showGuidanceDialog = ref(false)
const showChapterCountDialog = ref(false)
const showDeleteVolumeDialog = ref(false)
const deleteVolumeTarget = ref(null)
const deleteVolumeMode = ref('outline_only') // outline_only | with_characters
const dialogTempData = ref({}) // To store temp data during dialog flow
const projectStore = useProjectStore()
const aiTaskStore = useAiTaskStore()

onMounted(async () => {
    await loadOutlines()
    
    // 如果正在初始化，保持 AI 状态
    if (aiTaskStore.isRunning) {
        selectedVolume.value = 'total'
        if (aiTaskStore.streamTarget === 'total_outline' && aiTaskStore.streamContent) {
             editContent.value = aiTaskStore.streamContent
        }
    }
})

// === Sync Logic ===
watch(editContent, (newVal) => {
    if (viewMode.value === 'kanban') {
        const blocks = newVal.split(/\n\s*\n/).filter(b => b.trim())
        cards.value = blocks.map((b, i) => ({ id: i, text: b.trim() }))
    }
})

watch(viewMode, (newMode) => {
    if (newMode === 'kanban') {
        // Parse text into cards
        const blocks = (editContent.value || '').split(/\n\s*\n/).filter(b => b.trim())
        cards.value = blocks.map((b, i) => ({ id: i, text: b.trim() }))
    } else {
        // Sync back to text
        editContent.value = cards.value.map(c => c.text).join('\n\n')
    }
})

// === Drag and Drop Kanban ===
function onDragStart(index, event) {
    dragIndex.value = index
    event.dataTransfer.effectAllowed = 'move'
    // 稍微延迟隐藏拖拽的原元素，以获得原图
    setTimeout(() => {
        event.target.classList.add('dragging')
    }, 0)
}

function onDragOver(index, event) {
    event.preventDefault()
    // Here we can swap dynamically or just let it drop
}

function onDrop(index, event) {
    event.preventDefault()
    if (dragIndex.value !== null && dragIndex.value !== index) {
        // Swap or Move
        const items = [...cards.value]
        const draggedItem = items.splice(dragIndex.value, 1)[0]
        items.splice(index, 0, draggedItem)
        cards.value = items
        // Auto sync to text
        editContent.value = cards.value.map(c => c.text).join('\n\n')
    }
    dragIndex.value = null
}

function onDragEnd(event) {
    event.target.classList.remove('dragging')
    dragIndex.value = null
}

function updateCard(index, newText) {
    cards.value[index].text = newText
    editContent.value = cards.value.map(c => c.text).join('\n\n')
}

// === Existing Logic ===

// 监听流式内容更新
watch(() => aiTaskStore?.streamContent, (newContent) => {
    if (aiTaskStore?.streamTarget === 'total_outline' && selectedVolume.value === 'total') {
        editContent.value = newContent || ''
    }
})

// 安全获取当前步骤名称
const currentStepName = computed(() => {
    if (!aiTaskStore?.initSteps?.length) return '初始化中...'
    const lastStep = aiTaskStore.initSteps[aiTaskStore.initSteps.length - 1]
    return lastStep?.name || '初始化中...'
})

// 监听任务结束（如果是初始化且成功）
watch(() => aiTaskStore?.result, async (newResult) => {
    if (newResult?.success && aiTaskStore?.taskName === '项目初始化') {
        await loadOutlines()
        selectedVolume.value = 'total'
        const total = outlines.value.find(o => o.volume === 0)
        if (totalOutline.value) {
           editContent.value = totalOutline.value.content || ''
        } else if (total) {
           editContent.value = total.content || ''
        }
    }
})

// 监听项目切换，实时刷新大纲
watch(() => projectStore.projectRoot, async (newRoot) => {
  if (newRoot) {
    if (aiTaskStore.isRunning) return
    message.value = '🔄 正在同步项目大纲...'
    selectedVolume.value = null
    await loadOutlines()
  }
})

// 自动清除消息提示
let messageTimer = null
watch(message, (val) => {
  if (messageTimer) clearTimeout(messageTimer)
  if (val && (val.startsWith('✓') || val.startsWith('✗'))) {
    messageTimer = setTimeout(() => { message.value = '' }, 3000)
  }
})

async function loadOutlines() {
  loading.value = true
  try {
    const { data } = await outlinesApi.getAll()
    outlines.value = data.outlines || []
    totalOutline.value = data.total_outline || null
  } catch (e) {
    message.value = '✗ 加载失败：' + e.message
  } finally {
    loading.value = false
  }
}

function selectOutline(type, volume = null) {
  if (type === 'total') {
    selectedVolume.value = 'total'
    editContent.value = totalOutline.value?.content || ''
  } else {
    selectedVolume.value = volume
    const outline = outlines.value.find(o => o.volume === volume)
    editContent.value = outline?.content || ''
  }
  if (window.innerWidth < 768) showSidebar.value = false
}

async function saveOutline() {
  saving.value = true
  message.value = ''
  try {
    // If we are in Kanban mode, ensure text reflects cards
    if (viewMode.value === 'kanban') {
      editContent.value = cards.value.map(c => c.text).join('\n\n')
    }
    
    if (!selectedVolume.value) return 
    if (selectedVolume.value === 'total') {
      await outlinesApi.updateTotal(editContent.value)
    } else {
      await outlinesApi.updateVolume(selectedVolume.value, editContent.value)
    }
    message.value = '✓ 保存成功'
    await loadOutlines()
  } catch (e) {
    message.value = '✗ 保存失败：' + e.message
  } finally {
    saving.value = false
  }
}

function confirmDeleteVolume(volume, event) {
  event.stopPropagation()
  deleteVolumeTarget.value = volume
  deleteVolumeMode.value = 'outline_only'
  showDeleteVolumeDialog.value = true
}

async function doDeleteVolume() {
  if (deleteVolumeTarget.value == null) return
  try {
    const withCharacters = deleteVolumeMode.value === 'with_characters'
    const { data } = await outlinesApi.deleteVolume(deleteVolumeTarget.value, withCharacters)
    showDeleteVolumeDialog.value = false
    // If we just deleted the selected volume, clear selection
    if (selectedVolume.value === deleteVolumeTarget.value) {
      selectedVolume.value = null
      editContent.value = ''
    }
    deleteVolumeTarget.value = null
    if (withCharacters) {
      const c = data?.deleted_character_count || 0
      message.value = c > 0 ? `✓ 已删除（联动删除角色 ${c} 个）` : '✓ 已删除（无可联动删除角色）'
    } else {
      message.value = '✓ 已删除'
    }
    await loadOutlines()
  } catch (e) {
    message.value = '✗ 删除失败：' + (e.response?.data?.detail || e.message)
  }
}

function aiPlanVolume() {
  const isTotal = selectedVolume.value === 'total'
  let targetVolume = isTotal ? 0 : selectedVolume.value
  
  // Store context for dialogs
  dialogTempData.value = { targetVolume, isTotal }

  if (isTotal) {
    if (editContent.value?.length > 50) {
      showConfirmDialog.value = true
      return
    }
    openGuidanceDialog()
  } else {
    showChapterCountDialog.value = true
  }
}

// Dialog Handlers
function openGuidanceDialog() {
  showGuidanceDialog.value = true
}

async function handleGuidanceConfirm(guidance) {
  showGuidanceDialog.value = false
  await executeAiPlan(dialogTempData.value.targetVolume, 0, guidance)
}

async function handleChapterCountConfirm(count) {
  showChapterCountDialog.value = false
  await executeAiPlan(dialogTempData.value.targetVolume, parseInt(count) || 30, "")
}

async function handleOverwriteConfirm() {
  showConfirmDialog.value = false
  openGuidanceDialog()
}

async function executeAiPlan(targetVolume, count, guidance) {
  aiPlanning.value = true
  editContent.value = ''
  viewMode.value = 'text' // 自动切回文本模式以显示流

  const taskName = targetVolume === 0 ? '规划总纲' : `规划第 ${targetVolume} 卷大纲`
  aiTaskStore.startTask(taskName)

  try {
    const response = await aiApi.planVolumeStream(targetVolume, count, guidance)
    const reader = response.body.getReader()
    const decoder = new TextDecoder()

    let fullContent = ''
    let buffer = ''
    while (true) {
      const { done, value } = await reader.read()
      if (done) break

      buffer += decoder.decode(value, { stream: true })
      const parts = buffer.split('\n\n')
      buffer = parts.pop()

      for (const part of parts) {
        const line = part.trim()
        if (!line.startsWith('data: ')) continue
        const data = JSON.parse(line.substring(6))
        if (data.type === 'error') {
          throw new Error(data.message)
        } else if (data.type === 'step') {
          aiTaskStore.updateStep({ step: data.name, name: data.name, status: data.status === 'processing' ? 'active' : 'completed' })
          message.value = data.name + '...'
        } else if (data.type === 'content') {
          fullContent += data.chunk
          editContent.value = fullContent
        } else if (data.type === 'done') {
          aiTaskStore.completeTask(true, `${taskName}完成`)
          message.value = `${taskName}完成`
          await loadOutlines()
        }
      }
    }
  } catch (e) {
    aiTaskStore.failTask(e.message)
    message.value = '✗ AI 规划失败：' + e.message
  } finally {
    aiPlanning.value = false
  }
}

function createNewVolume() {
  const nextVolume = outlines.value.length + 1
  selectedVolume.value = nextVolume
  editContent.value = ''
}

// ----------------- Outline Polishing -----------------
const showPolishDialog = ref(false)

function polishOutline() {
  if (!editContent.value) return
  showPolishDialog.value = true
}

async function handlePolishConfirm(requirements) {
  showPolishDialog.value = false
  await executeAiPolish(selectedVolume.value, requirements)
}

async function executeAiPolish(volume, requirements) {
  const currentContent = editContent.value
  if (!currentContent) return

  aiPlanning.value = true
  editContent.value = ''
  viewMode.value = 'text'

  const vNum = volume === 'total' ? 0 : volume
  const taskName = `润色${volume === 'total' ? '总纲' : '第 ' + volume + ' 卷大纲'}`

  aiTaskStore.startTask(taskName)

  try {
    const response = await aiApi.polishOutlineStream(vNum, currentContent, requirements)
    const reader = response.body.getReader()
    const decoder = new TextDecoder()

    let fullContent = ''
    let buffer = ''
    while (true) {
      const { done, value } = await reader.read()
      if (done) break

      buffer += decoder.decode(value, { stream: true })
      const parts = buffer.split('\n\n')
      buffer = parts.pop()

      for (const part of parts) {
        const line = part.trim()
        if (!line.startsWith('data: ')) continue
        const data = JSON.parse(line.substring(6))
        if (data.type === 'error') {
          throw new Error(data.message)
        } else if (data.type === 'step') {
          aiTaskStore.updateStep({ step: data.name, name: data.name, status: data.status === 'processing' ? 'active' : 'completed' })
          message.value = data.name + '...'
        } else if (data.type === 'content') {
          fullContent += data.chunk
          editContent.value = fullContent
        } else if (data.type === 'done') {
          aiTaskStore.completeTask(true, `${taskName}完成`)
          message.value = `${taskName}完成`
          await loadOutlines()
        }
      }
    }
  } catch (e) {
    aiTaskStore.failTask(e.message)
    message.value = '✗ AI 润色失败：' + e.message
    if (!editContent.value) editContent.value = currentContent
  } finally {
    aiPlanning.value = false
  }
}
</script>

<template>
  <div class="outline-layout backend-bg">
    <!-- 左侧导航栏 -->
    <aside class="outline-sidebar" :class="{ collapsed: !showSidebar }">
      <div class="sidebar-header">
        <div class="header-row">
            <h2 class="sidebar-title">
            <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor" class="size-5 mr-2"><path stroke-linecap="round" stroke-linejoin="round" d="M3.75 6.75h16.5M3.75 12h16.5m-16.5 5.25h16.5" /></svg>
            大纲目录
            </h2>
            <button class="icon-btn sidebar-btn" @click="createNewVolume" title="新建卷" v-if="!aiTaskStore.isRunning">
            <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor" class="size-5"><path stroke-linecap="round" stroke-linejoin="round" d="M12 4.5v15m7.5-7.5h-15" /></svg>
            </button>
        </div>
        
        <!-- 初始化状态指示 -->
        <!-- <div v-if="aiTaskStore.isRunning && aiTaskStore.taskName === '项目初始化'" class="init-mini-status">
            <span class="status-dot pulse"></span>
            <span class="status-text">{{ currentStepName }}</span>
        </div> -->
      </div>

      <div class="outline-list">
        <div 
          class="outline-item total-outline"
          :class="{ active: selectedVolume === 'total' }"
          @click="selectOutline('total')"
        >
          <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor" class="size-4 item-icon"><path stroke-linecap="round" stroke-linejoin="round" d="M12 21a9.004 9.004 0 0 0 8.716-6.747M12 21a9.004 9.004 0 0 1-8.716-6.747M12 21c2.485 0 4.5-4.03 4.5-9S14.485 3 12 3m0 18c-2.485 0-4.5-4.03-4.5-9S9.515 3 12 3m0 0a8.997 8.997 0 0 1 7.843 4.582M12 3a8.997 8.997 0 0 0-7.843 4.582m15.686 0A11.953 11.953 0 0 1 12 10.5c-2.998 0-5.74-1.1-7.843-2.918m15.686 0A8.959 8.959 0 0 1 21 12c0 .778-.099 1.533-.284 2.253m0 0A17.919 17.919 0 0 1 12 16.5c-3.162 0-6.133-.815-8.716-2.247m0 0A9.015 9.015 0 0 1 3 12c0-1.605.42-3.113 1.157-4.418" /></svg>
          <span class="item-title">全书总纲</span>
        </div>

        <div class="divider"></div>
        <div class="section-label">分卷大纲</div>

        <div
          v-for="outline in outlines"
          :key="outline.id"
          class="outline-item"
          :class="{ active: selectedVolume === outline.volume }"
          @click="selectOutline('volume', outline.volume)"
        >
          <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor" class="size-4 item-icon"><path stroke-linecap="round" stroke-linejoin="round" d="M12 6.042A8.967 8.967 0 0 0 6 3.75c-1.052 0-2.062.18-3 .512v14.25A8.987 8.987 0 0 1 6 18c2.305 0 4.408.867 6 2.292m0-14.25a8.966 8.966 0 0 1 6-2.292c1.052 0 2.062.18 3 .512v14.25A8.987 8.987 0 0 0 18 18a8.967 8.967 0 0 0-6 2.292m0-14.25v14.25" /></svg>
          <span class="item-title">第{{ outline.volume }}卷 {{ outline.title }}</span>
          <button class="item-delete-btn" @click="confirmDeleteVolume(outline.volume, $event)" title="删除此卷">
            <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor" class="size-3-5"><path stroke-linecap="round" stroke-linejoin="round" d="M6 18 18 6M6 6l12 12" /></svg>
          </button>
        </div>

        <div v-if="outlines.length === 0" class="empty-hint">
          点击上方 + 新建第一卷
        </div>
      </div>

      <div class="sidebar-footer">
        <button class="toggle-btn" @click="showSidebar = !showSidebar">
          <svg v-if="showSidebar" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor" class="size-5"><path stroke-linecap="round" stroke-linejoin="round" d="M15.75 19.5 8.25 12l7.5-7.5" /></svg>
          <svg v-else xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor" class="size-5"><path stroke-linecap="round" stroke-linejoin="round" d="m8.25 4.5 7.5 7.5-7.5 7.5" /></svg>
        </button>
      </div>
    </aside>

    <!-- 右侧编辑区 -->
    <main class="outline-main">
      <div v-if="selectedVolume" class="editor-container">
        <!-- 顶部工具栏 -->
        <header class="editor-header">
          <div class="header-left">
            <h2 class="volume-title">
              {{ selectedVolume === 'total' ? '全书总纲' : `第 ${selectedVolume} 卷大纲` }}
            </h2>
            <span v-if="aiPlanning" class="ai-status">
              <span class="pulse-dot"></span> AI 演算中...
            </span>
          </div>
          
          <div class="header-actions">
            <!-- 视图切换 -->
            <div class="view-toggle tabs-panel">
                <button :class="{'active': viewMode === 'text'}" @click="viewMode = 'text'" title="文本编辑视图">📄 文本</button>
                <button :class="{'active': viewMode === 'kanban'}" @click="viewMode = 'kanban'" title="看板拖拽视图">🗂️ 看板</button>
            </div>

            <button class="btn btn-ai outline-btn" @click="aiPlanVolume" :disabled="aiPlanning">
              ✨ {{ selectedVolume === 'total' ? 'AI 智能规划' : 'AI 规划本卷' }}
            </button>
            <button class="btn btn-secondary outline-btn" @click="polishOutline" :disabled="aiPlanning || !editContent" title="润色当前大纲">
               🪄 润色
            </button>
            <button class="btn btn-primary primary-btn" @click="saveOutline" :disabled="saving">
              💾 {{ saving ? '保存中...' : '保存' }}
            </button>
          </div>
        </header>

        <!-- 编辑区域 -->
        <div class="editor-wrapper">
          <!-- Text Mode -->
          <textarea
            v-show="viewMode === 'text'"
            v-model="editContent"
            class="main-textarea text-editor-box"
            :placeholder="selectedVolume === 'total' ? '输入全书大纲或点击 AI 生成...' : '输入分卷细纲或点击 AI 生成...'"
            spellcheck="false"
          ></textarea>

          <!-- Kanban Mode -->
          <div v-show="viewMode === 'kanban'" class="kanban-board">
              <div v-if="cards.length === 0" class="kanban-empty">
                  <span>没有任何卡片。请在文本模式输入内容，段落间通过空行区隔卡片。</span>
              </div>
              <div class="kanban-columns">
                  <div class="kanban-column">
                      <!-- 可拖拽卡片列表 -->
                      <div 
                        v-for="(card, index) in cards" 
                        :key="card.id"
                        class="kanban-card theme-card"
                        draggable="true"
                        @dragstart="onDragStart(index, $event)"
                        @dragover.prevent="onDragOver(index, $event)"
                        @drop="onDrop(index, $event)"
                        @dragend="onDragEnd"
                      >
                          <div class="card-drag-handle">::</div>
                          <textarea 
                            v-model="card.text" 
                            @input="updateCard(index, card.text)" 
                            class="card-textarea"
                          ></textarea>
                      </div>
                  </div>
              </div>
          </div>
        </div>
        
        <!-- 状态提示 -->
        <div v-if="message" class="toast-message" :class="{ error: message.startsWith('✗') }">
          {{ message }}
        </div>
      </div>

      <!-- 空状态 -->
      <div v-else class="empty-state">
        <div class="empty-content theme-empty">
          <div class="empty-icon">📂</div>
          <h3>选择或创建一个大纲</h3>
          <p>好的大纲是成功的一半。从左侧选择总纲开始规划吧。</p>
          <button class="primary-btn btn-large" @click="selectOutline('total')">打开全书总纲</button>
        </div>
      </div>
    </main>

    <!-- Dialogs -->
    <ConfirmDialog
      :is-open="showConfirmDialog"
      title="确认覆盖"
      message="当前总纲已有内容，确定要让 AI 重新规划并覆盖吗？此操作不可撤销。"
      confirm-text="确定覆盖"
      type="warning"
      @confirm="handleOverwriteConfirm"
      @cancel="showConfirmDialog = false"
    />

    <InputDialog
      :is-open="showGuidanceDialog"
      title="总纲指导"
      label="请输入您对总纲的指导意见（可选）："
      placeholder="例如：赛博朋克风格、主角是黑客、快节奏爽文..."
      input-type="text"
      @confirm="handleGuidanceConfirm"
      @cancel="showGuidanceDialog = false"
    />

    <InputDialog
      :is-open="showChapterCountDialog"
      title="章节规划"
      label="请输入本卷计划章节数："
      default-value="30"
      input-type="number"
      @confirm="handleChapterCountConfirm"
      @cancel="showChapterCountDialog = false"
    />

    <InputDialog
      :is-open="showPolishDialog"
      title="大纲润色"
      label="请输入润色要求："
      placeholder="例如：每一章都加上伤亡统计、增加反派戏份、调整节奏..."
      input-type="textarea"
      @confirm="handlePolishConfirm"
      @cancel="showPolishDialog = false"
    />

    <ConfirmDialog
      :is-open="showDeleteVolumeDialog"
      title="确认删除"
      :message="`确定要删除第 ${deleteVolumeTarget} 卷大纲吗？此操作不可撤销。`"
      confirm-text="删除"
      type="danger"
      @confirm="doDeleteVolume"
      @cancel="showDeleteVolumeDialog = false"
    >
      <div class="delete-options">
        <label class="delete-option">
          <input v-model="deleteVolumeMode" type="radio" value="outline_only" />
          <span>仅删大纲（推荐）</span>
        </label>
        <label class="delete-option danger">
          <input v-model="deleteVolumeMode" type="radio" value="with_characters" />
          <span>连同该卷自动生成角色一起删（危险）</span>
        </label>
        <p class="delete-note" v-if="deleteVolumeMode === 'with_characters'">
          只会删除带“档案创建于第{{ deleteVolumeTarget }}卷大纲生成时”标记的角色档案，并尝试同步活跃角色表。
        </p>
      </div>
    </ConfirmDialog>
  </div>
</template>

<style scoped>
/* Standard Clean Backend Background Foundation */
.backend-bg {
  background-color: #f3f4f6; /* Very light gray */
  color: #111827; /* Dark text */
}

.outline-layout {
  display: flex;
  height: 100%;
  width: 100%;
  overflow: hidden;
}

/* Sidebar Specifics */
.outline-sidebar {
  width: 280px;
  background-color: #ffffff;
  border-right: 1px solid #e5e7eb;
  display: flex;
  flex-direction: column;
  transition: width 0.3s cubic-bezier(0.4, 0, 0.2, 1);
  flex-shrink: 0;
  z-index: 10;
  box-shadow: 1px 0 5px rgba(0,0,0,0.02);
}
.outline-sidebar.collapsed { width: 0; border: none; overflow: hidden; }
.outline-sidebar.collapsed * { display: none; }

.sidebar-header {
  padding: 1.5rem;
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
  border-bottom: 1px solid #e5e7eb;
}

.header-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  width: 100%;
}

.sidebar-title {
  font-size: 1.2rem;
  font-weight: 700;
  display: flex;
  align-items: center;
  color: #111827;
  margin: 0;
}

.icon-btn.sidebar-btn {
  width: 32px; height: 32px;
  border-radius: 8px;
  display: flex; align-items: center; justify-content: center;
  cursor: pointer;
  background-color: #f3f4f6;
  border: 1px solid #e5e7eb;
  color: #4b5563;
  transition: all 0.2s;
}
.icon-btn.sidebar-btn:hover {
  background-color: #e5e7eb;
  color: #111827;
}

.outline-list {
  flex: 1;
  overflow-y: auto;
  padding: 1rem;
}

.outline-item {
  display: flex;
  align-items: center;
  padding: 0.8rem 1rem;
  border-radius: 8px;
  cursor: pointer;
  margin-bottom: 6px;
  color: #4b5563;
  transition: all 0.2s;
  border: 1px solid transparent;
}

.outline-item:hover {
  background-color: #f3f4f6;
}

.outline-item.active {
  background-color: #f0ebe3;
  border-color: #c7d2fe;
  color: #6b5840;
  font-weight: 600;
}

.item-icon { flex-shrink: 0; margin-right: 0.75rem; }
.item-title { font-size: 0.9rem; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; flex: 1; }

.item-delete-btn {
  flex-shrink: 0;
  background: none;
  border: none;
  color: #9ca3af;
  cursor: pointer;
  padding: 0.25rem;
  border-radius: 4px;
  display: flex;
  align-items: center;
  justify-content: center;
  opacity: 0;
  transition: all 0.15s;
  margin-left: auto;
}
.outline-item:hover .item-delete-btn { opacity: 1; }
.item-delete-btn:hover { background: #fee2e2; color: #ef4444; }
.size-3-5 { width: 0.875rem; height: 0.875rem; }

.total-outline { font-weight: 600; }
.divider { height: 1px; background-color: #e5e7eb; margin: 1rem 0; }
.section-label { font-size: 0.75rem; color: #9ca3af; padding: 0 1rem 0.5rem; text-transform: uppercase; letter-spacing: 1px; font-weight: 600; }
.empty-hint { font-size: 0.85rem; color: #9ca3af; text-align: center; margin-top: 1rem; }

.sidebar-footer { padding: 1rem; border-top: 1px solid #e5e7eb; display: flex; justify-content: flex-end; }
.toggle-btn {
  background: transparent;
  border: none;
  padding: 0.5rem;
  border-radius: 8px;
  cursor: pointer;
  color: #9ca3af;
  transition: all 0.2s;
}
.toggle-btn:hover { background-color: #f3f4f6; color: #4b5563; }

/* Main Content area */
.outline-main {
  flex: 1;
  display: flex;
  flex-direction: column;
  position: relative;
}

.editor-container {
  display: flex;
  flex-direction: column;
  height: 100%;
  max-width: 1200px;
  margin: 0 auto;
  width: 100%;
}

.editor-header {
  padding: 1.5rem 2.5rem;
  display: flex;
  align-items: center;
  justify-content: space-between;
  background-color: #ffffff;
  border-bottom: 1px solid #e5e7eb;
  z-index: 5;
  box-shadow: 0 1px 2px rgba(0,0,0,0.03);
}

.volume-title { font-size: 1.5rem; font-weight: 700; color: #111827; margin: 0; }

.header-left {
  display: flex;
  align-items: center;
}

.init-mini-status {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  font-size: 0.85rem;
  color: #6b5840;
  background: #f0ebe3;
  padding: 0.35rem 0.75rem;
  border-radius: 6px;
}

.status-dot {
  width: 8px;
  height: 8px;
  background-color: #6b5840;
  border-radius: 50%;
  flex-shrink: 0;
}

.status-dot.pulse {
  animation: pulse 1s infinite alternate;
}

.status-text {
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.ai-status {
  font-size: 0.9rem;
  color: #6b5840;
  display: flex;
  align-items: center;
  gap: 0.5rem;
  margin-left: 1.5rem;
  background: #f0ebe3;
  padding: 0.3rem 0.8rem;
  border-radius: 20px;
}

.pulse-dot {
  width: 8px; height: 8px;
  background-color: #6b5840;
  border-radius: 50%;
  animation: pulse 1s infinite alternate;
}
@keyframes pulse { from { opacity: 0.4; } to { opacity: 1; } }

.header-actions { display: flex; gap: 0.8rem; align-items: center; }

/* View Tabs */
.tabs-panel {
    display: flex;
    background-color: #f3f4f6;
    border-radius: 8px;
    padding: 3px;
    border: 1px solid #e5e7eb;
}
.tabs-panel button {
    background: transparent;
    border: none;
    color: #4b5563;
    padding: 6px 14px;
    border-radius: 6px;
    cursor: pointer;
    font-size: 0.85rem;
    font-weight: 600;
    transition: all 0.2s;
}
.tabs-panel button.active {
    background-color: #ffffff;
    color: #111827;
    box-shadow: 0 1px 3px rgba(0,0,0,0.1);
}

.btn {
    padding: 0.5rem 1rem;
    border-radius: 8px;
    font-size: 0.9rem;
    font-weight: 500;
    cursor: pointer;
    display: flex;
    align-items: center;
}

.outline-btn {
  background-color: #ffffff;
  border: 1px solid #d1d5db;
  color: #374151;
  transition: all 0.2s;
}
.outline-btn:hover:not(:disabled) {
  background-color: #f9fafb;
  border-color: #9ca3af;
}

.primary-btn {
  background-color: #6b5840;
  border: none;
  color: white;
  box-shadow: 0 1px 2px rgba(0,0,0,0.05);
  transition: all 0.2s;
  padding: 0.5rem 1rem;
  border-radius: 8px;
  cursor: pointer;
  font-weight: 500;
}
.primary-btn:hover:not(:disabled) {
  background-color: #5c4a32;
  box-shadow: 0 4px 6px -1px rgba(107, 88, 64, 0.2), 0 2px 4px -1px rgba(107, 88, 64, 0.1);
}
.btn-large {
  padding: 0.8rem 1.5rem;
  font-size: 1rem;
  border-radius: 8px;
}

/* Editor Wrapper */
.editor-wrapper {
  flex: 1;
  overflow: hidden; 
  position: relative;
  background-color: #f9fafb;
}

.text-editor-box {
  width: 100%;
  height: 100%;
  border: none;
  resize: none;
  font-size: 1.05rem; 
  line-height: 1.8;
  outline: none;
  font-family: 'Inter', sans-serif;
  padding: 2.5rem 3.5rem; 
  box-sizing: border-box;
  background-color: transparent;
  color: #1f2937;
}

.text-editor-box::placeholder { color: #9ca3af; }

/* Kanban Board Layout */
.kanban-board {
    width: 100%;
    height: 100%;
    padding: 2rem 3rem;
    overflow-y: auto;
    overflow-x: hidden;
}

.kanban-empty {
    text-align: center;
    color: #6b7280;
    padding: 4rem;
    border: 2px dashed #d1d5db;
    border-radius: 12px;
}

.kanban-columns {
    display: flex;
    gap: 1.5rem;
    flex-wrap: wrap;
    align-items: flex-start;
}

.kanban-column {
    flex: 1;
    min-width: 300px;
    display: flex;
    flex-direction: column;
    gap: 1rem;
}

/* Kanban Cards & Drag'N'Drop */
.theme-card {
    background-color: #ffffff;
    border: 1px solid #e5e7eb;
    box-shadow: 0 1px 3px rgba(0, 0, 0, 0.05);
}

.kanban-card {
    border-radius: 8px;
    padding: 1rem 1rem 1rem 2.5rem;
    position: relative;
    cursor: grab;
    transition: transform 0.2s, box-shadow 0.2s, border-color 0.2s;
}

.kanban-card:hover {
    border-color: #a5b4fc;
    box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1), 0 2px 4px -1px rgba(0, 0, 0, 0.06);
}

.kanban-card:active {
    cursor: grabbing;
}

.kanban-card.dragging {
    opacity: 0.5;
    transform: scale(0.98);
}

.card-drag-handle {
    position: absolute;
    left: 10px;
    top: 50%;
    transform: translateY(-50%);
    color: #9ca3af;
    font-weight: bold;
    cursor: grab;
    user-select: none;
}
.card-drag-handle:active { cursor: grabbing; color: #6b5840; }

.card-textarea {
    width: 100%;
    min-height: 80px;
    background: transparent;
    border: none;
    color: #374151;
    resize: vertical;
    outline: none;
    font-family: 'Inter', sans-serif;
    font-size: 0.95rem;
    line-height: 1.6;
}

/* Toast */
.toast-message {
  position: absolute;
  bottom: 2rem;
  left: 50%;
  transform: translateX(-50%);
  background-color: #1f2937;
  color: #fff;
  padding: 0.8rem 1.5rem;
  border-radius: 8px;
  font-size: 0.9rem;
  font-weight: 500;
  animation: slideUpFade 0.3s cubic-bezier(0.16, 1, 0.3, 1);
  display: flex;
  align-items: center;
  gap: 0.5rem;
  box-shadow: 0 10px 15px -3px rgba(0, 0, 0, 0.1);
}

.toast-message.error { background-color: #ef4444; }

.delete-options {
  margin-top: 0.75rem;
  display: flex;
  flex-direction: column;
  gap: 0.55rem;
}

.delete-option {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  font-size: 0.9rem;
  color: #374151;
  cursor: pointer;
}

.delete-option input[type="radio"] {
  accent-color: #6b5840;
}

.delete-option.danger {
  color: #991b1b;
}

.delete-note {
  margin: 0.1rem 0 0;
  padding: 0.5rem 0.6rem;
  border-radius: 8px;
  border: 1px solid #fecaca;
  background: #fef2f2;
  color: #7f1d1d;
  font-size: 0.8rem;
  line-height: 1.5;
}

@keyframes slideUpFade {
  from { opacity: 0; transform: translate(-50%, 15px); }
  to { opacity: 1; transform: translate(-50%, 0); }
}

/* Empty State */
.empty-state {
  display: flex; 
  align-items: center; 
  justify-content: center; 
  height: 100%; 
}
.theme-empty {
    background-color: #ffffff;
    border: 1px dashed #d1d5db;
    padding: 3rem;
    border-radius: 12px;
    text-align: center;
    max-width: 500px;
    box-shadow: 0 1px 2px rgba(0,0,0,0.02);
}
.empty-icon { font-size: 4rem; margin-bottom: 1rem; color: #9ca3af; }
.empty-content h3 { font-size: 1.5rem; margin-bottom: 0.8rem; color: #111827; }
.empty-content p { color: #6b7280; margin-bottom: 2rem; line-height: 1.6; }
</style>
