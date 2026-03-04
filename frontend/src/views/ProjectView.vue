<!-- Copyright (c) 2026 左岚. All rights reserved. -->
<!-- ProjectView.vue - 项目管理页面 (Premium Redesign) -->
<script setup>
import { ref, onMounted, nextTick, watch } from 'vue'
import { useRouter } from 'vue-router'
import { useProjectStore } from '../stores/project'
import { useAiTaskStore } from '../stores/aiTask'
import { aiApi, projectsApi, ragApi } from '../api'
import SearchSelect from '../components/SearchSelect.vue'
import ConfirmDialog from '../components/ConfirmDialog.vue'

const router = useRouter()
const projectStore = useProjectStore()
const aiTaskStore = useAiTaskStore()

// State
const genres = ref([])
const selectedGenre = ref('')
const title = ref('')
const initTargetWords = ref('')
const protagonistName = ref('')
const goldenFingerName = ref('')
const goldenFingerType = ref('')
const additionalInfo = ref('')
const loading = ref(false)
const deleting = ref(false)
const showDeleteDialog = ref(false)
const generatingSynopsis = ref(false)
const message = ref('')

// AI Config State
const aiConfig = ref({ base_url: '', api_key: '', model: '' })
const aiModels = ref([])
const aiModelsLoading = ref(false)
const showAiConfig = ref(false) // Default collapsed
const apiBaseUrls = [
  'http://jiushi.online', 'http://localhost:8000', 'http://127.0.0.1:8317', 'http://localhost:8317', 'https://cifang.xyz',
  'https://api.openai.com', 'https://api.deepseek.com', 'https://api.moonshot.cn'
]

// Title Editing State
const editingTitle = ref(false)
const editTitleValue = ref('')
const titleInput = ref(null)
const editingTargetWords = ref(false)
const editTargetWordsValue = ref('')
const targetWordsInput = ref(null)
const generatingTitles = ref(false)
const showTitlesDialog = ref(false)
const titleCandidates = ref([])
const initSteps = ref([])

// Settings Cards State
const settings = ref({
  worldview: '',
  power_system: '',
  protagonist: ''
})
const settingsExpanded = ref({
  worldview: false,
  power_system: false,
  protagonist: false
})

// Helper Functions
function showMessage(text, duration = 3000) {
  message.value = text
  setTimeout(() => { if (message.value === text) message.value = '' }, duration)
}

async function loadAiConfig() {
  try {
    const { data } = await aiApi.getConfig()
    aiConfig.value = {
      base_url: data.base_url,
      model: data.model,
      api_key: data.has_api_key ? '******' : ''
    }
  } catch (e) { console.error(e) }
}

async function loadModels() {
  if (!aiConfig.value.base_url) return
  aiModelsLoading.value = true
  try {
    const configToUpdate = { ...aiConfig.value }
    if (configToUpdate.api_key === '******') delete configToUpdate.api_key
    await aiApi.updateConfig(configToUpdate)
    const { data } = await aiApi.getModels()
    if (data.success) aiModels.value = data.models
  } catch (e) { console.error('Failed to load models:', e) } 
  finally { aiModelsLoading.value = false }
}

async function saveAiConfig() {
  try {
    const configToUpdate = { ...aiConfig.value }
    if (configToUpdate.api_key === '******') delete configToUpdate.api_key
    await aiApi.updateConfig(configToUpdate)
    showMessage('✓ AI 配置已保存')
    showAiConfig.value = false
  } catch (e) { showMessage('✗ 保存失败：' + e.message) }
}

// Lifecycle
onMounted(async () => {
  try {
    const { data } = await aiApi.getGenres()
    genres.value = data.genres
    if (genres.value.length > 0) selectedGenre.value = genres.value[0].id
  } catch (e) {
    genres.value = [
      { id: '修仙', name: '修仙' }, { id: '系统流', name: '系统流' },
      { id: '都市异能', name: '都市异能' }, { id: '狗血言情', name: '狗血言情' },
    ]
    selectedGenre.value = genres.value[0].id
  }
  await loadAiConfig()
  await projectStore.fetchStatus()
  
  // Load settings if project is initialized
  if (projectStore.initialized) {
    await loadSettings()
  }
  
  // Sync inputs with stored data
  if (projectStore.title && !title.value) title.value = projectStore.title
  if (projectStore.genre) {
     const matched = genres.value.find(g => g.name === projectStore.genre || g.id === projectStore.genre)
     if (matched) selectedGenre.value = matched.id
  }
  if (projectStore.targetWords && !projectStore.initialized && !initTargetWords.value) {
    initTargetWords.value = String(projectStore.targetWords)
  }
})

async function loadSettings() {
  try {
    const { data } = await projectsApi.getSettings()
    settings.value = {
      worldview: data.worldview || '',
      power_system: data.power_system || '',
      protagonist: data.protagonist || ''
    }
  } catch (e) {
    console.error('Failed to load settings:', e)
  }
}

// Watchers
watch(() => projectStore.title, (newVal) => {
  if (newVal && !title.value && !projectStore.initialized) title.value = newVal
})
watch(() => projectStore.genre, (newVal) => {
  if (newVal && !selectedGenre.value && !projectStore.initialized) {
     const matched = genres.value.find(g => g.name === newVal || g.id === newVal)
     if (matched) selectedGenre.value = matched.id
  }
})
watch(() => projectStore.targetWords, (newVal) => {
  if (newVal && !projectStore.initialized && !initTargetWords.value) {
    initTargetWords.value = String(newVal)
  }
})

