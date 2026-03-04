<!-- Copyright (c) 2026 左岚. All rights reserved. -->
<!-- HomeView.vue - 项目总览（第一层） -->
<script setup>
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { projectsApi, aiApi } from '../api'
import { useProjectStore } from '../stores/project'
import ConfirmDialog from '../components/ConfirmDialog.vue'

const router = useRouter()
const projectStore = useProjectStore()

const projects = ref([])
const loading = ref(false)
const error = ref(null)

// Genre list from API
const genres = ref([])

// Create modal
const showCreateModal = ref(false)
const newProject = ref({ name: '', path: '', genre: '' })
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

onMounted(() => {
  loadProjects()
  loadGenres()
})

async function loadGenres() {
  try {
    const { data } = await aiApi.getGenres()
    genres.value = data.genres || []
  } catch (e) {
    console.warn('加载题材列表失败，使用默认', e)
    genres.value = [
      { id: '修仙', name: '修仙' },
      { id: '玄幻', name: '玄幻' },
      { id: '都市', name: '都市' },
      { id: '科幻', name: '科幻' },
      { id: '规则怪谈', name: '规则怪谈' },
      { id: '其他', name: '其他' }
    ]
  }
}

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
  newProject.value = { name: '', path: '', genre: genres.value[0]?.id || '修仙' }
  showAdvancedPath.value = false
  showCreateModal.value = true
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
    alert('创建项目失败：' + (e.response?.data?.detail || e.message))
  } finally {
    creating.value = false
  }
}

async function importProject() {
  if (!importPath.value) return
  importing.value = true
  try {
    await projectsApi.import(importPath.value)
    await projectStore.setCurrentProject(importPath.value)
    showImportModal.value = false
    router.push('/workspace/project')
  } catch (e) {
    alert('导入项目失败：' + (e.response?.data?.detail || e.message))
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
    alert('删除失败：' + (e.response?.data?.detail || e.message))
  } finally {
    deleting.value = false
  }
}

function formatDate(ts) {
  if (!ts) return '--'
  const d = new Date(typeof ts === 'number' ? ts * 1000 : ts)
  return d.toLocaleDateString('zh-CN', { month: 'short', day: 'numeric' })
}

function getGenreIcon(genre) {
  switch (genre) {
    case '修仙':
      return '<svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" d="M3.75 13.5l10.5-11.25L12 10.5h8.25L9.75 21.75 12 13.5H3.75z" /></svg>'
    case '都市':
      return '<svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" d="M2.25 21h19.5m-18-18v18m10.5-18v18m6-13.5V21M6.75 6.75h.75m-.75 3h.75m-.75 3h.75m3-6h.75m-.75 3h.75m-.75 3h.75M6.75 21v-3.375c0-.621.504-1.125 1.125-1.125h2.25c.621 0 1.125.504 1.125 1.125V21" /></svg>'
    case '科幻':
      return '<svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" d="M9.348 14.651a3.75 3.75 0 010-5.303m5.304 0a3.75 3.75 0 010 5.303m-7.425 2.122a6.75 6.75 0 010-9.546m9.546 0a6.75 6.75 0 010 9.546M5.106 18.894c-3.808-3.808-3.808-9.98 0-13.788m13.788 0c3.808 3.808 3.808 9.98 0 13.788M12 12h.008v.008H12V12zm.375 0a.375.375 0 11-.75 0 .375.375 0 01.75 0z" /></svg>'
    case '玄幻':
      return '<svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" d="M9.813 15.904 9 18.75l-.813-2.846a4.5 4.5 0 0 0-3.09-3.09L2.25 12l2.846-.813a4.5 4.5 0 0 0 3.09-3.09L9 5.25l.813 2.846a4.5 4.5 0 0 0 3.09 3.09L15.75 12l-2.846.813a4.5 4.5 0 0 0-3.09 3.09ZM18.259 8.715 18 9.75l-.259-1.035a3.375 3.375 0 0 0-2.455-2.456L14.25 6l1.036-.259a3.375 3.375 0 0 0 2.455-2.456L18 2.25l.259 1.035a3.375 3.375 0 0 0 2.456 2.456L21.75 6l-1.035.259a3.375 3.375 0 0 0-2.456 2.456Z" /></svg>'
    default:
      return '<svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" d="M12 6.042A8.967 8.967 0 006 3.75c-1.052 0-2.062.18-3 .512v14.25A8.987 8.987 0 016 18c2.305 0 4.408.867 6 2.292m0-14.25a8.966 8.966 0 016-2.292c1.052 0 2.062.18 3 .512v14.25A8.987 8.987 0 0018 18a8.967 8.967 0 00-6 2.292m0-14.25v14.25" /></svg>'
  }
}
</script>

