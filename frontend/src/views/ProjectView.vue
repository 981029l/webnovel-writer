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
import { copyText } from '../utils/clipboard'

const router = useRouter()
const projectStore = useProjectStore()
const aiTaskStore = useAiTaskStore()

// State
const genres = ref([])
const selectedGenre = ref('')
const selectedSubstyle = ref('')
const title = ref('')
const initTargetWords = ref('')
const protagonistName = ref('')
const goldenFingerName = ref('')
const goldenFingerType = ref('')
// 从 AI 共创页带过来的金手指设定（sessionStorage 交接）
const pendingGoldenFinger = ref('')
const pendingGfExpanded = ref(false)
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
  'https://api.openai.com', 'https://api.deepseek.com', 'https://api.moonshot.cn', 'https://api-inference.modelscope.cn/compatible-mode/v1',
  'https://api.x.ai/v1', 'https://generativelanguage.googleapis.com/v1beta/openai', 'http://localhost:8000', 'http://127.0.0.1:8317', 'http://localhost:8317'
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
const projectGenreDraft = ref('')
const projectSubstyleDraft = ref('')
const savingGenreProfile = ref(false)

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

function normalizeGenres(items = []) {
  return items.map(item => ({
    ...item,
    aliases: item.aliases || [],
    substyles: item.substyles || []
  }))
}

function findGenreOption(value) {
  if (!value) return null
  const raw = String(value).trim()
  return genres.value.find(g =>
    g.id === raw ||
    g.name === raw ||
    (g.aliases || []).includes(raw)
  ) || null
}

function pickSubstyleId(genreOption, preferred = '') {
  const options = genreOption?.substyles || []
  if (!options.length) return ''
  const raw = String(preferred || '').trim()
  const matched = options.find(s => s.id === raw || s.name === raw)
  return matched?.id || genreOption.default_substyle || options[0].id
}

function getAvailableSubstyles(genreId) {
  return findGenreOption(genreId)?.substyles || []
}

function syncInitGenreSelection(genreValue = '', substyleValue = '') {
  const matched = findGenreOption(genreValue) || genres.value[0] || null
  if (!matched) return
  selectedGenre.value = matched.id
  selectedSubstyle.value = pickSubstyleId(matched, substyleValue)
}

function syncProjectGenreDraft(genreValue = '', substyleValue = '') {
  const matched = findGenreOption(genreValue) || genres.value[0] || null
  if (!matched) return
  projectGenreDraft.value = matched.id
  projectSubstyleDraft.value = pickSubstyleId(matched, substyleValue)
}

