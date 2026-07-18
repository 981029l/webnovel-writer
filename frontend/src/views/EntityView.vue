<script setup>
// Copyright (c) 2026 左岚. All rights reserved.
// EntityView.vue - 全景设定集(chips 筛选 + 卡片墙 + 详情抽屉)
import { ref, onMounted, onUnmounted, computed } from 'vue'
import { Inbox, Search, X, ChevronRight } from 'lucide-vue-next'
import { entitiesApi } from '../api'
import { marked } from 'marked'
import DOMPurify from 'dompurify'

const entities = ref([])
const loading = ref(true)
const selectedType = ref('all')
const entityTypes = ref([])
const searchText = ref('')

// Drawer state
const selectedEntity = ref(null)
const isDrawerOpen = ref(false)

const typeMeta = {
    character: { label: '角色', dot: 'var(--cat-main-dot)' },
    location: { label: '地点', dot: 'var(--cat-sec-dot)' },
    item: { label: '物品', dot: 'var(--warning)' },
    faction: { label: '势力', dot: 'var(--success)' },
    skill: { label: '招式/技能', dot: 'var(--cat-vil-dot)' },
    foreshadowing: { label: '伏笔', dot: 'var(--primary)' },
}

function typeLabel(type) {
    return typeMeta[type]?.label || type || '未知'
}

function typeDot(type) {
    return typeMeta[type]?.dot || 'var(--cat-un-dot)'
}

const typeChips = computed(() => {
    const chips = [{ id: 'all', label: '全部', count: entities.value.length, dot: null }]
    entityTypes.value.forEach(t => {
        const id = t.id || t
        chips.push({
            id,
            label: t.name || typeLabel(id),
            count: entities.value.filter(e => e.type === id).length,
            dot: typeDot(id),
        })
    })
    return chips
})

const filteredEntities = computed(() => {
    let list = entities.value
    if (selectedType.value !== 'all') {
        list = list.filter(e => e.type === selectedType.value)
    }
    const kw = searchText.value.trim().toLowerCase()
    if (kw) {
        list = list.filter(e =>
            (e.name || '').toLowerCase().includes(kw) ||
            (e.description || '').toLowerCase().includes(kw)
        )
    }
    return list
})

function renderMd(text) {
    if (!text) return ''
    return DOMPurify.sanitize(marked.parse(text, { breaks: true }))
}

const drawerHtml = computed(() => renderMd(selectedEntity.value?.description || ''))

async function loadEntities() {
    loading.value = true
    try {
        const { data } = await entitiesApi.getAll({})
        entities.value = data.entities || []
    } catch (e) {
        console.error('Failed to load entities:', e)
    } finally {
        loading.value = false
    }
}

async function loadTypes() {
    try {
        const { data } = await entitiesApi.getTypes()
        entityTypes.value = data.types || []
    } catch (e) {
        console.error('Failed to load types:', e)
    }
}

function openDrawer(entity) {
    selectedEntity.value = entity
    isDrawerOpen.value = true
}

function closeDrawer() {
    isDrawerOpen.value = false
    setTimeout(() => { if (!isDrawerOpen.value) selectedEntity.value = null }, 250)
}

function handleKeydown(e) {
    if (e.key === 'Escape' && isDrawerOpen.value) closeDrawer()
}

onMounted(async () => {
    window.addEventListener('keydown', handleKeydown)
    await loadTypes()
    await loadEntities()
})

onUnmounted(() => {
    window.removeEventListener('keydown', handleKeydown)
})
</script>

