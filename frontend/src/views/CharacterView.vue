<script setup>
// Copyright (c) 2026 左岚. All rights reserved.
// CharacterView.vue - 世界观管理(卡片墙 + 详情抽屉)
import { ref, onMounted, onUnmounted, computed, watch } from 'vue'
import { charactersApi, chaptersApi } from '../api'
import { useProjectStore } from '../stores/project'
import { useToast } from '../composables/useToast'
import ConfirmDialog from '../components/ConfirmDialog.vue'
import { marked } from 'marked'
import DOMPurify from 'dompurify'
import {
    RefreshCw, Plus, Search, X, Pencil, Trash2, ChevronRight,
    Activity, IdCard, Users, Gem, Scroll, Landmark, MapPin, FileText
} from 'lucide-vue-next'

const toast = useToast()
const projectStore = useProjectStore()

const categories = ref({})
const loading = ref(true)
const activeTab = ref('主要角色')
const searchText = ref('')

// 关系图数据 → 角色元信息(分类/主角/身故/关系)
const graphLoaded = ref(false)
const charMeta = ref({})

// 抽屉
const drawerOpen = ref(false)
const drawerItem = ref(null)
const profile = ref(null)
const profileLoading = ref(false)
const fileContent = ref('')
const fileLoading = ref(false)
const editMode = ref(false)
const editText = ref('')
const saving = ref(false)

// 单文件文档视图
const docLoading = ref(false)
const docContent = ref('')
const docEditing = ref(false)
const docText = ref('')
const docSaving = ref(false)

// 新建 / 删除
const showCreateModal = ref(false)
const newCharName = ref('')
const newCharCategory = ref('次要角色')
const deleteTarget = ref(null)
const deleting = ref(false)

// 同步状态
const syncStatus = ref({
    total_chapters: 0,
    synced_chapters: 0,
    pending_chapters: 0,
    last_synced_chapter: 0,
    last_continuous_synced_chapter: 0,
    pending_items: [],
    chapter_items: [],
})
const syncingMissing = ref(false)
const syncMessage = ref('')
const syncListExpanded = ref(false)

const tabsConfig = [
    { key: '实时状态', icon: Activity, single: true },
    { key: '主角卡', icon: IdCard, single: true },
    { key: '主要角色', dot: 'var(--cat-main-dot)' },
    { key: '次要角色', dot: 'var(--cat-sec-dot)' },
    { key: '反派角色', dot: 'var(--cat-vil-dot)' },
    { key: '活跃角色表', icon: Users, single: true },
    { key: '宝物库', icon: Gem },
    { key: '功法库', icon: Scroll },
    { key: '势力库', icon: Landmark },
    { key: '地点库', icon: MapPin },
]
const charTabs = ['主要角色', '次要角色', '反派角色']
const singleFileTabs = ['实时状态', '主角卡', '活跃角色表']

const isCharTab = computed(() => charTabs.includes(activeTab.value))
const isSingleTab = computed(() => singleFileTabs.includes(activeTab.value))
const activeTabConfig = computed(() => tabsConfig.find(t => t.key === activeTab.value))

const catDotColor = {
    '主要角色': 'var(--cat-main-dot)',
    '次要角色': 'var(--cat-sec-dot)',
    '反派角色': 'var(--cat-vil-dot)',
    '未归档': 'var(--cat-un-dot)',
}

const libIcon = { '宝物库': Gem, '功法库': Scroll, '势力库': Landmark, '地点库': MapPin }

const singleItem = computed(() => categories.value[activeTab.value] || null)

const currentList = computed(() => {
    if (isSingleTab.value) return []
    return categories.value[activeTab.value] || []
})

const filteredList = computed(() => {
    const kw = searchText.value.trim().toLowerCase()
    if (!kw) return currentList.value
    return currentList.value.filter(item => (item.name || '').toLowerCase().includes(kw))
})

function metaOf(name) {
    return charMeta.value[name] || null
}

function renderMd(text) {
    if (!text) return ''
    return DOMPurify.sanitize(marked.parse(text, { breaks: true }))
}

const docHtml = computed(() => renderMd(docContent.value))
const fileHtml = computed(() => renderMd(fileContent.value))

function tagName(t) { return typeof t === 'string' ? t : (t?.name || '') }
function tagDesc(t) { return typeof t === 'object' && t ? (t.desc || t.description || '') : '' }

const profileRows = computed(() => {
    const p = profile.value
    if (!p) return []
    return [
        { label: '境界', value: p.realm },
        { label: '身份', value: p.identity },
        { label: '状态', value: p.status },
        { label: '当前位置', value: p.location },
        { label: '初登场', value: p.firstAppear },
        { label: '最近更新', value: p.lastUpdateChapter ? `第${p.lastUpdateChapter}章` : '' },
    ].filter(r => r.value)
})

const profileTagGroups = computed(() => {
    const p = profile.value
    if (!p) return []
    return [
        { label: '势力', items: p.factions || [], dot: 'var(--success)' },
        { label: '宝物', items: p.treasures || [], dot: 'var(--warning)' },
        { label: '功法', items: p.techniques || [], dot: 'var(--cat-vil-dot)' },
    ].filter(g => g.items.length)
})

// ── 数据加载 ──
async function loadCharacters() {
    loading.value = true
    try {
        const { data } = await charactersApi.list()
        categories.value = data.categories || {}
    } catch (e) {
        console.error('加载档案列表失败:', e)
    } finally {
        loading.value = false
    }
}

async function loadRelationships() {
    try {
        const { data } = await charactersApi.getRelationships()
        const { nodes = [], edges = [], protagonist } = data || {}
        const byId = {}
        nodes.forEach(n => { byId[n.id] = n })
        const meta = {}
        nodes.forEach(node => {
            const relations = edges
                .filter(e => e.source === node.id || e.target === node.id)
                .map(e => {
                    const other = byId[e.source === node.id ? e.target : e.source]
                    return {
                        name: other?.name || '未知',
                        label: e.label || '相关',
                        category: other?.category || '次要角色',
                    }
                })
            meta[node.name] = {
                category: node.category,
                isProtagonist: node.name === protagonist,
                dead: node.dead || false,
                relationCount: relations.length,
                relations,
            }
        })
        charMeta.value = meta
        graphLoaded.value = true
    } catch (e) {
        console.warn('关系数据不可用,卡片降级显示:', e?.message)
        graphLoaded.value = false
    }
}