// Actions
async function initProject() {
  if (!selectedGenre.value || !title.value) {
    showMessage('请填写小说标题')
    return
  }

  let parsedTargetWords = null
  const rawTargetWords = initTargetWords.value.trim()
  if (rawTargetWords) {
    parsedTargetWords = parseInt(rawTargetWords.replace(/[^\d]/g, ''), 10)
    if (!Number.isFinite(parsedTargetWords) || parsedTargetWords <= 0) {
      showMessage('✗ 请输入有效的目标字数')
      return
    }
  }

  loading.value = true
  initSteps.value = []

  // Watch for streaming start — navigate to outline once content begins flowing
  const stopWatch = watch(() => aiTaskStore.streamContent, (val) => {
    if (val) {
      stopWatch()
      router.push('/workspace/outline')
    }
  })

  try {
    const payload = {
      title: title.value,
      genre: selectedGenre.value,
      protagonist_name: protagonistName.value,
      golden_finger_name: goldenFingerName.value,
      golden_finger_type: goldenFingerType.value,
      additional_info: additionalInfo.value,
      mode: 'standard'
    }
    if (parsedTargetWords) payload.target_words = parsedTargetWords

    await aiTaskStore.initProjectAction({
      ...payload
    }, aiApi)
    // Stream finished — refresh project status
    await projectStore.fetchStatus()
  } catch (e) {
    stopWatch()
    showMessage('初始化失败：' + e.message)
  } finally {
    loading.value = false
  }
}

function deleteProject() { showDeleteDialog.value = true }

async function handleDeleteConfirm() {
  showDeleteDialog.value = false
  deleting.value = true
  try {
    const { data } = await projectsApi.reset()
    showMessage('✓ ' + data.message)
    await projectStore.fetchStatus()
  } catch (e) { showMessage('✗ 删除失败：' + e.message) } 
  finally { deleting.value = false }
}

async function generateSynopsisAI() {
  generatingSynopsis.value = true
  showMessage('AI 正在构思简介...', 60000)
  try {
    const { data } = await aiApi.generateSynopsis()
    if (data.success && data.synopsis) {
      projectStore.description = data.synopsis 
      await projectStore.fetchStatus()
      showMessage('✓ 简介已生成')
    }
  } catch (err) { showMessage('✗ 生成失败') } 
  finally { generatingSynopsis.value = false }
}

async function copyDescription() {
  if (!projectStore.description) return
  try {
    await navigator.clipboard.writeText(projectStore.description)
    showMessage('✓ 已复制')
  } catch (err) { showMessage('✗ 复制失败') }
}

// Title Logic
function startEditTitle() {
  editTitleValue.value = projectStore.title || ''
  editingTitle.value = true
  nextTick(() => titleInput.value?.focus())
}

async function saveTitle() {
  if (!editingTitle.value) return
  const newTitle = editTitleValue.value.trim()
  editingTitle.value = false
  if (newTitle && newTitle !== projectStore.title) {
    try {
      await aiApi.updateProjectInfo({ title: newTitle })
      await projectStore.fetchStatus()
      showMessage('✓ 标题已更新')
    } catch (e) { showMessage('✗ 更新失败') }
  }
}

async function generateTitlesAI() {
  generatingTitles.value = true
  try {
    const { data } = await aiApi.generateTitles()
    if (data.success && data.titles) {
      titleCandidates.value = data.titles
      showTitlesDialog.value = true
    }
  } catch (e) { showMessage('✗ 生成失败') } 
  finally { generatingTitles.value = false }
}

async function selectTitle(t) {
  try {
    await aiApi.updateProjectInfo({ title: t })
    await projectStore.fetchStatus()
    showTitlesDialog.value = false
    showMessage('✓ 标题已应用')
  } catch (e) { showMessage('✗ 更新失败') }
}

function formatTargetWords(words) {
  if (!words || words <= 0) return '未设置'
  if (words >= 10000) {
    const w = words / 10000
    return `${Number.isInteger(w) ? w.toFixed(0) : w.toFixed(1)} 万字`
  }
  return `${words} 字`
}

function startEditTargetWords() {
  editTargetWordsValue.value = projectStore.targetWords ? String(projectStore.targetWords) : ''
  editingTargetWords.value = true
  nextTick(() => targetWordsInput.value?.focus())
}

async function saveTargetWords() {
  if (!editingTargetWords.value) return
  editingTargetWords.value = false

  const raw = editTargetWordsValue.value.trim()
  if (!raw) return

  const parsed = parseInt(raw.replace(/[^\d]/g, ''), 10)
  if (!Number.isFinite(parsed) || parsed <= 0) {
    showMessage('✗ 请输入有效的目标字数')
    return
  }

  if (parsed === projectStore.targetWords) return

  try {
    await aiApi.updateProjectInfo({ target_words: parsed })
    await projectStore.fetchStatus()
    showMessage('✓ 目标字数已更新')
  } catch (e) {
    showMessage('✗ 目标字数更新失败')
  }
}
const indexing = ref(false)

async function rebuildIndex() {
  indexing.value = true
  showMessage('🚀 正在重建索引，请稍候...')
  try {
    const { data } = await ragApi.rebuildIndex()
    if (data.success) {
      showMessage(`✓ 索引完成！共处理 ${data.indexed_files} 章，${data.total_chunks} 个片段`)
    } else {
      showMessage('✗ 索引失败：' + data.error)
    }
  } catch (e) {
    showMessage('✗ 请求失败')
  } finally {
    indexing.value = false
  }
}
</script>