<template>
  <div class="home-page">
    <!-- Top bar -->
    <header class="top-bar">
      <div class="top-bar-left">
        <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor" class="logo-icon">
          <path stroke-linecap="round" stroke-linejoin="round" d="m16.862 4.487 1.687-1.688a1.875 1.875 0 1 1 2.652 2.652L10.582 16.07a4.5 4.5 0 0 1-1.897 1.13L6 18l.8-2.685a4.5 4.5 0 0 1 1.13-1.897l8.932-8.931Zm0 0L19.5 7.125M18 14v4.75A2.25 2.25 0 0 1 15.75 21H5.25A2.25 2.25 0 0 1 3 18.75V8.25A2.25 2.25 0 0 1 5.25 6H10" />
        </svg>
        <span class="logo-text">Webnovel Writer</span>
      </div>
    </header>

    <!-- Main content -->
    <div class="home-content">
      <!-- Title row -->
      <div class="title-row">
        <h1 class="page-title">我的作品</h1>
        <div class="title-actions">
          <button class="btn btn-secondary" @click="showImportModal = true">
            <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor" class="size-5">
              <path stroke-linecap="round" stroke-linejoin="round" d="M3 16.5v2.25A2.25 2.25 0 0 0 5.25 21h13.5A2.25 2.25 0 0 0 21 18.75V16.5m-13.5-9L12 3m0 0 4.5 4.5M12 3v13.5" />
            </svg>
            导入项目
          </button>
          <button class="btn btn-primary" @click="openCreateModal">
            <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor" class="size-5">
              <path stroke-linecap="round" stroke-linejoin="round" d="M12 4.5v15m7.5-7.5h-15" />
            </svg>
            新建项目
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
        <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor" class="error-icon">
          <path stroke-linecap="round" stroke-linejoin="round" d="M12 9v3.75m-9.303 3.376c-.866 1.5.217 3.374 1.948 3.374h14.71c1.73 0 2.813-1.874 1.948-3.374L13.949 3.378c-.866-1.5-3.032-1.5-3.898 0L2.697 16.126ZM12 15.75h.007v.008H12v-.008Z" />
        </svg>
        <p>加载失败: {{ error }}</p>
        <button class="btn btn-secondary" @click="loadProjects">重试</button>
      </div>

      <!-- Empty -->
      <div v-else-if="projects.length === 0" class="empty-state">
        <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor" class="empty-icon">
          <path stroke-linecap="round" stroke-linejoin="round" d="M12 6.042A8.967 8.967 0 0 0 6 3.75c-1.052 0-2.062.18-3 .512v14.25A8.987 8.987 0 0 1 6 18c2.305 0 4.408.867 6 2.292m0-14.25a8.966 8.966 0 0 1 6-2.292c1.052 0 2.062.18 3 .512v14.25A8.987 8.987 0 0 0 18 18a8.967 8.967 0 0 0-6 2.292m0-14.25v14.25" />
        </svg>
        <h3>还没有任何作品</h3>
        <p>新建或导入一个项目，开始您的创作之旅</p>
        <button class="btn btn-primary" @click="openCreateModal">
          <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor" class="size-5">
            <path stroke-linecap="round" stroke-linejoin="round" d="M12 4.5v15m7.5-7.5h-15" />
          </svg>
          新建项目
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
            <div class="card-genre-icon" v-html="getGenreIcon(project.genre)"></div>
            <button class="card-delete-btn" @click.stop="confirmDelete(project)" title="删除项目">
              <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor" class="size-4">
                <path stroke-linecap="round" stroke-linejoin="round" d="m14.74 9-.346 9m-4.788 0L9.26 9m9.968-3.21c.342.052.682.107 1.022.166m-1.022-.165L18.16 19.673a2.25 2.25 0 0 1-2.244 2.077H8.084a2.25 2.25 0 0 1-2.244-2.077L4.772 5.79m14.456 0a48.108 48.108 0 0 0-3.478-.397m-12 .562c.34-.059.68-.114 1.022-.165m0 0a48.11 48.11 0 0 1 3.478-.397m7.5 0v-.916c0-1.18-.91-2.164-2.09-2.201a51.964 51.964 0 0 0-3.32 0c-1.18.037-2.09 1.022-2.09 2.201v.916m7.5 0a48.667 48.667 0 0 0-7.5 0" />
              </svg>
            </button>
          </div>
          <h3 class="card-title">{{ project.name }}</h3>
          <span class="card-genre-tag">{{ project.genre || '未分类' }}</span>
          <div class="card-meta">
            <div class="meta-item">
              <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor" class="size-4">
                <path stroke-linecap="round" stroke-linejoin="round" d="M19.5 14.25v-2.625a3.375 3.375 0 0 0-3.375-3.375h-1.5A1.125 1.125 0 0 1 13.5 7.125v-1.5a3.375 3.375 0 0 0-3.375-3.375H8.25m0 12.75h7.5m-7.5 3H12M10.5 2.25H5.625c-.621 0-1.125.504-1.125 1.125v17.25c0 .621.504 1.125 1.125 1.125h12.75c.621 0 1.125-.504 1.125-1.125V11.25a9 9 0 0 0-9-9Z" />
              </svg>
              <span>{{ project.total_chapters || 0 }} 章</span>
            </div>
            <div class="meta-item">
              <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor" class="size-4">
                <path stroke-linecap="round" stroke-linejoin="round" d="m16.862 4.487 1.687-1.688a1.875 1.875 0 1 1 2.652 2.652L10.582 16.07a4.5 4.5 0 0 1-1.897 1.13L6 18l.8-2.685a4.5 4.5 0 0 1 1.13-1.897l8.932-8.931Zm0 0L19.5 7.125M18 14v4.75A2.25 2.25 0 0 1 15.75 21H5.25A2.25 2.25 0 0 1 3 18.75V8.25A2.25 2.25 0 0 1 5.25 6H10" />
              </svg>
              <span>{{ project.total_words ? (project.total_words / 10000).toFixed(1) + ' 万字' : '0 字' }}</span>
            </div>
          </div>
          <div class="card-footer">
            <span class="card-date">{{ formatDate(project.updated_at) }}</span>
          </div>
        </div>
      </div>
    </div>

    <!-- Create Modal -->
    <div v-if="showCreateModal" class="modal-overlay" @click.self="showCreateModal = false">
      <div class="modal">
        <div class="modal-header">
          <h3>新建项目</h3>
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
  </div>