async function loadSyncStatus() {
    try {
        const { data } = await chaptersApi.getSyncStatus()
        syncStatus.value = data
    } catch (e) {
        console.error('加载同步状态失败:', e)
    }
}

// ── 单文件文档 ──
async function loadDoc() {
    const item = singleItem.value
    docEditing.value = false
    if (!item?.path) { docContent.value = ''; return }
    docLoading.value = true
    try {
        const { data } = await charactersApi.getFile(item.path)
        docContent.value = data.content || ''
    } catch (e) {
        docContent.value = ''
        console.error('加载文档失败:', e)
    } finally {
        docLoading.value = false
    }
}

function startDocEdit() {
    docText.value = docContent.value
    docEditing.value = true
}

async function saveDoc() {
    const item = singleItem.value
    if (!item?.path) return
    docSaving.value = true
    try {
        await charactersApi.updateFile(item.path, docText.value)
        docContent.value = docText.value
        docEditing.value = false
        toast.success('已保存')
    } catch (e) {
        toast.error('保存失败: ' + (e.response?.data?.detail || e.message))
    } finally {
        docSaving.value = false
    }
}

// ── 抽屉 ──
async function openDrawer(item) {
    drawerItem.value = item
    drawerOpen.value = true
    editMode.value = false
    profile.value = null
    fileContent.value = ''

    fileLoading.value = true
    charactersApi.getFile(item.path)
        .then(({ data }) => { fileContent.value = data.content || '' })
        .catch(e => console.error('加载档案失败:', e))
        .finally(() => { fileLoading.value = false })

    if (isCharTab.value) {
        profileLoading.value = true
        try {
            const { data } = await charactersApi.getProfile(item.name)
            profile.value = data
        } catch (e) {
            if (e.response?.status !== 404) console.error('加载角色档案失败:', e)
            profile.value = null
        } finally {
            profileLoading.value = false
        }
    }
}

function closeDrawer() {
    drawerOpen.value = false
    editMode.value = false
    setTimeout(() => {
        if (!drawerOpen.value) { drawerItem.value = null; profile.value = null }
    }, 250)
}

function startEdit() {
    editText.value = fileContent.value
    editMode.value = true
}

async function saveEdit() {
    if (!drawerItem.value) return
    saving.value = true
    try {
        await charactersApi.updateFile(drawerItem.value.path, editText.value)
        fileContent.value = editText.value
        editMode.value = false
        toast.success('已保存')
        if (isCharTab.value) {
            charactersApi.getProfile(drawerItem.value.name)
                .then(({ data }) => { profile.value = data })
                .catch(() => {})
        }
    } catch (e) {
        toast.error('保存失败: ' + (e.response?.data?.detail || e.message))
    } finally {
        saving.value = false
    }
}

// ── 新建 / 删除 ──
async function createCharacter() {
    if (!newCharName.value.trim()) {
        toast.info('请输入角色名')
        return
    }
    try {
        await charactersApi.create(newCharName.value.trim(), newCharCategory.value)
        showCreateModal.value = false
        newCharName.value = ''
        await Promise.all([loadCharacters(), loadRelationships()])
    } catch (e) {
        toast.error('创建失败: ' + (e.response?.data?.detail || e.message))
    }
}

function confirmDelete(item) {
    deleteTarget.value = item
}

async function doDelete() {
    const item = deleteTarget.value
    if (!item) return
    deleting.value = true
    try {
        await charactersApi.delete(item.path)
        if (drawerItem.value?.path === item.path) closeDrawer()
        deleteTarget.value = null
        await Promise.all([loadCharacters(), loadRelationships()])
    } catch (e) {
        toast.error('删除失败: ' + (e.response?.data?.detail || e.message))
    } finally {
        deleting.value = false
    }
}

// ── 补同步(逻辑不变) ──
const pendingChapterLabel = computed(() => {
    const items = syncStatus.value.pending_items || []
    if (!items.length) return '全部章节已同步'
    const preview = items.slice(0, 5).map(item => `第${item.id}章`).join('、')
    return items.length > 5 ? `待补同步：${preview} 等 ${items.length} 章` : `待补同步：${preview}`
})

const syncOverviewLabel = computed(() => {
    const continuous = syncStatus.value.last_continuous_synced_chapter || 0
    const highest = syncStatus.value.last_synced_chapter || 0
    if (!syncStatus.value.total_chapters) return '暂无章节'
    if (continuous === highest) {
        return `已同步 ${syncStatus.value.synced_chapters}/${syncStatus.value.total_chapters} 章，连续同步到第${continuous}章`
    }
    return `已同步 ${syncStatus.value.synced_chapters}/${syncStatus.value.total_chapters} 章，连续同步到第${continuous}章，最高同步到第${highest}章`
})

const skippedEmptyLabel = computed(() => {
    const count = Number(syncStatus.value.skipped_empty_chapters || 0)
    if (!count) return ''
    return `已跳过 ${count} 个空章节，空白章节不参与设定同步`
})

async function syncMissingChapters() {
    syncingMissing.value = true
    syncMessage.value = '正在启动补同步...'

    try {
        const { data } = await chaptersApi.syncMissing()
        if (!data.task_id) {
            syncMessage.value = data.message || '当前没有未同步章节'
            await loadSyncStatus()
            return
        }

        const taskId = data.task_id

        while (true) {
            await new Promise(resolve => setTimeout(resolve, 1200))
            const { data: status } = await chaptersApi.getTaskStatus(taskId)
            syncMessage.value = status.message || '正在补同步...'

            if (status.status === 'completed') {
                await chaptersApi.ackTask(taskId).catch(() => {})
                await Promise.all([loadCharacters(), loadSyncStatus(), loadRelationships()])
                const result = status.result || {}
                const failed = result.failed || []
                syncMessage.value = failed.length
                    ? `补同步完成：成功 ${result.synced?.length || 0} 章，失败 ${failed.length} 章`
                    : status.message || '补同步完成'
                break
            }

            if (status.status === 'error') {
                await chaptersApi.ackTask(taskId).catch(() => {})
                syncMessage.value = '补同步失败：' + (status.message || '未知错误')
                break
            }
        }
    } catch (e) {
        syncMessage.value = '补同步失败：' + (e.response?.data?.detail || e.message)
    } finally {
        syncingMissing.value = false
    }
}

