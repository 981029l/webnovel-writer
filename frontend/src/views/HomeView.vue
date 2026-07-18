<!-- Copyright (c) 2026 左岚. All rights reserved. -->
<!-- HomeView.vue - 项目总览（第一层） -->
<script setup>
import { computed, ref, onMounted, watch } from 'vue'
import { useRouter } from 'vue-router'
import { projectsApi, aiApi } from '../api'
import { useProjectStore } from '../stores/project'
import ConfirmDialog from '../components/ConfirmDialog.vue'
import AiConfigModal from '../components/AiConfigModal.vue'
import { useAiTaskStore } from '../stores/aiTask'
import { useToast } from '../composables/useToast'
import { useTheme } from '../composables/useTheme'
import { Sun, Moon, Settings2, Import, Sparkles, Plus, Trash2, TriangleAlert, BookOpen, NotebookPen } from 'lucide-vue-next'

const router = useRouter()
const projectStore = useProjectStore()
const aiTaskStore = useAiTaskStore()
const toast = useToast()
const { theme, toggle: toggleTheme } = useTheme()

const projects = ref([])
const loading = ref(false)
const error = ref(null)

// Genre list from API
const genres = ref([])

// Create modal (quick create only)
const showCreateModal = ref(false)
const newProject = ref({ name: '', path: '', genre: '', substyle: '' })
const showAdvancedPath = ref(false)
const creating = ref(false)

// Import modal
const showImportModal = ref(false)
const importPath = ref('')
const importing = ref(false)

// Delete confirm
const showDeleteDialog = ref(false)
const deleteTarget = ref(null)
const deleting = ref(false)

// AI config modal
const showAiConfigModal = ref(false)

onMounted(() => {
  loadProjects()
  loadGenres()
})