<template>
  <div class="project-view">
    <div class="project-content">
      
      <!-- Page Header -->
      <div class="page-header stagger-in">
        <h1 class="page-title">项目管理</h1>
        <p class="page-subtitle">AI 驱动的创作中枢，一键初始化与设定生成</p>
      </div>

      <!-- Initialized View -->
      <div v-if="projectStore.initialized" class="project-dashboard stagger-in-2">
        
        <!-- Status Overview Card -->
        <div class="premium-card overview-card">
          <div class="card-header">
            <h2 class="section-title">
              <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor" class="size-5 text-indigo-500 mr-2"><path stroke-linecap="round" stroke-linejoin="round" d="M11.35 3.836c-.065.21-.1.433-.1.664 0 .414.336.75.75.75h4.5a.75.75 0 0 0 .75-.75 2.25 2.25 0 0 0-.1-.664m-5.8 0A2.251 2.251 0 0 1 13.5 2.25H15c1.012 0 1.867.668 2.15 1.586m-5.8 0c-.376.023-.75.05-1.124.08C9.095 4.01 8.25 4.973 8.25 6.108V8.25m0 0H4.875c-.621 0-1.125.504-1.125 1.125v11.25c0 .621.504 1.125 1.125 1.125h9.75c.621 0 1.125-.504 1.125-1.125V9.375c0-.621-.504-1.125-1.125-1.125H8.25ZM6.75 12h.008v.008H6.75V12Zm0 3h.008v.008H6.75V15Zm0 3h.008v.008H6.75V18Z" /></svg>
              项目概览
            </h2>
            <div class="title-actions">
              <div class="title-display" v-if="!editingTitle">
                 <span class="project-title-text">{{ projectStore.title || '未命名项目' }}</span>
                 <button class="btn-icon-hover" @click="startEditTitle" title="编辑标题">
                   <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor" class="size-4"><path stroke-linecap="round" stroke-linejoin="round" d="m16.862 4.487 1.687-1.688a1.875 1.875 0 1 1 2.652 2.652L6.832 19.82a4.5 4.5 0 0 1-1.897 1.13l-2.685.8.8-2.685a4.5 4.5 0 0 1 1.13-1.897L16.863 4.487Zm0 0L19.5 7.125" /></svg>
                 </button>
              </div>
              <input 
                v-else
                v-model="editTitleValue" 
                ref="titleInput"
                class="title-input-edit"
                @keyup.enter="saveTitle" 
                @blur="saveTitle"
              />
              <button class="btn btn-xs btn-ai-gradient" @click="generateTitlesAI" :disabled="generatingTitles">
                AI 灵感
              </button>
            </div>
          </div>

          <div class="target-words-row">
            <span class="target-words-label">目标字数</span>
            <div v-if="!editingTargetWords" class="target-words-display">
              <span class="target-words-value">{{ formatTargetWords(projectStore.targetWords) }}</span>
              <button class="btn-icon-hover" @click="startEditTargetWords" title="编辑目标字数">
                <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor" class="size-4"><path stroke-linecap="round" stroke-linejoin="round" d="m16.862 4.487 1.687-1.688a1.875 1.875 0 1 1 2.652 2.652L6.832 19.82a4.5 4.5 0 0 1-1.897 1.13l-2.685.8.8-2.685a4.5 4.5 0 0 1 1.13-1.897L16.863 4.487Zm0 0L19.5 7.125" /></svg>
              </button>
            </div>
            <input
              v-else
              ref="targetWordsInput"
              v-model="editTargetWordsValue"
              class="target-words-input"
              placeholder="例如 800000"
              @keyup.enter="saveTargetWords"
              @blur="saveTargetWords"
            />
          </div>
          
          <div class="stats-row">
             <div class="stat-box">
                <div class="stat-icon-bg bg-blue-50 text-blue-600">
                  <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor" class="size-6"><path stroke-linecap="round" stroke-linejoin="round" d="M12 6.042A8.967 8.967 0 0 0 6 3.75c-1.052 0-2.062.18-3 .512v14.25A8.987 8.987 0 0 1 6 18c2.305 0 4.408.867 6 2.292m0-14.25a8.966 8.966 0 0 1 6-2.292c1.052 0 2.062.18 3 .512v14.25A8.987 8.987 0 0 0 18 18a8.967 8.967 0 0 0-6 2.292m0-14.25v14.25" /></svg>
                </div>
                <div class="stat-info">
                  <div class="stat-val">{{ projectStore.totalChapters }}</div>
                  <div class="stat-lab">章节</div>
                </div>
             </div>
             
             <div class="stat-box">
                <div class="stat-icon-bg bg-pink-50 text-pink-600">
                  <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor" class="size-6"><path stroke-linecap="round" stroke-linejoin="round" d="M3.75 6.75h16.5M3.75 12H12m-8.25 5.25h16.5" /></svg>
                </div>
                <div class="stat-info">
                  <div class="stat-val">{{ (projectStore.totalWords / 10000).toFixed(1) }}w</div>
                  <div class="stat-lab">字数</div>
                </div>
             </div>

             <div class="stat-box">
                <div class="stat-icon-bg bg-orange-50 text-orange-600">
                  <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor" class="size-6"><path stroke-linecap="round" stroke-linejoin="round" d="M9.568 3H5.25A2.25 2.25 0 0 0 3 5.25v4.318c0 .597.237 1.17.659 1.591l9.581 9.581c.699.699 1.78.872 2.607.33a18.095 18.095 0 0 0 5.223-5.223c.542-.827.369-1.908-.33-2.607L11.16 3.66A2.25 2.25 0 0 0 9.568 3Z" /></svg>
                </div>
                <div class="stat-info">
                  <div class="stat-val text-sm">{{ projectStore.genre || '未设定' }}</div>
                  <div class="stat-lab">题材</div>
                </div>
             </div>

             <div class="stat-box">
                <div class="stat-icon-bg bg-teal-50 text-teal-600">
                  <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor" class="size-6"><path stroke-linecap="round" stroke-linejoin="round" d="M11.25 11.25l.041-.02a.75.75 0 0 1 1.063.852l-.708 2.836a.75.75 0 0 0 1.063.853l.041-.021M21 12a9 9 0 1 1-18 0 9 9 0 0 1 18 0Zm-9-3.75h.008v.008H12V8.25Z" /></svg>
                </div>
                <div class="stat-info">
                  <div class="stat-val text-sm">{{ projectStore.status || '连载中' }}</div>
                  <div class="stat-lab">状态</div>
                </div>
             </div>
          </div>
        </div>

        <!-- Next Step Guides -->
        <div class="guide-section">
          <h3 class="guide-title">
             <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor" class="size-5"><path stroke-linecap="round" stroke-linejoin="round" d="M3 13.125C3 12.504 3.504 12 4.125 12h2.25c.621 0 1.125.504 1.125 1.125v6.75C7.5 20.496 6.996 21 6.375 21h-2.25A1.125 1.125 0 0 1 3 19.875v-6.75ZM9.75 8.625c0-.621.504-1.125 1.125-1.125h2.25c.621 0 1.125.504 1.125 1.125v11.25c0 .621-.504 1.125-1.125 1.125h-2.25a1.125 1.125 0 0 1-1.125-1.125V8.625ZM16.5 4.125c0-.621.504-1.125 1.125-1.125h2.25C20.496 3 21 3.504 21 4.125v15.75c0 .621-.504 1.125-1.125 1.125h-2.25a1.125 1.125 0 0 1-1.125-1.125V4.125Z" /></svg>
             接下来做什么？
          </h3>
          <div class="guide-grid">
            <div class="guide-card primary-guide" @click="$router.push('/workspace/outline')">
               <div class="guide-icon-wrapper">
                  <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor" class="size-8"><path stroke-linecap="round" stroke-linejoin="round" d="M12 6.042A8.967 8.967 0 0 0 6 3.75c-1.052 0-2.062.18-3 .512v14.25A8.987 8.987 0 0 1 6 18c2.305 0 4.408.867 6 2.292m0-14.25a8.966 8.966 0 0 1 6-2.292c1.052 0 2.062.18 3 .512v14.25A8.987 8.987 0 0 0 18 18a8.967 8.967 0 0 0-6 2.292m0-14.25v14.25" /></svg>
               </div>
               <div class="guide-content">
                 <h4>完善大纲</h4>
                 <p>使用 AI 深度规划分卷剧情</p>
               </div>
               <div class="guide-arrow">→</div>
            </div>

            <div class="guide-card secondary-guide" @click="$router.push('/workspace/write')">
               <div class="guide-icon-wrapper">
                 <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor" class="size-8"><path stroke-linecap="round" stroke-linejoin="round" d="m16.862 4.487 1.687-1.688a1.875 1.875 0 1 1 2.652 2.652L10.582 16.07a4.5 4.5 0 0 1-1.897 1.13L6 18l.8-2.685a4.5 4.5 0 0 1 1.13-1.897l8.932-8.931Zm0 0L19.5 7.125M18 14v4.75A2.25 2.25 0 0 1 15.75 21H5.25A2.25 2.25 0 0 1 3 18.75V8.25A2.25 2.25 0 0 1 5.25 6H10" /></svg>
               </div>
               <div class="guide-content">
                 <h4>开始码字</h4>
                 <p>进入沉浸式写作工作台</p>
               </div>
               <div class="guide-arrow">→</div>
            </div>
          </div>
        </div>

        <!-- Synopsis Card -->
        <div class="premium-card synopsis-card">
          <div class="card-header">
            <h2 class="section-title">
               <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor" class="size-5 text-emerald-500 mr-2"><path stroke-linecap="round" stroke-linejoin="round" d="M19.5 14.25v-2.625a3.375 3.375 0 0 0-3.375-3.375h-1.5A1.125 1.125 0 0 1 13.5 7.125v-1.5a3.375 3.375 0 0 0-3.375-3.375H8.25m0 12.75h7.5m-7.5 3H12M10.5 2.25H5.625c-.621 0-1.125.504-1.125 1.125v17.25c0 .621.504 1.125 1.125 1.125h12.75c.621 0 1.125-.504 1.125-1.125V11.25a9 9 0 0 0-9-9Z" /></svg>
               简介设定
            </h2>
            <div class="header-actions">
              <button class="btn btn-sm btn-secondary" @click="generateSynopsisAI" :disabled="generatingSynopsis">
                {{ generatingSynopsis ? 'AI 生成中...' : 'AI 优化简介' }}
              </button>
            </div>
          </div>
          <div class="synopsis-content">
            {{ projectStore.description || '暂无简介，点击右上角 AI 生成...' }}
          </div>
        </div>
        
        <!-- Settings Cards Grid -->
        <div class="settings-grid">
          <!-- 世界观 Card -->
          <div class="premium-card setting-card" @click="settingsExpanded.worldview = !settingsExpanded.worldview">
            <div class="card-header">
              <h2 class="section-title">
                <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor" class="size-5 text-blue-500 mr-2"><path stroke-linecap="round" stroke-linejoin="round" d="M12 21a9.004 9.004 0 0 0 8.716-6.747M12 21a9.004 9.004 0 0 1-8.716-6.747M12 21c2.485 0 4.5-4.03 4.5-9S14.485 3 12 3m0 18c-2.485 0-4.5-4.03-4.5-9S9.515 3 12 3m0 0a8.997 8.997 0 0 1 7.843 4.582M12 3a8.997 8.997 0 0 0-7.843 4.582m15.686 0A11.953 11.953 0 0 1 12 10.5c-2.998 0-5.74-1.1-7.843-2.918m15.686 0A8.959 8.959 0 0 1 21 12c0 .778-.099 1.533-.284 2.253m0 0A17.919 17.919 0 0 1 12 16.5c-3.162 0-6.133-.815-8.716-2.247m0 0A9.015 9.015 0 0 1 3 12c0-1.605.42-3.113 1.157-4.418" /></svg>
                世界观
              </h2>
              <div class="header-actions">
                <span class="setting-status" :class="settings.worldview ? 'filled' : 'empty'">
                  {{ settings.worldview ? '已设定' : '待填写' }}
                </span>
                <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor" 
                     class="size-5 text-gray-400 transition-transform duration-200" :class="{ 'rotate-180': settingsExpanded.worldview }">
                  <path stroke-linecap="round" stroke-linejoin="round" d="m19.5 8.25-7.5 7.5-7.5-7.5" />
                </svg>
              </div>
            </div>
            <div v-if="settingsExpanded.worldview" class="setting-content" @click.stop>
              <pre>{{ settings.worldview || '暂无世界观设定...' }}</pre>
            </div>
          </div>
          
          <!-- 力量体系 Card -->
          <div class="premium-card setting-card" @click="settingsExpanded.power_system = !settingsExpanded.power_system">
            <div class="card-header">
              <h2 class="section-title">
                <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor" class="size-5 text-purple-500 mr-2"><path stroke-linecap="round" stroke-linejoin="round" d="m3.75 13.5 10.5-11.25L12 10.5h8.25L9.75 21.75 12 13.5H3.75Z" /></svg>
                力量体系
              </h2>
              <div class="header-actions">
                <span class="setting-status" :class="settings.power_system ? 'filled' : 'empty'">
                  {{ settings.power_system ? '已设定' : '待填写' }}
                </span>
                <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor" 
                     class="size-5 text-gray-400 transition-transform duration-200" :class="{ 'rotate-180': settingsExpanded.power_system }">
                  <path stroke-linecap="round" stroke-linejoin="round" d="m19.5 8.25-7.5 7.5-7.5-7.5" />
                </svg>
              </div>
            </div>
            <div v-if="settingsExpanded.power_system" class="setting-content" @click.stop>
              <pre>{{ settings.power_system || '暂无力量体系设定...' }}</pre>
            </div>
          </div>
          
          <!-- 主角卡 Card -->
          <div class="premium-card setting-card" @click="settingsExpanded.protagonist = !settingsExpanded.protagonist">
            <div class="card-header">
              <h2 class="section-title">
                <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor" class="size-5 text-orange-500 mr-2"><path stroke-linecap="round" stroke-linejoin="round" d="M15.75 6a3.75 3.75 0 1 1-7.5 0 3.75 3.75 0 0 1 7.5 0ZM4.501 20.118a7.5 7.5 0 0 1 14.998 0A17.933 17.933 0 0 1 12 21.75c-2.676 0-5.216-.584-7.499-1.632Z" /></svg>
                主角卡
              </h2>
              <div class="header-actions">
                <span class="setting-status" :class="settings.protagonist ? 'filled' : 'empty'">
                  {{ settings.protagonist ? '已设定' : '待填写' }}
                </span>
                <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor" 
                     class="size-5 text-gray-400 transition-transform duration-200" :class="{ 'rotate-180': settingsExpanded.protagonist }">
                  <path stroke-linecap="round" stroke-linejoin="round" d="m19.5 8.25-7.5 7.5-7.5-7.5" />
                </svg>
              </div>
            </div>
            <div v-if="settingsExpanded.protagonist" class="setting-content" @click.stop>
              <pre>{{ settings.protagonist || '暂无主角设定...' }}</pre>
            </div>
          </div>
        </div>
        
        <div class="danger-zone">
           <button class="btn-danger-ghost" @click="deleteProject">重置/删除项目</button>
        </div>

      </div>

      <!-- Not Initialized: Init Form -->
      <div v-if="!projectStore.initialized" class="card init-card stagger-in-2">
        <div class="init-header">
          <h2>开始新的旅程</h2>
          <p>AI 将为你构建完整的世界观、角色与故事总纲</p>
        </div>
        
        <div class="form-grid">
           <!-- Form Inputs (Styled) -->
           <div class="form-group full">
              <label>小说标题</label>
              <input v-model="title" class="input-modern xl" placeholder="例如：斗破苍穹" />
           </div>
           
           <div class="form-group">
              <label>题材分类</label>
              <select v-model="selectedGenre" class="input-modern">
                 <option v-for="g in genres" :key="g.id" :value="g.id">{{ g.name }}</option>
              </select>
           </div>

           <div class="form-group">
              <label>目标字数</label>
              <input
                v-model="initTargetWords"
                class="input-modern"
                inputmode="numeric"
                placeholder="例如：800000（留空默认 2000000）"
              />
           </div>
           
           <div class="form-group">
              <label>核心金手指</label>
              <input v-model="goldenFingerName" class="input-modern" placeholder="例如：深蓝加点" />
           </div>
           
           <!-- More inputs... same logic but better CSS -->
           <div class="form-group full">
              <label>补充设定 (AI 参考)</label>
              <textarea v-model="additionalInfo" class="input-modern textarea" placeholder="描述你的创意核心..."></textarea>
           </div>
        </div>
        
        <div class="init-actions">
           <button class="btn btn-xl btn-primary-gradient full-width" @click="initProject" :disabled="loading">
              {{ loading ? '正在构建世界...' : '✨ AI 一键初始化' }}
           </button>
        </div>
      </div>




      <!-- AI Config Card (Restored & Styled) -->
      <div class="premium-card config-card">
        <div class="card-header" @click="showAiConfig = !showAiConfig" style="cursor: pointer; margin-bottom: 0;">
          <h2 class="section-title">
             <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor" class="size-5 text-gray-500 mr-2"><path stroke-linecap="round" stroke-linejoin="round" d="M10.5 6h9.75M10.5 6a1.5 1.5 0 1 1-3 0m3 0a1.5 1.5 0 1 0-3 0M3.75 6H7.5m3 12h9.75m-9.75 0a1.5 1.5 0 0 1-3 0m3 0a1.5 1.5 0 0 0-3 0m-3.75 0H7.5m9-6h3.75m-3.75 0a1.5 1.5 0 0 1-3 0m3 0a1.5 1.5 0 0 0-3 0m-9.75 0h9.75" /></svg>
             AI 服务配置
          </h2>
          <div class="header-actions">
             <button class="btn btn-xs btn-secondary" @click="rebuildIndex" :disabled="indexing" title="重建 RAG 索引">
               <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor" class="size-4 mr-1" :class="{'animate-spin': indexing}">
                 <path stroke-linecap="round" stroke-linejoin="round" d="M16.023 9.348h4.992v-.001M2.985 19.644v-4.992m0 0h4.992m-4.993 0 3.181 3.183a8.25 8.25 0 0 0 13.803-3.7M4.031 9.865a8.25 8.25 0 0 1 13.803-3.7l3.181 3.182m0-4.991v4.99" />
               </svg>
               {{ indexing ? '索引中...' : '重建索引' }}
             </button>
             <div class="status-indicator">
               <span class="dot" :class="aiConfig.base_url ? 'bg-green-500' : 'bg-red-500'"></span>
               <span class="status-text">{{ aiConfig.base_url ? '已配置' : '未配置' }}</span>
             </div>
             <svg 
               xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor" class="size-5 text-gray-400 transition-transform duration-200"
               :class="{ 'rotate-180': showAiConfig }"
             >
               <path stroke-linecap="round" stroke-linejoin="round" d="m19.5 8.25-7.5 7.5-7.5-7.5" />
             </svg>
          </div>
        </div>
        
        <div v-show="showAiConfig" class="config-body">
           <div class="form-grid-config">
              <div class="form-group">
                 <label>API Base URL</label>
                 <SearchSelect
                   v-model="aiConfig.base_url"
                   :options="apiBaseUrls"
                   placeholder="输入或选择 API 地址..."
                 />
              </div>
              <div class="form-group">
                 <label>API Key</label>
                 <input v-model="aiConfig.api_key" type="password" class="input-modern" placeholder="sk-..." />
              </div>
              <div class="form-group full">
                 <label>Model Name</label>
                 <div class="model-row">
                   <SearchSelect
                     v-model="aiConfig.model"
                     :options="aiModels"
                     class="flex-1"
                     placeholder="选择或输入模型..."
                     :loading="aiModelsLoading"
                   />
                   <button class="btn btn-sm btn-secondary" @click="loadModels" :disabled="!aiConfig.base_url">
                     刷新模型
                   </button>
                   <button class="btn btn-sm btn-primary-gradient" @click="saveAiConfig">
                     保存配置
                   </button>
                 </div>
              </div>
           </div>
        </div>
      </div>

    </div>

    <!-- Dialogs -->

    <ConfirmDialog :is-open="showDeleteDialog" title="确认重置" message="确定要删除当前项目吗？数据不可恢复。" confirm-text="删除" type="danger" @confirm="handleDeleteConfirm" @cancel="showDeleteDialog = false" />
    
    <div v-if="showTitlesDialog" class="titles-dialog-overlay" @click.self="showTitlesDialog = false">
      <div class="titles-dialog premium-dialog">
        <h3>AI 灵感书名</h3>
        <div class="titles-grid">
           <div v-for="(t,i) in titleCandidates" :key="i" class="title-card" @click="selectTitle(t.title)">
              <div class="t-main">{{ t.title }}</div>
              <div class="t-sub">{{ t.reason }}</div>
           </div>
        </div>
      </div>
    </div>
    
    <!-- Toast -->
    <div v-if="message" class="toast-message">{{ message }}</div>

  </div>