// ── 生命周期 ──
function handleKeydown(e) {
    if (e.key === 'Escape') {
        if (drawerOpen.value) closeDrawer()
        else if (showCreateModal.value) showCreateModal.value = false
    }
}

watch(activeTab, () => {
    searchText.value = ''
    if (isSingleTab.value) loadDoc()
})

onMounted(async () => {
    window.addEventListener('keydown', handleKeydown)
    await Promise.all([loadCharacters(), loadSyncStatus(), loadRelationships()])
    if (isSingleTab.value) loadDoc()
})

onUnmounted(() => {
    window.removeEventListener('keydown', handleKeydown)
})

watch(() => projectStore.projectRoot, async (newRoot, oldRoot) => {
    if (!newRoot || newRoot === oldRoot) return
    closeDrawer()
    docContent.value = ''
    syncMessage.value = ''
    await Promise.all([loadCharacters(), loadSyncStatus(), loadRelationships()])
    if (isSingleTab.value) loadDoc()
})
</script>

<template>
    <div class="character-view">
        <header class="page-header">
            <div class="header-left">
                <h1>世界观管理</h1>
                <p class="subtitle">角色、宝物、功法、势力、地点的设定档案，AI 写作时自动引用</p>
            </div>
            <div class="header-actions">
                <button class="btn btn-secondary" @click="syncMissingChapters" :disabled="syncingMissing || !syncStatus.pending_chapters">
                    <RefreshCw :size="15" :stroke-width="1.75" :class="{ spinning: syncingMissing }" />
                    {{ syncingMissing ? '补同步中...' : '补同步章节' }}
                </button>
                <button class="btn btn-primary" @click="showCreateModal = true">
                    <Plus :size="15" :stroke-width="2" />
                    新建角色
                </button>
            </div>
        </header>

        <!-- 同步状态条 -->
        <div class="sync-bar">
            <div class="sync-main">
                <span class="sync-dot" :class="syncStatus.pending_chapters ? 'is-pending' : 'is-ok'"></span>
                <span class="sync-text">{{ syncOverviewLabel }}</span>
                <span class="sync-sep" aria-hidden="true"></span>
                <span class="sync-text muted">{{ syncMessage || pendingChapterLabel }}</span>
            </div>
            <button
                v-if="syncStatus.chapter_items?.length"
                class="sync-toggle-btn"
                @click="syncListExpanded = !syncListExpanded"
            >
                {{ syncListExpanded ? '收起详情' : `章节详情（${syncStatus.chapter_items.length}）` }}
                <ChevronRight :size="12" :stroke-width="2" class="toggle-arrow" :class="{ expanded: syncListExpanded }" />
            </button>
        </div>
        <p v-if="skippedEmptyLabel" class="sync-hint">{{ skippedEmptyLabel }}</p>
        <div v-if="syncListExpanded && syncStatus.chapter_items?.length" class="sync-chapter-list">
            <span
                v-for="item in syncStatus.chapter_items"
                :key="item.id"
                :class="['sync-chip', item.synced ? 'is-synced' : 'is-pending']"
            >
                第{{ item.id }}章 {{ item.synced ? '已同步' : '未同步' }}
            </span>
        </div>

        <!-- 分类 chips + 搜索 -->
        <div class="filter-row">
            <div class="tabs" role="tablist">
                <button
                    v-for="tab in tabsConfig"
                    :key="tab.key"
                    role="tab"
                    :aria-selected="activeTab === tab.key"
                    :class="{ active: activeTab === tab.key }"
                    @click="activeTab = tab.key"
                >
                    <span v-if="tab.dot" class="tab-dot" :style="{ background: tab.dot }"></span>
                    <component v-else-if="tab.icon" :is="tab.icon" :size="13" :stroke-width="1.75" />
                    {{ tab.key }}
                    <span v-if="!tab.single" class="count tnum">{{ (categories[tab.key] || []).length }}</span>
                </button>
            </div>
            <div v-if="!isSingleTab" class="search-wrap">
                <Search :size="14" :stroke-width="1.75" class="search-icon" />
                <input v-model="searchText" class="search-input" placeholder="搜索名称..." />
                <button v-if="searchText" class="search-clear" @click="searchText = ''" aria-label="清空搜索">
                    <X :size="13" :stroke-width="2" />
                </button>
            </div>
        </div>

        <!-- ── 单文件文档视图 ── -->
        <div v-if="isSingleTab" class="doc-view">
            <div class="doc-head">
                <div class="doc-title">
                    <component :is="activeTabConfig.icon" :size="16" :stroke-width="1.75" />
                    <span>{{ singleItem?.name || activeTab }}</span>
                </div>
                <div class="doc-actions">
                    <template v-if="docEditing">
                        <button class="btn btn-ghost btn-sm" @click="docEditing = false">取消</button>
                        <button class="btn btn-primary btn-sm" @click="saveDoc" :disabled="docSaving">
                            {{ docSaving ? '保存中...' : '保存' }}
                        </button>
                    </template>
                    <button v-else class="btn btn-secondary btn-sm" @click="startDocEdit" :disabled="docLoading || !singleItem">
                        <Pencil :size="13" :stroke-width="1.75" />
                        编辑
                    </button>
                </div>
            </div>
            <div v-if="docLoading" class="doc-body">
                <div class="skeleton sk-line" v-for="n in 6" :key="n" :style="{ width: (95 - n * 9) + '%' }"></div>
            </div>
            <div v-else-if="docEditing" class="doc-body doc-body-edit">
                <textarea v-model="docText" class="doc-editor" placeholder="编辑档案..."></textarea>
            </div>
            <div v-else-if="docContent" class="doc-body md-render" v-html="docHtml"></div>
            <div v-else class="doc-body doc-empty">
                <FileText :size="32" :stroke-width="1.25" />
                <p>该档案暂无内容</p>
                <button class="btn btn-secondary btn-sm" @click="startDocEdit" :disabled="!singleItem">开始填写</button>
            </div>
        </div>

        <!-- ── 卡片墙 ── -->
        <div v-else class="card-area">
            <template v-if="loading">
                <div class="cards-grid">
                    <div v-for="n in 6" :key="n" class="skeleton sk-card"></div>
                </div>
            </template>

            <div v-else-if="filteredList.length === 0" class="empty">
                <component :is="activeTabConfig.icon || Users" :size="36" :stroke-width="1.25" class="empty-icon" />
                <template v-if="searchText">
                    <p>没有匹配「{{ searchText }}」的档案</p>
                    <button class="btn btn-secondary btn-sm" @click="searchText = ''">清空搜索</button>
                </template>
                <template v-else>
                    <p>暂无{{ activeTab }}档案</p>
                    <p class="empty-hint">写作时 AI 会自动提取设定{{ isCharTab ? '，也可以手动新建' : '' }}</p>
                    <button v-if="isCharTab" class="btn btn-primary btn-sm" @click="newCharCategory = activeTab; showCreateModal = true">
                        <Plus :size="14" :stroke-width="2" />
                        新建{{ activeTab.replace('角色', '') }}角色
                    </button>
                </template>
            </div>

            <!-- 角色卡 -->
            <div v-else-if="isCharTab" class="cards-grid">
                <div
                    v-for="item in filteredList"
                    :key="item.path"
                    class="p-card"
                    role="button"
                    tabindex="0"
                    @click="openDrawer(item)"
                    @keydown.enter="openDrawer(item)"
                >
                    <div class="p-card-top">
                        <span class="cat-dot" :style="{ background: catDotColor[metaOf(item.name)?.category || activeTab] }"></span>
                        <span class="p-name">{{ item.name }}</span>
                        <span v-if="metaOf(item.name)?.isProtagonist" class="badge badge-protag">主角</span>
                        <span v-if="metaOf(item.name)?.dead" class="badge badge-dead">身故</span>
                        <button class="p-delete" title="删除档案" aria-label="删除档案" @click.stop="confirmDelete(item)">
                            <Trash2 :size="14" :stroke-width="1.75" />
                        </button>
                    </div>
                    <div v-if="metaOf(item.name)?.relations?.length" class="p-rels">
                        <div v-for="r in metaOf(item.name).relations.slice(0, 2)" :key="r.name" class="p-rel">
                            <span class="rel-dot" :style="{ background: catDotColor[r.category] || 'var(--cat-un-dot)' }"></span>
                            <span class="p-rel-name">{{ r.name }}</span>
                            <span class="p-rel-label">{{ r.label }}</span>
                        </div>
                    </div>
                    <div v-else class="p-rels-empty">{{ graphLoaded ? '暂无关系记录' : '关系数据加载中' }}</div>
                    <div class="p-card-foot">
                        <span v-if="metaOf(item.name)" class="p-count tnum">关系 {{ metaOf(item.name).relationCount }}</span>
                        <span class="p-open">查看档案 <ChevronRight :size="12" :stroke-width="2" /></span>
                    </div>
                </div>
            </div>

            <!-- 库卡(宝物/功法/势力/地点) -->
            <div v-else class="cards-grid lib-grid">
                <div
                    v-for="item in filteredList"
                    :key="item.path"
                    class="p-card lib-card"
                    role="button"
                    tabindex="0"
                    @click="openDrawer(item)"
                    @keydown.enter="openDrawer(item)"
                >
                    <span class="lib-icon">
                        <component :is="libIcon[activeTab] || FileText" :size="16" :stroke-width="1.5" />
                    </span>
                    <span class="p-name">{{ item.name }}</span>
                    <button class="p-delete" title="删除档案" aria-label="删除档案" @click.stop="confirmDelete(item)">
                        <Trash2 :size="14" :stroke-width="1.75" />
                    </button>
                    <ChevronRight :size="14" :stroke-width="1.75" class="lib-arrow" />
                </div>
            </div>
        </div>

        <!-- ── 详情抽屉 ── -->
        <div class="drawer-overlay" :class="{ active: drawerOpen }" @click="closeDrawer"></div>
        <aside class="detail-drawer" :class="{ open: drawerOpen }" role="dialog" aria-modal="true">
            <template v-if="drawerItem">
                <div class="drawer-head">
                    <div class="drawer-title-row">
                        <span v-if="isCharTab" class="cat-dot lg" :style="{ background: catDotColor[metaOf(drawerItem.name)?.category || activeTab] }"></span>
                        <span v-else class="lib-icon sm">
                            <component :is="libIcon[activeTab] || FileText" :size="14" :stroke-width="1.5" />
                        </span>
                        <h2 class="drawer-name">{{ drawerItem.name }}</h2>
                        <span v-if="metaOf(drawerItem.name)?.isProtagonist" class="badge badge-protag">主角</span>
                        <span v-if="metaOf(drawerItem.name)?.dead" class="badge badge-dead">身故</span>
                    </div>
                    <button class="drawer-close" @click="closeDrawer" aria-label="关闭">
                        <X :size="16" :stroke-width="1.75" />
                    </button>
                </div>

                <!-- 编辑态 -->
                <div v-if="editMode" class="drawer-body drawer-body-edit">
                    <textarea v-model="editText" class="drawer-editor" placeholder="编辑档案源文件..."></textarea>
                </div>

                <!-- 查看态 -->
                <div v-else class="drawer-body">
                    <template v-if="isCharTab">
                        <div v-if="profileLoading" class="drawer-section">
                            <div class="skeleton sk-line" v-for="n in 4" :key="n" :style="{ width: (90 - n * 12) + '%' }"></div>
                        </div>
                        <template v-else>
                            <div v-if="profileRows.length" class="drawer-section">
                                <h4 class="section-label">基本信息</h4>
                                <div class="info-grid">
                                    <div v-for="row in profileRows" :key="row.label" class="info-cell">
                                        <span class="info-label">{{ row.label }}</span>
                                        <span class="info-value">{{ row.value }}</span>
                                    </div>
                                </div>
                            </div>

                            <div v-if="metaOf(drawerItem.name)?.relations?.length" class="drawer-section">
                                <h4 class="section-label">关系 <span class="tnum">{{ metaOf(drawerItem.name).relationCount }}</span></h4>
                                <div class="rel-list">
                                    <div v-for="r in metaOf(drawerItem.name).relations" :key="r.name + r.label" class="rel-row">
                                        <span class="rel-dot" :style="{ background: catDotColor[r.category] || 'var(--cat-un-dot)' }"></span>
                                        <span class="rel-row-name">{{ r.name }}</span>
                                        <span class="rel-row-label">{{ r.label }}</span>
                                    </div>
                                </div>
                            </div>

                            <div v-for="group in profileTagGroups" :key="group.label" class="drawer-section">
                                <h4 class="section-label">{{ group.label }}</h4>
                                <div class="tag-wrap">
                                    <span v-for="t in group.items" :key="tagName(t)" class="tag-chip" :title="tagDesc(t)">
                                        <span class="rel-dot" :style="{ background: group.dot }"></span>
                                        {{ tagName(t) }}
                                    </span>
                                </div>
                            </div>
                        </template>
                    </template>

                    <div class="drawer-section">
                        <h4 class="section-label">档案原文</h4>
                        <div v-if="fileLoading" class="md-box">
                            <div class="skeleton sk-line" v-for="n in 5" :key="n" :style="{ width: (95 - n * 10) + '%' }"></div>
                        </div>
                        <div v-else-if="fileContent" class="md-box md-render" v-html="fileHtml"></div>
                        <div v-else class="md-box md-empty">档案为空，点击下方「编辑源文件」填写</div>
                    </div>
                </div>

                <div class="drawer-foot">
                    <template v-if="editMode">
                        <button class="btn btn-ghost" @click="editMode = false">取消</button>
                        <button class="btn btn-primary" @click="saveEdit" :disabled="saving">
                            {{ saving ? '保存中...' : '保存' }}
                        </button>
                    </template>
                    <template v-else>
                        <button class="btn btn-danger-ghost" @click="confirmDelete(drawerItem)">
                            <Trash2 :size="14" :stroke-width="1.75" />
                            删除
                        </button>
                        <button class="btn btn-secondary" @click="startEdit" :disabled="fileLoading">
                            <Pencil :size="14" :stroke-width="1.75" />
                            编辑源文件
                        </button>
                    </template>
                </div>
            </template>
        </aside>

        <!-- 新建角色弹窗 -->
        <div v-if="showCreateModal" class="modal-overlay" @click.self="showCreateModal = false">
            <div class="modal">
                <h3>新建角色</h3>
                <div class="form-group">
                    <label>角色名</label>
                    <input v-model="newCharName" placeholder="输入角色名" @keydown.enter="createCharacter" />
                </div>
                <div class="form-group">
                    <label>分类</label>
                    <select v-model="newCharCategory">
                        <option value="主要角色">主要角色</option>
                        <option value="次要角色">次要角色</option>
                        <option value="反派角色">反派角色</option>
                    </select>
                </div>
                <div class="modal-actions">
                    <button class="btn btn-secondary" @click="showCreateModal = false">取消</button>
                    <button class="btn btn-primary" @click="createCharacter">创建</button>
                </div>
            </div>
        </div>

        <!-- 删除确认 -->
        <ConfirmDialog
            :isOpen="!!deleteTarget"
            title="删除档案"
            :message="`确定删除「${deleteTarget?.name}」吗？\n此操作不可恢复。`"
            confirmText="确认删除"
            type="danger"
            :loading="deleting"
            @confirm="doDelete"
            @cancel="deleteTarget = null"
        />
    </div>