function isGenreProfileDirty() {
  const matched = findGenreOption(projectStore.genre) || null
  const currentGenreId = matched?.id || projectStore.genre || ''
  const currentSubstyleId = pickSubstyleId(matched, projectStore.substyle)
  return projectGenreDraft.value !== currentGenreId || projectSubstyleDraft.value !== currentSubstyleId
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
  pendingGoldenFinger.value = sessionStorage.getItem('pendingGoldenFinger') || ''
  try {
    const { data } = await aiApi.getGenres()
    genres.value = normalizeGenres(data.genres || [])
    if (genres.value.length > 0) {
      selectedGenre.value = genres.value[0].id
      selectedSubstyle.value = pickSubstyleId(genres.value[0])
    }
  } catch (e) {
    genres.value = normalizeGenres([
      {
        id: '玄幻',
        name: '玄幻',
        default_substyle: '热血升级流',
        substyles: [{ id: '热血升级流', name: '热血升级流' }, { id: '凡人流', name: '凡人流' }]
      },
      {
        id: '规则怪谈',
        name: '规则怪谈',
        default_substyle: '规则生存流',
        substyles: [{ id: '规则生存流', name: '规则生存流' }]
      },
      {
        id: '现代言情',
        name: '现代言情',
        default_substyle: '高甜拉扯',
        substyles: [{ id: '高甜拉扯', name: '高甜拉扯' }]
      }
    ])
    selectedGenre.value = genres.value[0].id
    selectedSubstyle.value = pickSubstyleId(genres.value[0])
  }
  await loadAiConfig()
  await projectStore.fetchStatus()
  
  // Load settings if project is initialized
  if (projectStore.initialized) {
    await loadSettings()
  }
  
  // Sync inputs with stored data
  if (projectStore.title && !title.value) title.value = projectStore.title
  syncInitGenreSelection(projectStore.genre, projectStore.substyle)
  syncProjectGenreDraft(projectStore.genre, projectStore.substyle)
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
  if (!newVal) return
  if (!projectStore.initialized) syncInitGenreSelection(newVal, projectStore.substyle)
  syncProjectGenreDraft(newVal, projectStore.substyle)
})
watch(() => projectStore.substyle, (newVal) => {
  if (!projectStore.initialized) {
    syncInitGenreSelection(projectStore.genre, newVal)
    return
  }
  syncProjectGenreDraft(projectStore.genre, newVal)
})
watch(() => projectStore.targetWords, (newVal) => {
  if (newVal && !projectStore.initialized && !initTargetWords.value) {
    initTargetWords.value = String(newVal)
  }
})
watch(selectedGenre, (newVal) => {
  const matched = findGenreOption(newVal)
  if (matched) selectedSubstyle.value = pickSubstyleId(matched, selectedSubstyle.value)
})
watch(projectGenreDraft, (newVal) => {
  const matched = findGenreOption(newVal)
  if (matched) projectSubstyleDraft.value = pickSubstyleId(matched, projectSubstyleDraft.value)
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
      substyle: selectedSubstyle.value,
      protagonist_name: protagonistName.value,
      golden_finger_name: goldenFingerName.value,
      golden_finger_type: goldenFingerType.value,
      golden_finger_design: pendingGoldenFinger.value,
      additional_info: additionalInfo.value,
      mode: 'standard'
    }
    if (parsedTargetWords) payload.target_words = parsedTargetWords

    await aiApi.updateProjectInfo({
      title: title.value,
      genre: selectedGenre.value,
      substyle: selectedSubstyle.value,
      ...(parsedTargetWords ? { target_words: parsedTargetWords } : {})
    })
    await projectStore.fetchStatus()

    await aiTaskStore.initProjectAction({
      ...payload
    }, aiApi)
    // Stream finished — refresh project status
    await projectStore.fetchStatus()
    // 金手指已写入设定集，清理交接数据
    sessionStorage.removeItem('pendingGoldenFinger')
    pendingGoldenFinger.value = ''
  } catch (e) {
    stopWatch()
    showMessage('初始化失败：' + e.message)
  } finally {
    loading.value = false
  }
}