async function loadGenres() {
  try {
    const { data } = await aiApi.getGenres()
    genres.value = normalizeGenres(data.genres || [])
  } catch (e) {
    console.warn('加载题材列表失败，使用默认', e)
    genres.value = normalizeGenres([
      { id: '玄幻', name: '玄幻', default_substyle: '热血升级流', substyles: [{ id: '热血升级流', name: '热血升级流' }] },
      { id: '规则怪谈', name: '规则怪谈', default_substyle: '规则生存流', substyles: [{ id: '规则生存流', name: '规则生存流' }] },
      { id: '现代言情', name: '现代言情', default_substyle: '高甜拉扯', substyles: [{ id: '高甜拉扯', name: '高甜拉扯' }] }
    ])
  }
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

const availableCreateSubstyles = computed(() => {
  return findGenreOption(newProject.value.genre)?.substyles || []
})

async function loadProjects() {
  loading.value = true
  error.value = null
  try {
    const { data } = await projectsApi.list()
    projects.value = data.projects || []
  } catch (e) {
    console.error('加载项目列表失败', e)
    error.value = e.message || '未知错误'
  } finally {
    loading.value = false
  }
}

async function openProject(project) {
  await projectStore.setCurrentProject(project.path)
  router.push('/workspace/dashboard')
}

function openCreateModal() {
  const defaultGenre = genres.value[0] || null
  newProject.value = {
    name: '',
    path: '',
    genre: defaultGenre?.id || '玄幻',
    substyle: pickSubstyleId(defaultGenre)
  }
  showAdvancedPath.value = false
  showCreateModal.value = true
}

function goToCoCreate() {
  router.push('/create')
}

function updateDefaultPath() {
  if (newProject.value.name) {
    newProject.value.path = `./data/${newProject.value.name}`
  }
}

async function createProject() {
  if (!newProject.value.name) return
  // Auto-generate path if not manually set
  if (!newProject.value.path) {
    newProject.value.path = `./data/${newProject.value.name}`
  }
  creating.value = true
  try {
    const { data } = await projectsApi.create(newProject.value)
    // Use backend-resolved absolute path instead of the relative input
    const resolvedPath = data.project?.path || newProject.value.path
    await projectStore.setCurrentProject(resolvedPath)
    showCreateModal.value = false
    router.push('/workspace/project')
  } catch (e) {
    toast.error('创建项目失败：' + (e.response?.data?.detail || e.message))
  } finally {
    creating.value = false
  }
}

watch(() => newProject.value.genre, (newVal) => {
  const matched = findGenreOption(newVal)
  newProject.value.substyle = pickSubstyleId(matched, newProject.value.substyle)
})

async function importProject() {
  if (!importPath.value) return
  importing.value = true
  try {
    const { data } = await projectsApi.import(importPath.value)
    const resolvedPath = data.project?.path || importPath.value
    await projectStore.setCurrentProject(resolvedPath)
    showImportModal.value = false
    router.push('/workspace/project')
  } catch (e) {
    toast.error('导入项目失败：' + (e.response?.data?.detail || e.message))
  } finally {
    importing.value = false
  }
}

function confirmDelete(project) {
  deleteTarget.value = project
  showDeleteDialog.value = true
}

async function doDelete() {
  if (!deleteTarget.value) return
  deleting.value = true
  try {
    await projectsApi.delete(deleteTarget.value.id, true)
    showDeleteDialog.value = false
    deleteTarget.value = null
    await loadProjects()
  } catch (e) {
    toast.error('删除失败：' + (e.response?.data?.detail || e.message))
  } finally {
    deleting.value = false
  }
}

function formatDate(ts) {
  if (!ts) return '--'
  const d = new Date(typeof ts === 'number' ? ts * 1000 : ts)
  return d.toLocaleDateString('zh-CN', { month: 'short', day: 'numeric' })
}

</script>

<template>
  <div class="home-page">
    <!-- Top bar -->
    <header class="top-bar">
      <div class="top-bar-left">
        <span class="logo-mark">
          <NotebookPen :size="16" :stroke-width="2" />
        </span>
        <div class="logo-text-wrap">
          <span class="logo-text">网文创作台</span>
          <span class="logo-sub">Webnovel Writer</span>
        </div>
      </div>
      <div class="top-bar-right">
        <button class="icon-btn" @click="toggleTheme" :title="theme === 'dark' ? '切换到日间模式' : '切换到夜间模式'" :aria-label="theme === 'dark' ? '切换到日间模式' : '切换到夜间模式'">
          <Sun v-if="theme === 'dark'" :size="18" :stroke-width="1.75" />
          <Moon v-else :size="18" :stroke-width="1.75" />
        </button>
        <button class="btn btn-secondary btn-sm" @click="showAiConfigModal = true" title="AI 服务配置">
          <Settings2 :size="16" :stroke-width="1.75" />
          <span>AI 配置</span>
        </button>
      </div>
    </header>

    <!-- Main content -->
    <div class="home-content">
      <!-- Title row -->
      <div class="title-row">
        <div class="title-block">
          <h1 class="page-title">我的作品</h1>
          <span v-if="projects.length" class="title-count tnum">{{ projects.length }} 个项目</span>
        </div>
        <div class="title-actions">
          <button class="btn btn-secondary" @click="showImportModal = true">
            <Import :size="16" :stroke-width="1.75" />
            导入项目
          </button>
          <button class="btn btn-secondary" @click="goToCoCreate">
            <Sparkles :size="16" :stroke-width="1.75" />
            AI 共创
          </button>
          <button class="btn btn-primary" @click="openCreateModal">
            <Plus :size="16" :stroke-width="2" />
            快速创建
          </button>
        </div>
      </div>

      <!-- Loading -->
      <div v-if="loading && projects.length === 0" class="loading-state">
        <div class="spinner"></div>
        <p>加载项目列表...</p>
      </div>

      <!-- Error -->
      <div v-else-if="error" class="error-state">
        <TriangleAlert class="state-icon" :size="40" :stroke-width="1.25" />
        <p>加载失败: {{ error }}</p>
        <button class="btn btn-secondary" @click="loadProjects">重试</button>
      </div>

      <!-- Empty -->
      <div v-else-if="projects.length === 0" class="empty-state">
        <BookOpen class="state-icon" :size="44" :stroke-width="1.25" />
        <h3>还没有任何作品</h3>
        <p>新建或导入一个项目，开始创作</p>
        <button class="btn btn-primary" @click="goToCoCreate">
          <Sparkles :size="16" :stroke-width="1.75" />
          开始创作
        </button>
      </div>

      <!-- Project Cards Grid -->
      <div v-else class="projects-grid">
        <div
          v-for="project in projects"
          :key="project.id"
          class="project-card"
          :class="{ missing: !project.exists }"
          @click="project.exists !== false && openProject(project)"
        >
          <div class="card-top">
            <span class="card-mark">{{ (project.genre || '文')[0] }}</span>
            <span class="card-genre-tag">{{ project.genre || '未分类' }}</span>
            <button class="card-delete-btn" @click.stop="confirmDelete(project)" title="删除项目" aria-label="删除项目">
              <Trash2 :size="15" :stroke-width="1.75" />
            </button>
          </div>
          <h3 class="card-title">{{ project.name }}</h3>
          <div class="card-meta">
            <div class="meta-item">
              <span class="meta-num tnum">{{ project.total_chapters || 0 }}</span>
              <span class="meta-unit">章</span>
            </div>
            <span class="meta-sep">/</span>
            <div class="meta-item">
              <span class="meta-num tnum">{{ project.total_words ? (project.total_words / 10000).toFixed(1) : '0' }}</span>
              <span class="meta-unit">{{ project.total_words ? '万字' : '字' }}</span>
            </div>
            <span class="card-date tnum">{{ formatDate(project.updated_at) }}</span>
          </div>
        </div>
      </div>
    </div>

    <!-- Quick Create Modal -->
    <div v-if="showCreateModal" class="modal-overlay" @click.self="showCreateModal = false">
      <div class="modal">
        <div class="modal-header">
          <h3>快速创建项目</h3>
          <button class="close-btn" @click="showCreateModal = false">
            <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor" class="size-5">
              <path stroke-linecap="round" stroke-linejoin="round" d="M6 18 18 6M6 6l12 12" />
            </svg>
          </button>
        </div>

        <div class="form-group">
          <label>项目名称</label>
          <input v-model="newProject.name" @input="updateDefaultPath" class="input" placeholder="例如：我的修仙小说" />
        </div>

        <div class="form-group">
          <label>题材</label>
          <select v-model="newProject.genre" class="input">
            <option v-for="g in genres" :key="g.id" :value="g.id">{{ g.name }}</option>
          </select>
        </div>

        <div class="form-group" v-if="availableCreateSubstyles.length">
          <label>子风格</label>
          <select v-model="newProject.substyle" class="input">
            <option v-for="s in availableCreateSubstyles" :key="s.id" :value="s.id">{{ s.name }}</option>
          </select>
        </div>

        <div class="advanced-toggle" @click="showAdvancedPath = !showAdvancedPath">
          <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor" class="size-4" :class="{ 'rotate-90': showAdvancedPath }">
            <path stroke-linecap="round" stroke-linejoin="round" d="m8.25 4.5 7.5 7.5-7.5 7.5" />
          </svg>
          <span>自定义存储路径</span>
        </div>

        <div v-if="showAdvancedPath" class="form-group">
          <label>存储路径</label>
          <input v-model="newProject.path" class="input" placeholder="默认：./data/项目名称" />
          <small class="hint">留空则自动使用 ./data/项目名称</small>
        </div>

        <div class="modal-actions">
          <button class="btn btn-secondary" @click="showCreateModal = false">取消</button>
          <button class="btn btn-primary" @click="createProject" :disabled="creating">
            {{ creating ? '创建中...' : '立即创建' }}
          </button>
        </div>
      </div>
    </div>

    <!-- Import Modal -->
    <div v-if="showImportModal" class="modal-overlay" @click.self="showImportModal = false">
      <div class="modal">
        <div class="modal-header">
          <h3>导入项目</h3>
          <button class="close-btn" @click="showImportModal = false">
            <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor" class="size-5">
              <path stroke-linecap="round" stroke-linejoin="round" d="M6 18 18 6M6 6l12 12" />
            </svg>
          </button>
        </div>
        <div class="form-group">
          <label>项目路径</label>
          <input v-model="importPath" class="input" placeholder="输入现有项目的路径" />
          <small class="hint">支持已存在的小说文件夹，会自动识别里面的大纲和章节</small>
        </div>
        <div class="modal-actions">
          <button class="btn btn-secondary" @click="showImportModal = false">取消</button>
          <button class="btn btn-primary" @click="importProject" :disabled="importing">
            {{ importing ? '导入中...' : '确认导入' }}
          </button>
        </div>
      </div>
    </div>

    <!-- Delete Confirm -->
    <ConfirmDialog
      :isOpen="showDeleteDialog"
      title="删除项目"
      :message="`确定要彻底删除项目「${deleteTarget?.name}」吗？\n\n此操作将永久删除该项目的所有文件，不可恢复。`"
      confirmText="确认删除"
      type="danger"
      :loading="deleting"
      @confirm="doDelete"
      @cancel="showDeleteDialog = false"
    />

    <!-- AI Config Modal -->
    <AiConfigModal v-if="showAiConfigModal" @close="showAiConfigModal = false" />
  </div>
</template>

<style scoped>
.home-page {
  height: 100%;
  width: 100%;
  display: flex;
  flex-direction: column;
  background-color: var(--bg);
  overflow-y: auto;
}

/* Top Bar */
.top-bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0.75rem 1.5rem;
  background: var(--card);
  border-bottom: 1px solid var(--border);
  flex-shrink: 0;
}