</template>

<style scoped>
.home-page {
  height: 100%;
  width: 100%;
  display: flex;
  flex-direction: column;
  background-color: var(--bg-background);
  overflow-y: auto;
}

/* Top Bar */
.top-bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 1.25rem 2.5rem;
  background: white;
  border-bottom: 1px solid var(--border);
  flex-shrink: 0;
}

.top-bar-left {
  display: flex;
  align-items: center;
  gap: 0.75rem;
}

.logo-icon {
  width: 1.75rem;
  height: 1.75rem;
  color: var(--primary);
}

.logo-text {
  font-size: 1.25rem;
  font-weight: 700;
  background: linear-gradient(135deg, var(--primary) 0%, var(--secondary) 100%);
  background-clip: text;
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
}

/* Main Content */
.home-content {
  flex: 1;
  max-width: 1200px;
  width: 100%;
  margin: 0 auto;
  padding: 2.5rem;
}

/* Title Row */
.title-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 2rem;
}

.page-title {
  font-size: 1.75rem;
  font-weight: 800;
  color: var(--text-primary);
  letter-spacing: -0.02em;
}

.title-actions {
  display: flex;
  gap: 0.75rem;
}

.title-actions .btn {
  gap: 0.375rem;
}

/* Projects Grid */
.projects-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
  gap: 1.5rem;
}

.project-card {
  background: white;
  border-radius: 16px;
  padding: 1.5rem;
  border: 1px solid rgba(229, 231, 235, 0.6);
  box-shadow: 0 2px 8px -2px rgba(0, 0, 0, 0.04);
  cursor: pointer;
  transition: all 0.25s cubic-bezier(0.4, 0, 0.2, 1);
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
}

.project-card:hover {
  transform: translateY(-4px);
  box-shadow: 0 12px 24px -4px rgba(99, 102, 241, 0.12);
  border-color: var(--border-hover);
}

.project-card.missing {
  opacity: 0.5;
  cursor: not-allowed;
}

.card-top {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
}

.card-genre-icon {
  width: 2.5rem;
  height: 2.5rem;
  border-radius: 10px;
  background: linear-gradient(135deg, rgba(99, 102, 241, 0.1), rgba(129, 140, 248, 0.06));
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--primary);
}

.card-genre-icon svg {
  width: 1.25rem;
  height: 1.25rem;
}

.card-delete-btn {
  background: none;
  border: none;
  color: var(--text-muted);
  cursor: pointer;
  padding: 0.375rem;
  border-radius: 6px;
  display: flex;
  align-items: center;
  justify-content: center;
  opacity: 0;
  transition: all 0.2s;
}