</template>

<style scoped>
.character-view {
    max-width: 1400px;
    margin: 0 auto;
    padding: 1.5rem 2rem 3rem;
    min-height: 100%;
    display: flex;
    flex-direction: column;
}

/* ── 头部 ── */
.page-header {
    display: flex;
    justify-content: space-between;
    align-items: flex-start;
    gap: 1.5rem;
    margin-bottom: 1rem;
}

.header-left h1 {
    font-size: 1.375rem;
    font-weight: 600;
    letter-spacing: -0.01em;
    color: var(--ink-primary);
    margin: 0 0 0.25rem;
}

.subtitle {
    color: var(--ink-muted);
    font-size: 0.875rem;
    margin: 0;
}

.header-actions { display: flex; align-items: center; gap: 0.625rem; flex-shrink: 0; }

.spinning { animation: spin 1s linear infinite; }
@keyframes spin { to { transform: rotate(360deg); } }
@media (prefers-reduced-motion: reduce) {
    .spinning { animation: none; }
}

/* ── 同步状态条 ── */
.sync-bar {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 1rem;
    padding: 0.55rem 0.875rem;
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: var(--radius-md);
    margin-bottom: 0.75rem;
}

.sync-main { display: flex; align-items: center; gap: 0.625rem; min-width: 0; flex-wrap: wrap; }