async function saveGenreProfile() {
  if (!projectStore.initialized || !isGenreProfileDirty()) return
  savingGenreProfile.value = true
  try {
    const { data } = await aiApi.updateProjectInfo({
      genre: projectGenreDraft.value,
      substyle: projectSubstyleDraft.value
    })
    await projectStore.fetchStatus()
    syncProjectGenreDraft(projectStore.genre, projectStore.substyle)
    const preservedSlots = data?.preserved_custom_prompt_slots || []
    if (projectStore.outlineInvalidated && preservedSlots.length) {
      showMessage('✓ 题材方向已更新；已保留你的自定义题材提示词，请同步检查总纲与提示词配置')
    } else if (projectStore.outlineInvalidated) {
      showMessage('✓ 题材方向已更新，请先重生成总纲/卷纲')
    } else if (preservedSlots.length) {
      showMessage('✓ 题材方向已更新；已保留你的自定义题材提示词')
    } else {
      showMessage('✓ 题材方向已更新')
    }
  } catch (e) {
    showMessage('✗ 题材方向更新失败')
  } finally {
    savingGenreProfile.value = false
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
    await copyText(projectStore.description)
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
  showMessage('正在重建索引，请稍候...')
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
      <div class="page-header">
        <h1 class="page-title">项目管理</h1>
        <p class="page-subtitle">AI 驱动的创作中枢，一键初始化与设定生成</p>
      </div>

      <!-- Initialized View -->
      <div v-if="projectStore.initialized" class="project-dashboard">
        
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
              <button class="btn btn-xs btn-ai" @click="generateTitlesAI" :disabled="generatingTitles">
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
                <div class="stat-icon-bg">
                  <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor" class="size-6"><path stroke-linecap="round" stroke-linejoin="round" d="M12 6.042A8.967 8.967 0 0 0 6 3.75c-1.052 0-2.062.18-3 .512v14.25A8.987 8.987 0 0 1 6 18c2.305 0 4.408.867 6 2.292m0-14.25a8.966 8.966 0 0 1 6-2.292c1.052 0 2.062.18 3 .512v14.25A8.987 8.987 0 0 0 18 18a8.967 8.967 0 0 0-6 2.292m0-14.25v14.25" /></svg>
                </div>
                <div class="stat-info">
                  <div class="stat-val">{{ projectStore.totalChapters }}</div>
                  <div class="stat-lab">章节</div>
                </div>
             </div>
             
             <div class="stat-box">
                <div class="stat-icon-bg">
                  <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor" class="size-6"><path stroke-linecap="round" stroke-linejoin="round" d="M3.75 6.75h16.5M3.75 12H12m-8.25 5.25h16.5" /></svg>
                </div>
                <div class="stat-info">
                  <div class="stat-val">{{ (projectStore.totalWords / 10000).toFixed(1) }}w</div>
                  <div class="stat-lab">字数</div>
                </div>
             </div>

             <div class="stat-box">
                <div class="stat-icon-bg">
                  <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor" class="size-6"><path stroke-linecap="round" stroke-linejoin="round" d="M9.568 3H5.25A2.25 2.25 0 0 0 3 5.25v4.318c0 .597.237 1.17.659 1.591l9.581 9.581c.699.699 1.78.872 2.607.33a18.095 18.095 0 0 0 5.223-5.223c.542-.827.369-1.908-.33-2.607L11.16 3.66A2.25 2.25 0 0 0 9.568 3Z" /></svg>
                </div>
                <div class="stat-info">
                  <div class="stat-val text-sm">{{ projectStore.substyle ? `${projectStore.genre} · ${projectStore.substyle}` : (projectStore.genre || '未设定') }}</div>
                  <div class="stat-lab">题材</div>
                </div>
             </div>

             <div class="stat-box">
                <div class="stat-icon-bg">
                  <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor" class="size-6"><path stroke-linecap="round" stroke-linejoin="round" d="M11.25 11.25l.041-.02a.75.75 0 0 1 1.063.852l-.708 2.836a.75.75 0 0 0 1.063.853l.041-.021M21 12a9 9 0 1 1-18 0 9 9 0 0 1 18 0Zm-9-3.75h.008v.008H12V8.25Z" /></svg>
                </div>
                <div class="stat-info">
                  <div class="stat-val text-sm">{{ projectStore.status || '连载中' }}</div>
                  <div class="stat-lab">状态</div>
                </div>
             </div>
          </div>

          <div v-if="projectStore.outlineInvalidated" class="outline-warning-banner">
            <div class="warning-title">题材方向已变更</div>
            <div class="warning-body">{{ projectStore.outlineInvalidationReason || '现有总纲与卷纲仍基于旧方向，请先重新生成总纲/卷纲。' }}</div>
          </div>

          <div class="genre-profile-card">
            <div class="genre-profile-head">
              <div>
                <h3>题材方向</h3>
                <p>题材与子风格会同时约束总纲、分卷和正文。</p>
              </div>
              <button
                class="btn btn-sm btn-primary-gradient"
                @click="saveGenreProfile"
                :disabled="savingGenreProfile || !isGenreProfileDirty()"
              >
                {{ savingGenreProfile ? '保存中...' : '保存题材方向' }}
              </button>
            </div>
            <div class="form-grid genre-profile-grid">
              <div class="form-group">
                <label>主题材</label>
                <select v-model="projectGenreDraft" class="input-modern">
                  <option v-for="g in genres" :key="g.id" :value="g.id">{{ g.name }}</option>
                </select>
              </div>
              <div class="form-group">
                <label>子风格</label>
                <select v-model="projectSubstyleDraft" class="input-modern">
                  <option v-for="s in getAvailableSubstyles(projectGenreDraft)" :key="s.id" :value="s.id">
                    {{ s.name }}
                  </option>
                </select>
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
      <div v-if="!projectStore.initialized" class="card init-card">
        <div class="init-header">
          <h2>开始新的旅程</h2>
          <p>AI 将为你构建完整的世界观、角色与故事总纲</p>
        </div>

        <!-- AI 共创带来的金手指设定（只读摘要） -->
        <div v-if="pendingGoldenFinger" class="gf-pending-card">
          <div class="gf-pending-head">
            <span class="gf-pending-title">
              <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor" class="size-4">
                <path stroke-linecap="round" stroke-linejoin="round" d="M9.813 15.904 9 18.75l-.813-2.846a4.5 4.5 0 0 0-3.09-3.09L2.25 12l2.846-.813a4.5 4.5 0 0 0 3.09-3.09L9 5.25l.813 2.846a4.5 4.5 0 0 0 3.09 3.09L15.75 12l-2.846.813a4.5 4.5 0 0 0-3.09 3.09Z" />
              </svg>
              已带入 AI 共创的金手指设定
            </span>
            <button class="gf-pending-toggle" @click="pendingGfExpanded = !pendingGfExpanded">
              {{ pendingGfExpanded ? '收起' : '查看全文' }}
            </button>
          </div>
          <div class="gf-pending-body" :class="{ expanded: pendingGfExpanded }">{{ pendingGoldenFinger }}</div>
          <p class="gf-pending-hint">初始化时会作为核心设定交给 AI，无需重复填写</p>
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
              <label>子风格</label>
              <select v-model="selectedSubstyle" class="input-modern">
                 <option v-for="s in getAvailableSubstyles(selectedGenre)" :key="s.id" :value="s.id">
                   {{ s.name }}
                 </option>
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
              {{ loading ? '正在构建世界...' : 'AI 一键初始化' }}
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
/* Core Layout — 白纸内容页 */
.project-view {
  height: 100%; width: 100%;
  overflow-y: auto;
  padding: 2rem;
}
.project-content { max-width: 900px; margin: 0 auto; padding-bottom: 4rem; }

/* Page Header */
.page-header { margin-bottom: 2rem; }
.page-title {
  font-size: 1.375rem;
  font-weight: 600;
  color: var(--ink-primary);
  margin-bottom: 0.375rem;
  letter-spacing: -0.01em;
}
.page-subtitle { color: var(--ink-secondary); font-size: 0.9375rem; font-weight: 400; }

/* Panel Card */
.premium-card {
  background: var(--card);
  border-radius: var(--radius-lg);
  padding: 1.25rem;
  border: 1px solid var(--border);
  box-shadow: none;
  margin-bottom: 0.875rem;
}

/* Overview Card */
.card-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 1.25rem; }
.section-title {
  font-size: 1rem;
  font-weight: 600;
  color: var(--ink-primary);
  display: flex;
  align-items: center;
}
.title-actions { display: flex; align-items: center; gap: 0.75rem; }
.project-title-text { font-size: 1.125rem; font-weight: 600; color: var(--ink-primary); }
.target-words-row {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 0.5rem;
  margin-bottom: 1rem;
}
.target-words-label {
  font-size: 0.8125rem;
  color: var(--ink-secondary);
  font-weight: 400;
}
.target-words-display {
  display: flex;
  align-items: center;
  gap: 0.35rem;
}
.target-words-value {
  font-family: var(--font-mono);
  font-feature-settings: "tnum";
  font-weight: 500;
  color: var(--primary-on-tint);
  background: var(--primary-tint);
  padding: 0.2rem 0.5rem;
  border-radius: var(--radius-sm);
  font-size: 0.8125rem;
}
.target-words-input {
  width: 160px;
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  outline: none;
  font-size: 0.875rem;
  padding: 0.25rem 0.5rem;
  background: var(--surface);
  color: var(--ink-primary);
  font-family: var(--font-mono);
  font-feature-settings: "tnum";
}
.target-words-input:focus { border-color: var(--primary); background: var(--card); }

/* Stats Row */
.stats-row { display: grid; grid-template-columns: repeat(4, 1fr); gap: 0.75rem; }
.stat-box {
  display: flex; align-items: center; gap: 0.75rem;
  padding: 0.875rem 1rem; background: var(--surface); border-radius: var(--radius-md);
  border: 1px solid transparent;
}
.stat-icon-bg {
  width: 2.25rem; height: 2.25rem; border-radius: var(--radius-md);
  display: flex; align-items: center; justify-content: center;
  background: var(--card);
  border: 1px solid var(--border);
  color: var(--ink-secondary);
  flex-shrink: 0;
}
.stat-val { font-family: var(--font-mono); font-feature-settings: "tnum"; font-weight: 600; color: var(--ink-primary); font-size: 1.0625rem; line-height: 1.2; }
.stat-lab { font-size: 0.75rem; color: var(--ink-muted); font-weight: 400; }
.outline-warning-banner {
  margin-top: 1rem;
  padding: 0.875rem 1rem;
  border-radius: var(--radius-md);
  background: var(--warning-tint);
  border: 1px solid transparent;
}
.warning-title {
  font-size: 0.875rem;
  font-weight: 600;
  color: var(--warning-strong);
  margin-bottom: 0.25rem;
}
.warning-body {
  font-size: 0.8125rem;
  line-height: 1.6;
  color: var(--warning-strong);
  font-weight: 400;
}
.genre-profile-card {
  margin-top: 1rem;
  padding: 1rem;
  border-radius: var(--radius-md);
  background: var(--surface);
}
.genre-profile-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 1rem;
  margin-bottom: 1rem;
}
.genre-profile-head h3 {
  margin: 0 0 0.25rem;
  font-size: 0.9375rem;
  font-weight: 600;
  color: var(--ink-primary);
}
.genre-profile-head p {
  margin: 0;
  font-size: 0.8125rem;
  color: var(--ink-secondary);
  font-weight: 400;
}
.genre-profile-grid {
  margin-bottom: 0;
}