.project-card:hover .card-delete-btn {
  opacity: 1;
}

.card-delete-btn:hover {
  background: #fee2e2;
  color: var(--danger);
}

.card-title {
  font-size: 1.125rem;
  font-weight: 700;
  color: var(--text-primary);
  margin: 0;
  line-height: 1.3;
}

.card-genre-tag {
  display: inline-flex;
  align-self: flex-start;
  font-size: 0.75rem;
  font-weight: 500;
  padding: 0.125rem 0.5rem;
  border-radius: 999px;
  background: rgba(99, 102, 241, 0.08);
  color: var(--primary);
}

.card-meta {
  display: flex;
  gap: 1rem;
}

.meta-item {
  display: flex;
  align-items: center;
  gap: 0.25rem;
  font-size: 0.8125rem;
  color: var(--text-secondary);
}

.meta-item svg {
  color: var(--text-muted);
}

.card-footer {
  margin-top: auto;
  padding-top: 0.75rem;
  border-top: 1px solid rgba(229, 231, 235, 0.5);
}

.card-date {
  font-size: 0.75rem;
  color: var(--text-muted);
}

/* Loading / Error / Empty States */
.loading-state,
.error-state,
.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 4rem 2rem;
  color: var(--text-muted);
  gap: 1rem;
}

.spinner {
  width: 2rem;
  height: 2rem;
  border: 3px solid var(--border);
  border-top-color: var(--primary);
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

.error-icon,
.empty-icon {
  width: 3rem;
  height: 3rem;
  opacity: 0.4;
}

.empty-state h3 {
  color: var(--text-primary);
  font-size: 1.125rem;
  margin: 0;
}

.empty-state p {
  color: var(--text-muted);
  margin: 0;
}

/* Modal Styling */
.modal-overlay {
  position: fixed;
  top: 0; left: 0; right: 0; bottom: 0;
  background: rgba(0, 0, 0, 0.4);
  backdrop-filter: blur(8px);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 100;
  animation: fadeIn 0.2s ease-out;
}

@keyframes fadeIn {
  from { opacity: 0; }
  to { opacity: 1; }
}

.modal {
  background: white;
  border-radius: var(--radius-xl);
  padding: 2rem;
  width: 100%;
  max-width: 500px;
  box-shadow: 0 20px 25px -5px rgba(0, 0, 0, 0.1), 0 10px 10px -5px rgba(0, 0, 0, 0.04);
  border: 1px solid var(--border);
  animation: scaleIn 0.3s cubic-bezier(0.16, 1, 0.3, 1);
  position: relative;
}

@keyframes scaleIn {
  from { opacity: 0; transform: scale(0.95) translateY(10px); }
  to { opacity: 1; transform: scale(1) translateY(0); }
}

.modal-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 2rem;
}

.modal h3 {
  margin: 0;
  font-size: 1.5rem;
  font-weight: 700;
  color: var(--text-primary);
}

.close-btn {
  background: none;
  border: none;
  color: var(--text-muted);
  cursor: pointer;
  padding: 0.375rem;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all 0.2s;
}

.close-btn:hover {
  background: var(--bg-hover);
  color: var(--text-primary);
}

.form-group {
  margin-bottom: 1.5rem;
}

.form-group label {
  display: block;
  margin-bottom: 0.5rem;
  font-weight: 500;
  font-size: 0.875rem;
  color: var(--text-secondary);
}

.input {
  width: 100%;
  padding: 0.625rem 0.75rem;
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  font-size: 0.875rem;
  color: var(--text-primary);
  background: white;
  transition: border-color 0.2s;
}

.input:focus {
  outline: none;
  border-color: var(--primary);
  box-shadow: 0 0 0 3px rgba(99, 102, 241, 0.1);
}

.hint {
  display: block;
  margin-top: 0.5rem;
  font-size: 0.75rem;
  color: var(--text-muted);
}

.modal-actions {
  display: flex;
  justify-content: flex-end;
  gap: 1rem;
  margin-top: 2.5rem;
  padding-top: 1.5rem;
  border-top: 1px solid var(--border);
}

/* Advanced toggle */
.advanced-toggle {
  display: flex;
  align-items: center;
  gap: 0.375rem;
  font-size: 0.8125rem;
  color: var(--text-muted);
  cursor: pointer;
  padding: 0.25rem 0;
  margin-bottom: 0.5rem;
  transition: color 0.2s;
}

.advanced-toggle:hover {
  color: var(--text-secondary);
}

.advanced-toggle svg {
  transition: transform 0.2s;
}

.advanced-toggle .rotate-90 {
  transform: rotate(90deg);
}
</style>