.top-bar-left {
  display: flex;
  align-items: center;
  gap: 0.625rem;
}

.logo-mark {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 30px;
  height: 30px;
  background: var(--primary);
  color: var(--on-primary);
  border-radius: var(--radius-md);
}

.logo-text-wrap {
  display: flex;
  flex-direction: column;
  line-height: 1.2;
}

.logo-text {
  font-size: 0.9375rem;
  font-weight: 600;
  color: var(--ink-primary);
}

.logo-sub {
  font-size: 0.6875rem;
  color: var(--ink-muted);
}

.top-bar-right {
  display: flex;
  align-items: center;
  gap: 0.5rem;
}

.icon-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 32px;
  height: 32px;
  background: var(--card);
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  color: var(--ink-secondary);
  cursor: pointer;
  transition: color var(--dur-fast) var(--ease-standard), border-color var(--dur-fast) var(--ease-standard), background-color var(--dur-fast) var(--ease-standard);
}

.icon-btn:hover {
  color: var(--ink-primary);
  border-color: var(--border-strong);
  background: var(--hover);
}

/* Main Content */
.home-content {
  flex: 1;
  max-width: 1200px;
  width: 100%;
  margin: 0 auto;
  padding: 2rem 1.5rem 3rem;
}

/* Title Row */
.title-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 1rem;
  flex-wrap: wrap;
  margin-bottom: 1.5rem;
}