/* Guide Section */
.guide-section { margin: 1.5rem 0; }
.guide-title {
  font-size: 1rem;
  font-weight: 600;
  color: var(--ink-primary);
  margin-bottom: 0.875rem;
  display: flex;
  align-items: center;
  gap: 0.5rem;
}
.guide-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 0.875rem; }
.guide-card {
  display: flex; align-items: center; gap: 1rem;
  padding: 1.1rem 1.25rem; border-radius: var(--radius-lg); cursor: pointer;
  transition: border-color var(--dur-fast) var(--ease-standard), background-color var(--dur-fast) var(--ease-standard);
  position: relative; overflow: hidden;
  border: 1px solid var(--border);
}
.primary-guide { background: var(--primary-tint); border-color: transparent; }
.secondary-guide { background: var(--success-tint); border-color: transparent; }
.guide-card:hover { border-color: var(--border-strong); }

.guide-icon-wrapper {
  width: 3rem; height: 3rem; border-radius: var(--radius-md);
  display: flex; align-items: center; justify-content: center;
  background: var(--card);
  flex-shrink: 0;
}
.primary-guide .guide-icon-wrapper { color: var(--primary-text); }
.secondary-guide .guide-icon-wrapper { color: var(--success); }

.guide-content h4 { font-size: 1rem; font-weight: 600; color: var(--ink-primary); margin-bottom: 0.25rem; }
.guide-content p { font-size: 0.8125rem; color: var(--ink-secondary); font-weight: 400; }
.guide-arrow { margin-left: auto; font-size: 1.25rem; opacity: 0.35; font-weight: 400; transition: transform var(--dur-fast) var(--ease-standard), opacity var(--dur-fast) var(--ease-standard); color: var(--ink-secondary); }
.guide-card:hover .guide-arrow { transform: translateX(3px); opacity: 0.8; }