.sync-dot { width: 8px; height: 8px; border-radius: 50%; flex-shrink: 0; }
.sync-dot.is-ok { background: var(--success); }
.sync-dot.is-pending { background: var(--warning); }

.sync-text { font-size: 0.8125rem; color: var(--ink-secondary); }
.sync-text.muted { color: var(--ink-muted); }
.sync-sep { width: 1px; height: 0.875rem; background: var(--border); flex-shrink: 0; }

.sync-toggle-btn {
    display: inline-flex;
    align-items: center;
    gap: 0.3rem;
    background: none;
    border: none;
    color: var(--ink-muted);
    font-size: 0.8125rem;
    cursor: pointer;
    padding: 0.25rem 0.375rem;
    border-radius: var(--radius-sm);
    flex-shrink: 0;
}
.sync-toggle-btn:hover { color: var(--ink-primary); background: var(--hover); }

.toggle-arrow { transition: transform var(--dur-fast) var(--ease-standard); }
.toggle-arrow.expanded { transform: rotate(90deg); }

.sync-hint { margin: 0 0 0.5rem; color: var(--ink-muted); font-size: 0.8125rem; }

.sync-chapter-list {
    display: flex;
    flex-wrap: wrap;
    gap: 0.45rem;
    margin-bottom: 0.75rem;
    max-height: 8.5rem;
    overflow-y: auto;
}

.sync-chip {
    display: inline-flex;
    align-items: center;
    padding: 0.2rem 0.55rem;
    border-radius: var(--radius-sm);
    font-size: 0.75rem;
    border: 1px solid var(--border);
}
.sync-chip.is-synced { color: var(--success); background: var(--success-tint); border-color: transparent; }
.sync-chip.is-pending { color: var(--warning-strong); background: var(--warning-tint); border-color: transparent; }