.title-block {
  display: flex;
  align-items: baseline;
  gap: 0.75rem;
}

.page-title {
  font-size: 1.375rem;
  font-weight: 600;
  color: var(--ink-primary);
  letter-spacing: -0.01em;
}

.title-count {
  font-family: var(--font-mono);
  font-size: 0.75rem;
  color: var(--ink-muted);
}

.title-actions {
  display: flex;
  gap: 0.5rem;
}

/* Projects Grid */
.projects-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
  gap: 0.875rem;
}

.project-card {
  background: var(--card);
  border-radius: var(--radius-lg);
  padding: 1.1rem 1.2rem 1rem;
  border: 1px solid var(--border);
  box-shadow: var(--shadow-sm);
  cursor: pointer;
  transition: border-color var(--dur-fast) var(--ease-standard), box-shadow var(--dur-fast) var(--ease-standard);
  display: flex;
  flex-direction: column;
  gap: 0.6rem;
}

.project-card:hover {
  border-color: var(--border-strong);
  box-shadow: var(--shadow-md);
}

.project-card.missing {
  opacity: 0.5;
  cursor: not-allowed;
}

.card-top {
  display: flex;
  align-items: center;
  gap: 0.6rem;
}

.card-mark {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 34px;
  height: 34px;
  flex-shrink: 0;
  background: var(--primary-tint);
  color: var(--primary-on-tint);
  border-radius: var(--radius-md);
  font-size: 0.9375rem;
  font-weight: 500;
  line-height: 1;
}

.card-genre-tag {
  font-size: 0.6875rem;
  font-weight: 500;
  padding: 0.15rem 0.5rem;
  border-radius: var(--radius-sm);
  border: 1px solid var(--border);
  color: var(--ink-secondary);
  background: var(--surface);
}

.card-delete-btn {
  margin-left: auto;
  background: none;
  border: none;
  color: var(--ink-muted);
  cursor: pointer;
  padding: 0.35rem;
  border-radius: var(--radius-sm);
  display: flex;
  align-items: center;
  justify-content: center;
  opacity: 0;
  transition: opacity var(--dur-fast) var(--ease-standard), color var(--dur-fast) var(--ease-standard), background-color var(--dur-fast) var(--ease-standard);
}

.project-card:hover .card-delete-btn,
.card-delete-btn:focus-visible {
  opacity: 1;
}

.card-delete-btn:hover {
  background: var(--danger-tint);
  color: var(--danger);
}