/* Synopsis */
.synopsis-content {
  line-height: 1.8; color: var(--ink-secondary); font-size: 0.9375rem;
  background: var(--surface); padding: 1.1rem; border-radius: var(--radius-md);
  font-weight: 400;
}

/* Init Form */
.init-card { background: var(--card); border: 1px solid var(--border); border-radius: var(--radius-lg); padding: 2rem; }
.init-header { margin-bottom: 1.75rem; }
.init-header h2 {
  font-size: 1.375rem;
  font-weight: 600;
  color: var(--ink-primary);
  letter-spacing: -0.01em;
}
.form-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 1.25rem; margin-bottom: 1.75rem; }
.form-group.full { grid-column: span 2; }
.input-modern {
  width: 100%; padding: 0.6rem 0.85rem; border-radius: var(--radius-md); border: 1px solid var(--border);
  background: var(--surface); transition: border-color var(--dur-fast) var(--ease-standard), background-color var(--dur-fast) var(--ease-standard), box-shadow var(--dur-fast) var(--ease-standard); font-size: 0.9375rem;
  color: var(--ink-primary); font-weight: 400;
}
.input-modern:focus { border-color: var(--primary); background: var(--card); box-shadow: 0 0 0 3px var(--primary-tint); outline: none; }
.input-modern.xl { font-size: 1.125rem; padding: 0.8rem 1rem; font-weight: 500; }
.textarea { min-height: 100px; resize: vertical; line-height: 1.6; }