/* ── 分类 chips + 搜索 ── */
.filter-row {
    display: flex;
    align-items: center;
    gap: 0.875rem;
    padding-bottom: 0.875rem;
    margin-bottom: 1rem;
    border-bottom: 1px solid var(--border);
}

.tabs {
    display: flex;
    gap: 0.25rem;
    overflow-x: auto;
    flex: 1;
    min-width: 0;
    scrollbar-width: none;
}
.tabs::-webkit-scrollbar { display: none; }

.tabs button {
    display: inline-flex;
    align-items: center;
    gap: 0.375rem;
    background: none;
    border: 1px solid transparent;
    padding: 0.4rem 0.7rem;
    cursor: pointer;
    border-radius: var(--radius-md);
    color: var(--ink-secondary);
    font-size: 0.8125rem;
    font-weight: 500;
    white-space: nowrap;
    transition: background-color var(--dur-fast) var(--ease-standard), color var(--dur-fast) var(--ease-standard);
}
.tabs button:hover { background: var(--hover); color: var(--ink-primary); }
.tabs button.active {
    background: var(--primary-tint);
    color: var(--primary-on-tint);
}

.tab-dot { width: 7px; height: 7px; border-radius: 50%; flex-shrink: 0; }

.count {
    font-family: var(--font-mono);
    font-feature-settings: "tnum";
    background: var(--surface);
    color: var(--ink-muted);
    padding: 0 0.4rem;
    border-radius: var(--radius-sm);
    font-size: 0.6875rem;
    font-weight: 500;
}
.tabs button.active .count { background: var(--card); color: var(--primary-on-tint); }

.search-wrap {
    position: relative;
    display: flex;
    align-items: center;
    flex-shrink: 0;
}

.search-icon { position: absolute; left: 0.6rem; color: var(--ink-muted); pointer-events: none; }

.search-input {
    width: 190px;
    padding: 0.4rem 1.75rem 0.4rem 2rem;
    border: 1px solid var(--border);
    border-radius: var(--radius-md);
    background: var(--surface);
    color: var(--ink-primary);
    font-size: 0.8125rem;
    outline: none;
    transition: border-color var(--dur-fast) var(--ease-standard), background-color var(--dur-fast) var(--ease-standard), box-shadow var(--dur-fast) var(--ease-standard);
}
.search-input:focus {
    border-color: var(--primary);
    background: var(--card);
    box-shadow: 0 0 0 3px var(--primary-tint);
}
.search-input::placeholder { color: var(--ink-muted); }

.search-clear {
    position: absolute;
    right: 0.4rem;
    display: flex;
    align-items: center;
    justify-content: center;
    width: 18px; height: 18px;
    border: none;
    background: var(--hover);
    color: var(--ink-muted);
    border-radius: 50%;
    cursor: pointer;
}
.search-clear:hover { color: var(--ink-primary); }

/* ── 卡片墙 ── */
.card-area { flex: 1; }

.cards-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(250px, 1fr));
    gap: 0.75rem;
    align-content: start;
}

.p-card {
    background: var(--card);
    border: 1px solid var(--border);
    border-radius: var(--radius-lg);
    padding: 0.875rem 1rem;
    cursor: pointer;
    transition: border-color var(--dur-fast) var(--ease-standard), box-shadow var(--dur-fast) var(--ease-standard);
    display: flex;
    flex-direction: column;
    gap: 0.55rem;
    min-width: 0;
}

.p-card:hover {
    border-color: var(--border-strong);
    box-shadow: var(--shadow-md);
}

.p-card:focus-visible {
    outline: 2px solid var(--primary);
    outline-offset: 2px;
}

.p-card-top {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    min-width: 0;
}

.cat-dot { width: 8px; height: 8px; border-radius: 50%; flex-shrink: 0; }
.cat-dot.lg { width: 10px; height: 10px; }

.p-name {
    font-size: 0.9375rem;
    font-weight: 600;
    color: var(--ink-primary);
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
    min-width: 0;
}

.badge {
    flex-shrink: 0;
    font-size: 0.6875rem;
    font-weight: 600;
    padding: 0.1rem 0.4rem;
    border-radius: var(--radius-sm);
}
.badge-protag { color: var(--warning-strong); background: var(--warning-tint); }
.badge-dead { color: var(--ink-muted); background: var(--surface); border: 1px solid var(--border); }

.p-delete {
    margin-left: auto;
    flex-shrink: 0;
    background: none;
    border: none;
    color: var(--ink-muted);
    cursor: pointer;
    padding: 0.25rem;
    border-radius: var(--radius-sm);
    display: flex;
    align-items: center;
    opacity: 0;
    transition: opacity var(--dur-fast) var(--ease-standard), color var(--dur-fast) var(--ease-standard), background-color var(--dur-fast) var(--ease-standard);
}
.p-card:hover .p-delete,
.p-delete:focus-visible { opacity: 1; }
.p-delete:hover { color: var(--danger); background: var(--danger-tint); }

.p-rels {
    display: flex;
    flex-direction: column;
    gap: 0.3rem;
}

.p-rel {
    display: flex;
    align-items: center;
    gap: 0.4rem;
    font-size: 0.8125rem;
    min-width: 0;
}

.rel-dot { width: 5px; height: 5px; border-radius: 50%; flex-shrink: 0; }

.p-rel-name { color: var(--ink-primary); font-weight: 500; flex-shrink: 0; }

.p-rel-label {
    color: var(--ink-muted);
    font-size: 0.75rem;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
    margin-left: auto;
}

.p-rels-empty {
    font-size: 0.8125rem;
    color: var(--ink-muted);
    opacity: 0.75;
    padding: 0.1rem 0;
}

.p-card-foot {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding-top: 0.55rem;
    border-top: 1px solid var(--border);
}

.p-count {
    font-family: var(--font-mono);
    font-feature-settings: "tnum";
    font-size: 0.75rem;
    color: var(--ink-muted);
}

.p-open {
    display: inline-flex;
    align-items: center;
    gap: 0.15rem;
    font-size: 0.75rem;
    font-weight: 500;
    color: var(--primary-text);
    opacity: 0;
    transform: translateX(-3px);
    transition: opacity var(--dur-fast) var(--ease-standard), transform var(--dur-fast) var(--ease-standard);
}
.p-card:hover .p-open { opacity: 1; transform: translateX(0); }