</template>

<style scoped>
/* Core Layout */
.project-view {
  height: 100%; width: 100%;
  overflow-y: auto;
  background-color: #fafbfc;
  padding: 2rem;
}
.project-content { max-width: 900px; margin: 0 auto; padding-bottom: 4rem; }

/* Page Header */
.page-header { text-align: center; margin-bottom: 2.5rem; }
.page-title { font-size: 2rem; font-weight: 800; color: #111827; margin-bottom: 0.5rem; }
.page-subtitle { color: #6b7280; font-size: 1rem; }

/* Premium Card (Shared with Home) */
.premium-card {
  background: white; border-radius: 16px; padding: 1.5rem;
  box-shadow: 0 4px 6px -1px rgba(0,0,0,0.02), 0 2px 4px -1px rgba(0,0,0,0.02);
  border: 1px solid rgba(229,231,235,0.5);
  margin-bottom: 1.5rem;
}

/* Overview Card */
.card-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 1.5rem; }
.section-title { font-size: 1.125rem; font-weight: 700; color: #1f2937; display: flex; align-items: center; }
.title-actions { display: flex; align-items: center; gap: 0.75rem; }
.project-title-text { font-size: 1.25rem; font-weight: 700; color: #111827; }
.target-words-row {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 0.5rem;
  margin-bottom: 1rem;
}
.target-words-label {
  font-size: 0.85rem;
  color: #6b7280;
}
.target-words-display {
  display: flex;
  align-items: center;
  gap: 0.35rem;
}
.target-words-value {
  font-weight: 600;
  color: #6b5840;
  background: #faf8f4;
  padding: 0.2rem 0.5rem;
  border-radius: 999px;
  font-size: 0.85rem;
}
.target-words-input {
  width: 160px;
  border: none;
  border-bottom: 2px solid #6b5840;
  outline: none;
  font-size: 0.9rem;
  padding: 0.2rem 0.1rem;
}

/* Stats Row */
.stats-row { display: grid; grid-template-columns: repeat(4, 1fr); gap: 1rem; }
.stat-box { 
  display: flex; align-items: center; gap: 0.75rem;
  padding: 1rem; background: #f9fafb; border-radius: 12px;
  border: 1px solid #f3f4f6; transition: all 0.2s;
}
.stat-box:hover { transform: translateY(-2px); border-color: #e5e7eb; box-shadow: 0 4px 6px -1px rgba(0,0,0,0.05); }
.stat-icon-bg { 
  width: 2.5rem; height: 2.5rem; border-radius: 10px; 
  display: flex; align-items: center; justify-content: center; 
}
.stat-val { font-weight: 700; color: #111827; font-size: 1.1rem; line-height: 1.2; }
.stat-lab { font-size: 0.75rem; color: #9ca3af; }

/* Guide Section */
.guide-section { margin: 2.5rem 0; }
.guide-title { font-size: 1.125rem; font-weight: 700; color: #374151; margin-bottom: 1rem; display: flex; align-items: center; gap: 0.5rem; }
.guide-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 1.5rem; }
.guide-card {
  display: flex; align-items: center; gap: 1.25rem;
  padding: 1.5rem; border-radius: 16px; cursor: pointer;
  transition: all 0.3s ease; position: relative; overflow: hidden;
  border: 1px solid transparent;
}
.primary-guide { background: linear-gradient(135deg, #faf8f4 0%, #ffffff 100%); border-color: #f0ebe3; }
.secondary-guide { background: linear-gradient(135deg, #ecfdf5 0%, #ffffff 100%); border-color: #d1fae5; }
.guide-card:hover { transform: translateY(-4px) scale(1.02); box-shadow: 0 10px 20px -5px rgba(0,0,0,0.05); }

.guide-icon-wrapper { 
  width: 3.5rem; height: 3.5rem; border-radius: 12px;
  display: flex; align-items: center; justify-content: center;
  background: white; shadow: 0 2px 4px rgba(0,0,0,0.05);
}
.primary-guide .guide-icon-wrapper { color: #6b5840; }
.secondary-guide .guide-icon-wrapper { color: #059669; }

.guide-content h4 { font-size: 1.1rem; font-weight: 700; color: #111827; margin-bottom: 0.25rem; }
.guide-content p { font-size: 0.85rem; color: #6b7280; }
.guide-arrow { margin-left: auto; font-size: 1.5rem; opacity: 0.3; font-weight: 300; transition: transform 0.2s; }
.guide-card:hover .guide-arrow { transform: translateX(4px); opacity: 0.8; }

/* Synopsis */
.synopsis-content { 
  line-height: 1.8; color: #4b5563; font-size: 0.95rem; 
  background: #f9fafb; padding: 1.25rem; border-radius: 12px;
}

/* Init Form */
.init-card { background: white; border-radius: 20px; padding: 2.5rem; box-shadow: 0 20px 25px -5px rgba(0,0,0,0.1); }
.init-header { text-align: center; margin-bottom: 2rem; }
.init-header h2 { font-size: 1.75rem; font-weight: 800; color: #111827; }
.form-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 1.5rem; margin-bottom: 2rem; }
.form-group.full { grid-column: span 2; }
.input-modern { 
  width: 100%; padding: 0.75rem 1rem; border-radius: 10px; border: 1px solid #e5e7eb; 
  background: #f9fafb; transition: all 0.2s; font-size: 0.95rem;
}
.input-modern:focus { border-color: #8b7355; background: white; box-shadow: 0 0 0 3px rgba(139,115,85,0.1); outline: none; }
.input-modern.xl { font-size: 1.25rem; padding: 1rem; font-weight: 600; }
.textarea { min-height: 100px; resize: vertical; }

.btn-primary-gradient {
  background: linear-gradient(135deg, #6b5840 0%, #8b7355 100%); color: white; border: none;
  font-weight: 600; padding: 1rem; border-radius: 12px; cursor: pointer;
  transition: opacity 0.2s;
}
.btn-primary-gradient:hover { opacity: 0.9; }

/* Config Toggle (Removed) */

/* Config Card */
.config-card { margin-top: 2rem; border-color: #e5e7eb; box-shadow: none; background: #f9fafb; }
.config-card .card-header:hover { background: #f3f4f6; border-radius: 12px; margin: -0.5rem -0.5rem 0; padding: 0.5rem; }
.config-body { padding-top: 1.5rem; border-top: 1px solid #e5e7eb; margin-top: 1rem; animation: slideDown 0.3s ease-out; }
@keyframes slideDown { from { opacity: 0; transform: translateY(-10px); } to { opacity: 1; transform: translateY(0); } }

.header-actions { display: flex; align-items: center; gap: 1rem; }
.status-indicator { display: flex; align-items: center; gap: 6px; background: white; padding: 4px 10px; border-radius: 20px; border: 1px solid #e5e7eb; font-size: 0.8rem; color: #4b5563; }

/* Model Row Layout */
.model-row { display: flex; gap: 0.75rem; align-items: center; }

/* Enforce consistent height for inputs & buttons */
.model-row :deep(.input-container), 
.model-row .btn,
.form-grid-config .input-modern {
  height: 46px !important;
  box-sizing: border-box;
}

.model-row .btn { 
  white-space: nowrap; 
  flex-shrink: 0; 
  display: flex; 
  align-items: center; 
  justify-content: center; 
  padding: 0 1.25rem !important; /* Horizontal padding only */
  font-size: 0.9rem;
}

/* Ensure SearchSelect input doesn't break height */
.model-row :deep(.select-input) {
  height: 100%;
  padding-top: 0;
  padding-bottom: 0;
  display: flex;
  align-items: center;
}

.form-grid-config { display: grid; grid-template-columns: 1fr 1fr; gap: 1.5rem; align-items: end; }
.stagger-in { animation: slideUp 0.6s ease-out; }
.stagger-in-2 { animation: slideUp 0.6s ease-out 0.1s backwards; }
@keyframes slideUp { from { opacity: 0; transform: translateY(20px); } to { opacity: 1; transform: translateY(0); } }

/* Helpers */
.title-input-edit { font-size: 1.25rem; font-weight: 700; border: none; border-bottom: 2px solid #6b5840; outline: none; width: 200px; }
.btn-ai-gradient { background: linear-gradient(135deg, #8b5cf6, #d946ef); color: white; border: none; padding: 0.25rem 0.75rem; border-radius: 6px; font-size: 0.75rem; }
.danger-zone { margin-top: 3rem; text-align: center; opacity: 0.6; }
.danger-zone:hover { opacity: 1; }
.btn-danger-ghost { color: #ef4444; background: none; border: 1px dashed #ef4444; padding: 0.5rem 1rem; border-radius: 8px; cursor: pointer; }
.bg-blue-50 { background-color: #eff6ff; } .text-blue-600 { color: #2563eb; }
.bg-pink-50 { background-color: #fdf2f8; } .text-pink-600 { color: #db2777; }
.bg-orange-50 { background-color: #fff7ed; } .text-orange-600 { color: #ea580c; }
.bg-teal-50 { background-color: #f0fdfa; } .text-teal-600 { color: #0d9488; }
.toast-message { position: fixed; top: 20px; left: 50%; transform: translateX(-50%); background: #1f2937; color: white; padding: 0.75rem 1.5rem; border-radius: 99px; z-index: 200; }

/* Titles Dialog */
.titles-dialog-overlay {
  position: fixed;
  top: 0; left: 0; right: 0; bottom: 0;
  background: rgba(0,0,0,0.5);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 100;
  backdrop-filter: blur(4px);
}
.titles-dialog {
  background: white;
  width: 600px;
  max-width: 90vw;
  max-height: 80vh;
  border-radius: 16px;
  padding: 2rem;
  overflow-y: auto;
  box-shadow: 0 20px 25px -5px rgba(0,0,0,0.1);
}
.titles-dialog h3 {
  font-size: 1.5rem;
  margin-bottom: 1.5rem;
  font-weight: 700;
  color: #111827;
}
.titles-grid {
  display: grid;
  gap: 1rem;
}
.title-card {
  border: 1px solid #e5e7eb;
  padding: 1rem;
  border-radius: 8px;
  cursor: pointer;
  transition: all 0.2s;
}
.title-card:hover {
  border-color: #8b7355;
  background: #eff6ff;
  transform: translateY(-2px);
}
.t-main {
  font-size: 1.1rem;
  font-weight: 600;
  color: #1f2937;
  margin-bottom: 0.25rem;
}
.t-sub {
  font-size: 0.875rem;
  color: #6b7280;
}

/* Settings Cards */
.settings-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 1rem;
  margin-top: 1.5rem;
}
@media (max-width: 900px) {
  .target-words-row {
    justify-content: flex-start;
    margin-top: -0.5rem;
  }
  .target-words-input {
    width: 130px;
  }
  .settings-grid { grid-template-columns: 1fr; }
}
.setting-card {
  cursor: pointer;
  transition: box-shadow 0.2s, transform 0.2s;
}
.setting-card:hover {
  box-shadow: 0 4px 15px rgba(0,0,0,0.08);
  transform: translateY(-2px);
}
.setting-card .card-header {
  margin-bottom: 0;
}
.setting-status {
  font-size: 0.75rem;
  padding: 0.2rem 0.5rem;
  border-radius: 4px;
  margin-right: 0.5rem;
}
.setting-status.filled { background: #dcfce7; color: #16a34a; }
.setting-status.empty { background: #fef3c7; color: #d97706; }
.setting-content {
  padding: 1rem;
  background: #f9fafb;
  border-radius: 8px;
  margin-top: 0.75rem;
  max-height: 300px;
  overflow-y: auto;
}
.setting-content pre {
  white-space: pre-wrap;
  word-wrap: break-word;
  font-family: inherit;
  font-size: 0.875rem;
  color: #374151;
  margin: 0;
  line-height: 1.6;
}
</style>