.btn-primary-gradient {
  background: var(--primary);
  color: var(--on-primary); border: 1px solid var(--primary);
  font-weight: 500; padding: 0.75rem 1.25rem; border-radius: var(--radius-md); cursor: pointer;
  font-size: 0.9375rem;
  transition: background-color var(--dur-fast) var(--ease-standard), border-color var(--dur-fast) var(--ease-standard);
}
.btn-primary-gradient:hover {
  background: var(--primary-hover);
  border-color: var(--primary-hover);
}
.btn-primary-gradient:disabled { opacity: 0.5; cursor: not-allowed; }

/* Config Card */
.config-card { margin-top: 1.5rem; border-color: var(--border); box-shadow: none; background: var(--surface); }
.config-card .card-header:hover { background: var(--hover); border-radius: var(--radius-md); margin: -0.5rem -0.5rem 0; padding: 0.5rem; }
.config-body { padding-top: 1.25rem; border-top: 1px solid var(--border); margin-top: 1rem; }

.header-actions { display: flex; align-items: center; gap: 1rem; }
.status-indicator { display: flex; align-items: center; gap: 6px; background: var(--card); padding: 4px 10px; border-radius: var(--radius-sm); border: 1px solid var(--border); font-size: 0.75rem; color: var(--ink-secondary); }

/* Model Row Layout */
.model-row { display: flex; gap: 0.75rem; align-items: center; }

.model-row :deep(.input-container),
.model-row .btn,
.form-grid-config .input-modern {
  height: 42px !important;
  box-sizing: border-box;
}