/* 库卡 */
.lib-grid { grid-template-columns: repeat(auto-fill, minmax(210px, 1fr)); }

.lib-card {
    flex-direction: row;
    align-items: center;
    gap: 0.625rem;
    padding: 0.75rem 0.875rem;
}

.lib-icon {
    display: flex;
    align-items: center;
    justify-content: center;
    width: 30px; height: 30px;
    flex-shrink: 0;
    border-radius: var(--radius-md);
    background: var(--surface);
    border: 1px solid var(--border);
    color: var(--ink-secondary);
}
.lib-icon.sm { width: 24px; height: 24px; }

.lib-card .p-name { font-size: 0.875rem; flex: 1; }

.lib-arrow {
    color: var(--ink-muted);
    flex-shrink: 0;
    opacity: 0.5;
}

/* ── 单文件文档视图 ── */
.doc-view {
    flex: 1;
    display: flex;
    flex-direction: column;
    background: var(--card);
    border: 1px solid var(--border);
    border-radius: var(--radius-lg);
    overflow: hidden;
    min-height: 320px;
}

.doc-head {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 1rem;
    padding: 0.75rem 1.25rem;
    border-bottom: 1px solid var(--border);
    flex-shrink: 0;
}

.doc-title {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    font-size: 0.9375rem;
    font-weight: 600;
    color: var(--ink-primary);
}
.doc-title svg { color: var(--ink-muted); }

.doc-actions { display: flex; align-items: center; gap: 0.5rem; }

.doc-body {
    flex: 1;
    overflow-y: auto;
    padding: 1.25rem 1.5rem;
}

.doc-body-edit { padding: 0.75rem; display: flex; }

.doc-editor {
    flex: 1;
    min-height: 360px;
    resize: none;
    padding: 1rem;
    border: 1px solid var(--border);
    border-radius: var(--radius-md);
    font-family: var(--font-mono);
    font-size: 0.875rem;
    line-height: 1.7;
    background: var(--surface);
    color: var(--ink-primary);
    outline: none;
}
.doc-editor:focus { border-color: var(--primary); background: var(--card); box-shadow: 0 0 0 3px var(--primary-tint); }

.doc-empty {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    gap: 0.75rem;
    color: var(--ink-muted);
    font-size: 0.875rem;
    padding: 3rem 1rem;
}

/* ── 空状态 / 骨架 ── */
.empty {
    display: flex;
    flex-direction: column;
    align-items: center;
    text-align: center;
    padding: 3.5rem 1rem;
    color: var(--ink-secondary);
    gap: 0.625rem;
    font-size: 0.9375rem;
}
.empty-hint { font-size: 0.8125rem; color: var(--ink-muted); margin: 0; }
.empty-icon { color: var(--ink-muted); opacity: 0.6; }
.empty .btn { margin-top: 0.375rem; }

.sk-line { height: 0.875rem; margin-bottom: 0.625rem; }
.sk-card { height: 118px; border-radius: var(--radius-lg); }

/* ── 详情抽屉 ── */
.drawer-overlay {
    position: fixed;
    inset: 0;
    background: rgb(15 17 21 / 0.45);
    z-index: var(--z-modal-backdrop);
    opacity: 0;
    pointer-events: none;
    transition: opacity var(--dur-base) ease;
}
.drawer-overlay.active { opacity: 1; pointer-events: auto; }

.detail-drawer {
    position: fixed;
    top: 0; right: 0; bottom: 0;
    width: 520px;
    max-width: 92vw;
    background: var(--card);
    border-left: 1px solid var(--border);
    border-radius: var(--radius-lg) 0 0 var(--radius-lg);
    z-index: var(--z-modal);
    transform: translateX(100%);
    transition: transform 0.28s var(--ease-emerge);
    display: flex;
    flex-direction: column;
}
.detail-drawer.open {
    transform: translateX(0);
    box-shadow: var(--shadow-xl);
}

.drawer-head {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 1rem;
    padding: 1rem 1.25rem;
    border-bottom: 1px solid var(--border);
    flex-shrink: 0;
}

.drawer-title-row {
    display: flex;
    align-items: center;
    gap: 0.55rem;
    min-width: 0;
}

.drawer-name {
    font-size: 1.125rem;
    font-weight: 600;
    color: var(--ink-primary);
    margin: 0;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
}

.drawer-close {
    flex-shrink: 0;
    display: flex;
    align-items: center;
    justify-content: center;
    width: 30px; height: 30px;
    background: transparent;
    border: 1px solid var(--border);
    border-radius: var(--radius-md);
    color: var(--ink-muted);
    cursor: pointer;
    transition: color var(--dur-fast) var(--ease-standard), background-color var(--dur-fast) var(--ease-standard);
}
.drawer-close:hover { color: var(--ink-primary); background: var(--hover); }

.drawer-body {
    flex: 1;
    overflow-y: auto;
    padding: 1.1rem 1.25rem;
    display: flex;
    flex-direction: column;
    gap: 1.25rem;
}

.drawer-body-edit { padding: 0.75rem; }

.drawer-editor {
    flex: 1;
    width: 100%;
    resize: none;
    padding: 1rem;
    border: 1px solid var(--border);
    border-radius: var(--radius-md);
    font-family: var(--font-mono);
    font-size: 0.875rem;
    line-height: 1.7;
    background: var(--surface);
    color: var(--ink-primary);
    outline: none;
}
.drawer-editor:focus { border-color: var(--primary); background: var(--card); box-shadow: 0 0 0 3px var(--primary-tint); }

.drawer-section { display: flex; flex-direction: column; gap: 0.625rem; }

.section-label {
    font-size: 0.75rem;
    font-weight: 600;
    color: var(--ink-muted);
    margin: 0;
    padding-bottom: 0.4rem;
    border-bottom: 1px solid var(--border);
    display: flex;
    align-items: center;
    gap: 0.375rem;
}

.info-grid {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 0.5rem;
}

.info-cell {
    display: flex;
    flex-direction: column;
    gap: 0.15rem;
    padding: 0.55rem 0.7rem;
    background: var(--surface);
    border-radius: var(--radius-md);
    min-width: 0;
}