<template>
    <div class="entity-view">
        <header class="page-header">
            <div class="header-left">
                <h1>全景设定集</h1>
                <p class="subtitle">AI 从章节中自动提取的角色、地点、道具与伏笔档案</p>
            </div>
        </header>

        <!-- 类型 chips + 搜索 -->
        <div class="filter-row">
            <div class="type-chips" role="tablist">
                <button
                    v-for="chip in typeChips"
                    :key="chip.id"
                    role="tab"
                    :aria-selected="selectedType === chip.id"
                    :class="{ active: selectedType === chip.id }"
                    @click="selectedType = chip.id"
                >
                    <span v-if="chip.dot" class="chip-dot" :style="{ background: chip.dot }"></span>
                    {{ chip.label }}
                    <span class="count tnum">{{ chip.count }}</span>
                </button>
            </div>
            <div class="search-wrap">
                <Search :size="14" :stroke-width="1.75" class="search-icon" />
                <input v-model="searchText" class="search-input" placeholder="搜索名称或描述..." />
                <button v-if="searchText" class="search-clear" @click="searchText = ''" aria-label="清空搜索">
                    <X :size="13" :stroke-width="2" />
                </button>
            </div>
        </div>

        <!-- 加载骨架 -->
        <div v-if="loading" class="cards-grid">
            <div v-for="n in 6" :key="n" class="skeleton sk-card"></div>
        </div>

        <!-- 空状态 -->
        <div v-else-if="filteredEntities.length === 0" class="empty">
            <Inbox :size="36" :stroke-width="1.25" class="empty-icon" />
            <template v-if="searchText || selectedType !== 'all'">
                <p>没有匹配的设定条目</p>
                <button class="btn btn-secondary btn-sm" @click="searchText = ''; selectedType = 'all'">清空筛选</button>
            </template>
            <template v-else>
                <p>暂无设定数据</p>
                <p class="empty-hint">开始撰写章节后，AI 将自动从文字中提取实体信息</p>
            </template>
        </div>

        <!-- 卡片墙 -->
        <div v-else class="cards-grid">
            <div
                v-for="entity in filteredEntities"
                :key="entity.id"
                class="e-card"
                role="button"
                tabindex="0"
                @click="openDrawer(entity)"
                @keydown.enter="openDrawer(entity)"
            >
                <div class="e-card-top">
                    <span class="type-tag">
                        <span class="chip-dot" :style="{ background: typeDot(entity.type) }"></span>
                        {{ typeLabel(entity.type) }}
                    </span>
                    <span v-if="entity.first_appearance" class="chapter-tag tnum">{{ entity.first_appearance }}</span>
                </div>
                <h3 class="e-title">{{ entity.name }}</h3>
                <p class="e-desc">{{ entity.description || '暂无描述' }}</p>
                <div class="e-card-foot">
                    <span class="e-open">查看详情 <ChevronRight :size="12" :stroke-width="2" /></span>
                </div>
            </div>
        </div>

        <!-- 详情抽屉 -->
        <div class="drawer-overlay" :class="{ active: isDrawerOpen }" @click="closeDrawer"></div>
        <aside class="detail-drawer" :class="{ open: isDrawerOpen }" role="dialog" aria-modal="true">
            <template v-if="selectedEntity">
                <div class="drawer-head">
                    <div class="drawer-title-row">
                        <span class="type-tag">
                            <span class="chip-dot" :style="{ background: typeDot(selectedEntity.type) }"></span>
                            {{ typeLabel(selectedEntity.type) }}
                        </span>
                        <h2 class="drawer-name">{{ selectedEntity.name }}</h2>
                    </div>
                    <button class="drawer-close" @click="closeDrawer" aria-label="关闭">
                        <X :size="16" :stroke-width="1.75" />
                    </button>
                </div>

                <div class="drawer-body">
                    <div v-if="selectedEntity.first_appearance" class="drawer-section">
                        <h4 class="section-label">初次出现</h4>
                        <div class="info-cell">
                            <span class="info-value tnum">{{ selectedEntity.first_appearance }}</span>
                        </div>
                    </div>
                    <div class="drawer-section">
                        <h4 class="section-label">描述</h4>
                        <div v-if="selectedEntity.description" class="md-box md-render" v-html="drawerHtml"></div>
                        <div v-else class="md-box md-empty">暂无描述</div>
                    </div>
                </div>
            </template>
        </aside>
    </div>
</template>