.model-row .btn {
  white-space: nowrap;
  flex-shrink: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 0 1.25rem !important;
  font-size: 0.875rem;
}

.model-row :deep(.select-input) {
  height: 100%;
  padding-top: 0;
  padding-bottom: 0;
  display: flex;
  align-items: center;
}

.form-grid-config { display: grid; grid-template-columns: 1fr 1fr; gap: 1.25rem; align-items: end; }

/* ── 模板中 Tailwind 风格类名的本地实现(项目未装 Tailwind,这些类此前完全无效) ── */
.transition-transform { transition: transform var(--dur-fast) var(--ease-standard); }
.rotate-180 { transform: rotate(180deg); }
.animate-spin { animation: pvSpin 1s linear infinite; }
@keyframes pvSpin { to { transform: rotate(360deg); } }
@media (prefers-reduced-motion: reduce) {
  .animate-spin { animation: none; }
}
.text-sm { font-size: 0.875rem !important; }
.full-width { width: 100%; }

.status-indicator .dot { width: 7px; height: 7px; border-radius: 50%; flex-shrink: 0; }
.bg-green-500 { background: var(--success); }
.bg-red-500 { background: var(--danger); }

/* 行内小图标按钮(编辑标题/编辑目标字数) */
.title-display { display: inline-flex; align-items: center; gap: 0.375rem; min-width: 0; }
.btn-icon-hover {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 26px; height: 26px;
  background: transparent;
  border: none;
  border-radius: var(--radius-sm);
  color: var(--ink-muted);
  cursor: pointer;
  opacity: 0;
  transition: opacity var(--dur-fast) var(--ease-standard), color var(--dur-fast) var(--ease-standard), background-color var(--dur-fast) var(--ease-standard);
}
.title-display:hover .btn-icon-hover,
.target-words-display:hover .btn-icon-hover,
.btn-icon-hover:focus-visible { opacity: 1; }
.btn-icon-hover:hover { color: var(--ink-primary); background: var(--hover); }

.stat-info { display: flex; flex-direction: column; min-width: 0; }

.init-actions { margin-top: 0.5rem; }

/* Helpers */
.title-input-edit { font-size: 1.125rem; font-weight: 600; border: 1px solid var(--border); border-radius: var(--radius-sm); padding: 0.25rem 0.5rem; outline: none; width: 220px; background: var(--surface); color: var(--ink-primary); }
.title-input-edit:focus { border-color: var(--primary); background: var(--card); }
.danger-zone { margin-top: 3rem; text-align: center; opacity: 0.65; }
.danger-zone:hover { opacity: 1; }
.btn-danger-ghost { color: var(--danger); background: none; border: 1px dashed var(--danger); padding: 0.5rem 1rem; border-radius: var(--radius-md); cursor: pointer; font-size: 0.875rem; }
.btn-danger-ghost:hover { background: var(--danger-tint); }
.toast-message { position: fixed; top: 20px; left: 50%; transform: translateX(-50%); background: var(--ink-primary); color: var(--bg); padding: 0.625rem 1.25rem; border-radius: var(--radius-md); z-index: var(--z-toast); font-size: 0.875rem; box-shadow: var(--shadow-lg); }