.info-label { font-size: 0.6875rem; color: var(--ink-muted); }
.info-value {
    font-size: 0.8125rem;
    font-weight: 500;
    color: var(--ink-primary);
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
}

.rel-list { display: flex; flex-direction: column; }

.rel-row {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    padding: 0.4rem 0.1rem;
    font-size: 0.8125rem;
    border-bottom: 1px dashed var(--border);
    min-width: 0;
}
.rel-row:last-child { border-bottom: none; }

.rel-row-name { color: var(--ink-primary); font-weight: 500; flex-shrink: 0; }
.rel-row-label {
    color: var(--ink-muted);
    font-size: 0.75rem;
    margin-left: auto;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
}

.tag-wrap { display: flex; flex-wrap: wrap; gap: 0.4rem; }

.tag-chip {
    display: inline-flex;
    align-items: center;
    gap: 0.35rem;
    padding: 0.25rem 0.6rem;
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: var(--radius-sm);
    font-size: 0.75rem;
    font-weight: 500;
    color: var(--ink-secondary);
}

.md-box {
    background: var(--surface);
    border-radius: var(--radius-md);
    padding: 1rem 1.1rem;
}

.md-empty { color: var(--ink-muted); font-size: 0.8125rem; }

.drawer-foot {
    display: flex;
    justify-content: flex-end;
    align-items: center;
    gap: 0.625rem;
    padding: 0.875rem 1.25rem;
    border-top: 1px solid var(--border);
    flex-shrink: 0;
}

.drawer-foot .btn-danger-ghost {
    margin-right: auto;
    display: inline-flex;
    align-items: center;
    gap: 0.35rem;
    color: var(--danger);
    background: none;
    border: 1px solid transparent;
    padding: 0.5rem 0.875rem;
    border-radius: var(--radius-md);
    cursor: pointer;
    font-size: 0.875rem;
    font-weight: 500;
}
.drawer-foot .btn-danger-ghost:hover { background: var(--danger-tint); }

/* ── Markdown 渲染 ── */
.md-render { font-size: 0.875rem; line-height: 1.75; color: var(--ink-secondary); }
.md-render :deep(p) { margin: 0 0 0.625rem; }
.md-render :deep(p:last-child) { margin-bottom: 0; }
.md-render :deep(h1),
.md-render :deep(h2),
.md-render :deep(h3),
.md-render :deep(h4) {
    font-size: 0.9375rem;
    font-weight: 600;
    color: var(--ink-primary);
    margin: 1rem 0 0.5rem;
}
.md-render :deep(h1:first-child),
.md-render :deep(h2:first-child),
.md-render :deep(h3:first-child) { margin-top: 0; }
.md-render :deep(ul),
.md-render :deep(ol) { margin: 0.25rem 0 0.625rem; padding-left: 1.375rem; }
.md-render :deep(li) { margin-bottom: 0.25rem; }
.md-render :deep(strong) { font-weight: 600; color: var(--ink-primary); }
.md-render :deep(code) {
    font-family: var(--font-mono);
    font-size: 0.85em;
    background: var(--hover);
    border-radius: var(--radius-sm);
    padding: 0.1em 0.35em;
}
.md-render :deep(pre) {
    background: var(--hover);
    border-radius: var(--radius-md);
    padding: 0.75rem 1rem;
    overflow-x: auto;
    margin: 0.5rem 0 0.75rem;
}
.md-render :deep(pre code) { background: none; padding: 0; }
.md-render :deep(blockquote) {
    margin: 0.5rem 0;
    padding-left: 0.875rem;
    border-left: 3px solid var(--border-strong);
    color: var(--ink-muted);
}
.md-render :deep(hr) { border: none; border-top: 1px solid var(--border); margin: 0.875rem 0; }
.md-render :deep(table) { border-collapse: collapse; margin: 0.5rem 0; max-width: 100%; }
.md-render :deep(th),
.md-render :deep(td) { border: 1px solid var(--border); padding: 0.35rem 0.6rem; font-size: 0.8125rem; }

/* ── 弹窗 ── */
.modal-overlay {
    position: fixed;
    inset: 0;
    background: rgb(15 17 21 / 0.45);
    display: flex;
    align-items: center;
    justify-content: center;
    z-index: var(--z-modal-backdrop);
}

.modal {
    background: var(--card);
    padding: 1.5rem;
    border-radius: var(--radius-lg);
    width: 400px;
    border: 1px solid var(--border);
    box-shadow: var(--shadow-xl);
}

.modal h3 {
    margin: 0 0 1.25rem;
    font-size: 1.125rem;
    font-weight: 600;
    color: var(--ink-primary);
}

.form-group { margin-bottom: 1rem; }
.form-group label {
    display: block;
    margin-bottom: 0.4rem;
    font-size: 0.8125rem;
    font-weight: 500;
    color: var(--ink-secondary);
}
.form-group input, .form-group select {
    width: 100%;
    padding: 0.55rem 0.85rem;
    border: 1px solid var(--border);
    border-radius: var(--radius-md);
    background: var(--surface);
    color: var(--ink-primary);
    font-size: 0.9375rem;
    outline: none;
    box-sizing: border-box;
    transition: border-color var(--dur-fast) var(--ease-standard), box-shadow var(--dur-fast) var(--ease-standard), background-color var(--dur-fast) var(--ease-standard);
}
.form-group input:focus, .form-group select:focus {
    border-color: var(--primary);
    background: var(--card);
    box-shadow: 0 0 0 3px var(--primary-tint);
}

.modal-actions { display: flex; justify-content: flex-end; gap: 0.625rem; margin-top: 1.5rem; }

/* ── 响应式 ── */
@media (max-width: 960px) {
    .character-view { padding: 1rem; }
    .page-header { flex-direction: column; }
    .filter-row { flex-direction: column; align-items: stretch; }
    .search-wrap { width: 100%; }
    .search-input { width: 100%; }
    .cards-grid { grid-template-columns: 1fr 1fr; }
    .lib-grid { grid-template-columns: 1fr; }
    .info-grid { grid-template-columns: 1fr; }
    .detail-drawer { width: 100vw; max-width: 100vw; border-radius: 0; }
}

@media (max-width: 640px) {
    .cards-grid { grid-template-columns: 1fr; }
}
</style>