.card-title {
  font-size: 1.0625rem;
  font-weight: 600;
  color: var(--ink-primary);
  margin: 0;
  line-height: 1.35;
  letter-spacing: -0.01em;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.card-meta {
  display: flex;
  align-items: baseline;
  gap: 0.5rem;
  padding-top: 0.55rem;
  border-top: 1px solid var(--border);
}

.meta-item {
  display: inline-flex;
  align-items: baseline;
  gap: 0.2rem;
}

.meta-num {
  font-family: var(--font-mono);
  font-size: 0.875rem;
  font-weight: 500;
  color: var(--ink-primary);
}

.meta-unit {
  font-size: 0.6875rem;
  color: var(--ink-muted);
}

.meta-sep {
  color: var(--border);
  font-size: 0.75rem;
}

.card-date {
  margin-left: auto;
  font-family: var(--font-mono);
  font-size: 0.6875rem;
  color: var(--ink-muted);
}

/* Loading / Error / Empty States */
.loading-state,
.error-state,
.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 5rem 2rem;
  color: var(--ink-muted);
  gap: 1rem;
}

.spinner {
  width: 2rem;
  height: 2rem;
  border: 2px solid var(--border);
  border-top-color: var(--primary);
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

.state-icon {
  color: var(--ink-muted);
  opacity: 0.5;
}

.empty-state h3 {
  color: var(--ink-primary);
  font-size: 1.125rem;
  font-weight: 600;
  margin: 0;
}

.empty-state p {
  color: var(--ink-secondary);
  margin: 0;
  font-size: 0.9375rem;
}

/* Modal */
.modal-overlay {
  position: fixed;
  top: 0; left: 0; right: 0; bottom: 0;
  background: rgb(15 17 21 / 0.45);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: var(--z-modal-backdrop);
  animation: fadeIn var(--dur-fast) ease-out;
}

@keyframes fadeIn {
  from { opacity: 0; }
  to { opacity: 1; }
}

.modal {
  background: var(--card);
  border: 1px solid var(--border);
  border-radius: var(--radius-lg);
  padding: 1.5rem;
  width: 100%;
  max-width: 460px;
  box-shadow: var(--shadow-xl);
  animation: modalIn var(--dur-base) var(--ease-emerge);
  position: relative;
  z-index: var(--z-modal);
}

@keyframes modalIn {
  from { opacity: 0; transform: scale(0.98); }
  to { opacity: 1; transform: scale(1); }
}

.modal-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 1.25rem;
}

.modal h3 {
  margin: 0;
  font-size: 1.125rem;
  font-weight: 600;
  color: var(--ink-primary);
}

.close-btn {
  background: none;
  border: none;
  color: var(--ink-muted);
  cursor: pointer;
  padding: 0.35rem;
  border-radius: var(--radius-sm);
  display: flex;
  align-items: center;
  justify-content: center;
  transition: color var(--dur-fast) var(--ease-standard), background-color var(--dur-fast) var(--ease-standard);
}

.close-btn:hover {
  background: var(--hover);
  color: var(--ink-primary);
}

.form-group {
  margin-bottom: 1rem;
}

.form-group label {
  display: block;
  margin-bottom: 0.4rem;
  font-weight: 500;
  font-size: 0.8125rem;
  color: var(--ink-secondary);
}

.input {
  width: 100%;
  padding: 0.55rem 0.85rem;
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  font-family: var(--font-ui);
  font-size: 0.9375rem;
  color: var(--ink-primary);
  background: var(--surface);
  transition: border-color var(--dur-fast) var(--ease-standard), box-shadow var(--dur-fast) var(--ease-standard), background-color var(--dur-fast) var(--ease-standard);
}

.input:focus {
  outline: none;
  border-color: var(--primary);
  background: var(--card);
  box-shadow: 0 0 0 3px var(--primary-tint);
}

.hint {
  display: block;
  margin-top: 0.4rem;
  font-size: 0.75rem;
  color: var(--ink-muted);
}

.modal-actions {
  display: flex;
  justify-content: flex-end;
  gap: 0.625rem;
  margin-top: 1.5rem;
  padding-top: 1rem;
  border-top: 1px solid var(--border);
}

/* Advanced toggle */
.advanced-toggle {
  display: flex;
  align-items: center;
  gap: 0.4rem;
  font-size: 0.8125rem;
  color: var(--ink-muted);
  cursor: pointer;
  padding: 0.4rem 0;
  margin-bottom: 0.6rem;
  transition: color var(--dur-fast) var(--ease-standard);
  font-weight: 500;
}

.advanced-toggle:hover {
  color: var(--ink-secondary);
}

.advanced-toggle svg {
  transition: transform var(--dur-fast) var(--ease-standard);
}

.advanced-toggle .rotate-90 {
  transform: rotate(90deg);
}
</style>