/* Titles Dialog */
.titles-dialog-overlay {
  position: fixed;
  top: 0; left: 0; right: 0; bottom: 0;
  background: rgb(15 17 21 / 0.45);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: var(--z-modal-backdrop);
}
.titles-dialog {
  background: var(--card);
  border: 1px solid var(--border);
  width: 600px;
  max-width: 90vw;
  max-height: 80vh;
  border-radius: var(--radius-lg);
  padding: 1.5rem;
  overflow-y: auto;
  box-shadow: var(--shadow-xl);
}
.titles-dialog h3 {
  font-size: 1.125rem;
  margin-bottom: 1.25rem;
  font-weight: 600;
  color: var(--ink-primary);
}
.titles-grid {
  display: grid;
  gap: 0.75rem;
}
.title-card {
  border: 1px solid var(--border);
  padding: 0.875rem 1rem;
  border-radius: var(--radius-md);
  cursor: pointer;
  transition: border-color var(--dur-fast) var(--ease-standard), background-color var(--dur-fast) var(--ease-standard);
}
.title-card:hover {
  border-color: var(--primary);
  background: var(--primary-tint);
}
.t-main {
  font-size: 1rem;
  font-weight: 500;
  color: var(--ink-primary);
  margin-bottom: 0.25rem;
}
.t-sub {
  font-size: 0.8125rem;
  color: var(--ink-secondary);
  font-weight: 400;
}

/* Settings Cards */
.settings-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 0.875rem;
  margin-top: 1.25rem;
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
  .genre-profile-head {
    flex-direction: column;
    align-items: stretch;
  }
}
.setting-card {
  cursor: pointer;
  transition: border-color var(--dur-fast) var(--ease-standard), box-shadow var(--dur-fast) var(--ease-standard);
}
.setting-card:hover {
  border-color: var(--border-strong);
  box-shadow: var(--shadow-md);
}
.setting-card .card-header {
  margin-bottom: 0;
}
.setting-status {
  font-size: 0.75rem;
  padding: 0.2rem 0.5rem;
  border-radius: var(--radius-sm);
  margin-right: 0.5rem;
  font-weight: 500;
}
.setting-status.filled { background: var(--success-tint); color: var(--success); }
.setting-status.empty { background: var(--warning-tint); color: var(--warning-strong); }
.setting-content {
  padding: 1rem;
  background: var(--surface);
  border-radius: var(--radius-md);
  margin-top: 0.75rem;
  max-height: 300px;
  overflow-y: auto;
}
.setting-content pre {
  white-space: pre-wrap;
  word-wrap: break-word;
  font-family: inherit;
  font-size: 0.875rem;
  color: var(--ink-primary);
  margin: 0;
  line-height: 1.6;
  font-weight: 400;
}

/* AI 共创金手指只读摘要卡 */
.gf-pending-card {
  margin-bottom: 1.25rem;
  padding: 1rem 1.25rem;
  background: var(--primary-tint);
  border: 1px solid transparent;
  border-radius: var(--radius-md);
}

.gf-pending-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 1rem;
}

.gf-pending-title {
  display: inline-flex;
  align-items: center;
  gap: 0.5rem;
  font-size: 0.875rem;
  font-weight: 600;
  color: var(--primary-on-tint);
}

.gf-pending-title svg {
  width: 1rem;
  height: 1rem;
  flex-shrink: 0;
}

.gf-pending-toggle {
  background: none;
  border: none;
  color: var(--primary-text);
  font-size: 0.8125rem;
  font-weight: 500;
  cursor: pointer;
  padding: 0.25rem 0.5rem;
  border-radius: var(--radius-sm);
  flex-shrink: 0;
}

.gf-pending-toggle:hover {
  background: var(--hover);
}

.gf-pending-body {
  margin-top: 0.625rem;
  font-size: 0.875rem;
  line-height: 1.7;
  color: var(--ink-primary);
  white-space: pre-wrap;
  word-break: break-word;
  max-height: 4.5rem;
  overflow: hidden;
  position: relative;
}

.gf-pending-body:not(.expanded)::after {
  content: '';
  position: absolute;
  left: 0;
  right: 0;
  bottom: 0;
  height: 2rem;
  background: linear-gradient(transparent, var(--primary-tint));
}

.gf-pending-body.expanded {
  max-height: 20rem;
  overflow-y: auto;
}

.gf-pending-hint {
  margin: 0.625rem 0 0;
  font-size: 0.75rem;
  color: var(--ink-muted);
}
</style>