<style scoped>
.entity-view {
    max-width: 1400px;
    margin: 0 auto;
    padding: 1.5rem 2rem 3rem;
    min-height: 100%;
    color: var(--ink-primary);
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

.subtitle { color: var(--ink-muted); font-size: 0.875rem; margin: 0; }

/* ── chips + 搜索 ── */
.filter-row {
    display: flex;
    align-items: center;
    gap: 0.875rem;
    padding-bottom: 0.875rem;
    margin-bottom: 1rem;
    border-bottom: 1px solid var(--border);
}

.type-chips {
    display: flex;
    gap: 0.25rem;
    overflow-x: auto;
    flex: 1;
    min-width: 0;
    scrollbar-width: none;
}
.type-chips::-webkit-scrollbar { display: none; }

.type-chips button {
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
.type-chips button:hover { background: var(--hover); color: var(--ink-primary); }
.type-chips button.active { background: var(--primary-tint); color: var(--primary-on-tint); }

.chip-dot { width: 7px; height: 7px; border-radius: 50%; flex-shrink: 0; }

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
.type-chips button.active .count { background: var(--card); color: var(--primary-on-tint); }

.search-wrap { position: relative; display: flex; align-items: center; flex-shrink: 0; }
.search-icon { position: absolute; left: 0.6rem; color: var(--ink-muted); pointer-events: none; }

.search-input {
    width: 210px;
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
.cards-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
    gap: 0.75rem;
    align-content: start;
}

.e-card {
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

.e-card:hover {
    border-color: var(--border-strong);
    box-shadow: var(--shadow-md);
}

.e-card:focus-visible {
    outline: 2px solid var(--primary);
    outline-offset: 2px;
}

.e-card-top {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 0.5rem;
}

.type-tag {
    display: inline-flex;
    align-items: center;
    gap: 0.35rem;
    font-size: 0.75rem;
    font-weight: 500;
    color: var(--ink-secondary);
    background: var(--surface);
    border: 1px solid var(--border);
    padding: 0.2rem 0.55rem;
    border-radius: var(--radius-sm);
    flex-shrink: 0;
}

.chapter-tag {
    font-family: var(--font-mono);
    font-feature-settings: "tnum";
    font-size: 0.6875rem;
    color: var(--ink-muted);
    background: var(--surface);
    padding: 0.2rem 0.5rem;
    border-radius: var(--radius-sm);
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
}

.e-title {
    font-size: 1rem;
    font-weight: 600;
    color: var(--ink-primary);
    margin: 0;
    line-height: 1.35;
}

.e-desc {
    font-size: 0.8125rem;
    color: var(--ink-secondary);
    line-height: 1.6;
    margin: 0;
    display: -webkit-box;
    -webkit-line-clamp: 3;
    -webkit-box-orient: vertical;
    overflow: hidden;
}

.e-card-foot {
    display: flex;
    justify-content: flex-end;
    padding-top: 0.5rem;
    border-top: 1px solid var(--border);
    margin-top: auto;
}

.e-open {
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
.e-card:hover .e-open { opacity: 1; transform: translateX(0); }

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

.sk-card { height: 132px; border-radius: var(--radius-lg); }

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

.drawer-title-row { display: flex; align-items: center; gap: 0.625rem; min-width: 0; }

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

.drawer-section { display: flex; flex-direction: column; gap: 0.625rem; }

.section-label {
    font-size: 0.75rem;
    font-weight: 600;
    color: var(--ink-muted);
    margin: 0;
    padding-bottom: 0.4rem;
    border-bottom: 1px solid var(--border);
}

.info-cell {
    display: inline-flex;
    padding: 0.5rem 0.7rem;
    background: var(--surface);
    border-radius: var(--radius-md);
    align-self: flex-start;
}

.info-value { font-size: 0.8125rem; font-weight: 500; color: var(--ink-primary); }

.md-box {
    background: var(--surface);
    border-radius: var(--radius-md);
    padding: 1rem 1.1rem;
}
.md-empty { color: var(--ink-muted); font-size: 0.8125rem; }

/* Markdown 渲染 */
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
.md-render :deep(blockquote) {
    margin: 0.5rem 0;
    padding-left: 0.875rem;
    border-left: 3px solid var(--border-strong);
    color: var(--ink-muted);
}
.md-render :deep(hr) { border: none; border-top: 1px solid var(--border); margin: 0.875rem 0; }

/* ── 响应式 ── */
@media (max-width: 960px) {
    .entity-view { padding: 1rem; }
    .filter-row { flex-direction: column; align-items: stretch; }
    .search-wrap { width: 100%; }
    .search-input { width: 100%; }
    .cards-grid { grid-template-columns: 1fr; }
    .detail-drawer { width: 100vw; max-width: 100vw; border-radius: 0; }
}
</style>
