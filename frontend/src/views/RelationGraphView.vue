<script setup>
// Copyright (c) 2026 左岚. All rights reserved.
import { ref, onMounted, computed, watch } from 'vue'
import { charactersApi } from '../api'
import { useProjectStore } from '../stores/project'

const loading = ref(true)
const graphData = ref({ nodes: [], edges: [], protagonist: null, stats: { nodeCount: 0, edgeCount: 0 } })
const error = ref(null)
const selectedNode = ref(null)
const filterCategory = ref('全部')
const projectStore = useProjectStore()

// 详情面板
const profileLoading = ref(false)
const profile = ref(null)

async function loadRelationships() {
    loading.value = true
    error.value = null
    try {
        const { data } = await charactersApi.getRelationships()
        graphData.value = data
    } catch (e) {
        console.error('Failed to load relationships:', e)
        error.value = '加载关系数据失败: ' + (e.response?.data?.detail || e.message)
    } finally {
        loading.value = false
    }
}

// 构建每个角色的关系列表
const characterCards = computed(() => {
    const { nodes, edges, protagonist } = graphData.value
    if (!nodes.length) return []

    const nodeById = {}
    nodes.forEach(n => { nodeById[n.id] = n })

    return nodes.map(node => {
        const relations = edges
            .filter(e => e.source === node.id || e.target === node.id)
            .map(e => {
                const otherId = e.source === node.id ? e.target : e.source
                const other = nodeById[otherId]
                return {
                    name: other?.name || '未知',
                    label: e.label || '相关',
                    category: other?.category || '次要角色',
                }
            })

        return {
            id: node.id,
            name: node.name,
            category: node.category,
            isProtagonist: node.name === protagonist,
            dead: node.dead || false,
            relationCount: relations.length,
            relations,
        }
    })
})

const filteredCards = computed(() => {
    if (filterCategory.value === '全部') return characterCards.value
    return characterCards.value.filter(c => c.category === filterCategory.value)
})

const categories = ['全部', '主要角色', '次要角色', '反派角色']

const categoryColors = {
    '主要角色': { dot: '#ef4444', bg: '#fef2f2', border: '#fecaca', text: '#dc2626' },
    '次要角色': { dot: '#3b82f6', bg: '#eff6ff', border: '#bfdbfe', text: '#2563eb' },
    '反派角色': { dot: '#8b5cf6', bg: '#f5f3ff', border: '#ddd6fe', text: '#7c3aed' },
    '未归档': { dot: '#6b7280', bg: '#f3f4f6', border: '#d1d5db', text: '#4b5563' },
}

function buildFallbackProfile(card) {
    return {
        name: card.name,
        queryName: card.name,
        category: card.category || '未归档',
        content: '',
        realm: '',
        status: card.dead ? '已死亡' : '未建档',
        location: '',
        lastUpdateChapter: '',
        identity: '',
        firstAppear: '',
        treasures: [],
        factions: [],
        techniques: [],
        missing: true,
    }
}

async function selectCard(card) {
    if (selectedNode.value === card.id) {
        selectedNode.value = null
        profile.value = null
        return
    }
    selectedNode.value = card.id
    profileLoading.value = true
    profile.value = null
    try {
        const { data } = await charactersApi.getProfile(card.name)
        profile.value = data
    } catch (e) {
        if (e.response?.status !== 404) {
            console.error('Failed to load profile:', e)
        }
        profile.value = buildFallbackProfile(card)
    } finally {
        profileLoading.value = false
    }
}

function closePanel() {
    selectedNode.value = null
    profile.value = null
}

onMounted(loadRelationships)

watch(() => projectStore.projectRoot, async (newRoot, oldRoot) => {
    if (!newRoot || newRoot === oldRoot) return
    selectedNode.value = null
    profile.value = null
    await loadRelationships()
})
</script>

<template>
    <div class="relation-view">
        <header class="page-header">
            <div class="header-left">
                <h1>角色关系图谱</h1>
                <div class="stats" v-if="graphData.stats">
                    <span>{{ graphData.stats.nodeCount }} 角色</span>
                    <span class="sep">|</span>
                    <span>{{ graphData.stats.edgeCount }} 关系</span>
                    <span v-if="graphData.protagonist" class="sep">|</span>
                    <span v-if="graphData.protagonist" class="protagonist-tag">主角: {{ graphData.protagonist }}</span>
                </div>
            </div>
            <button class="refresh-btn" @click="loadRelationships" :disabled="loading">
                {{ loading ? '加载中...' : '刷新' }}
            </button>
        </header>

        <!-- 分类筛选 -->
        <div v-if="!loading && !error && graphData.nodes.length" class="filter-bar">
            <button
                v-for="cat in categories"
                :key="cat"
                class="filter-btn"
                :class="{ active: filterCategory === cat }"
                @click="filterCategory = cat"
            >
                <span v-if="cat !== '全部'" class="cat-dot" :style="{ background: categoryColors[cat]?.dot }"></span>
                {{ cat }}
                <span class="filter-count">{{ cat === '全部' ? characterCards.length : characterCards.filter(c => c.category === cat).length }}</span>
            </button>
        </div>

        <div v-if="loading" class="loading-state">
            <div class="spinner"></div>
            <p>正在加载角色关系...</p>
        </div>

        <div v-else-if="error" class="error-state">
            <p class="error-text">{{ error }}</p>
            <button class="retry-btn" @click="loadRelationships">重试</button>
        </div>

        <div v-else-if="graphData.nodes.length === 0" class="empty-state">
            <h2>暂无关系数据</h2>
            <p>请先在「角色管理」中创建角色档案。</p>
        </div>

        <!-- 主体区域：卡片 + 详情面板 -->
        <div v-else class="main-area">
            <!-- 卡片网格 -->
            <div class="cards-grid" :class="{ 'has-panel': selectedNode !== null }">
                <div
                    v-for="card in filteredCards"
                    :key="card.id"
                    class="char-card"
                    :class="{
                        protagonist: card.isProtagonist,
                        selected: selectedNode === card.id,
                        'no-relations': card.relations.length === 0,
                        dead: card.dead
                    }"
                    @click="selectCard(card)"
                >
                    <div class="card-top">
                        <div class="card-name-row">
                            <span class="cat-indicator" :style="{ background: categoryColors[card.category]?.dot }"></span>
                            <span class="card-name" :class="{ 'name-dead': card.dead }">{{ card.name }}</span>
                            <span v-if="card.dead" class="dead-badge">已死亡</span>
                            <span v-else-if="card.isProtagonist" class="protag-badge">主角</span>
                        </div>
                        <span class="card-category" :style="{
                            color: categoryColors[card.category]?.text,
                            background: categoryColors[card.category]?.bg,
                            borderColor: categoryColors[card.category]?.border,
                        }">{{ card.category }}</span>
                    </div>

                    <div v-if="card.relations.length" class="relations-list">
                        <div v-for="(rel, i) in card.relations" :key="i" class="relation-item">
                            <span class="rel-dot" :style="{ background: categoryColors[rel.category]?.dot }"></span>
                            <span class="rel-name">{{ rel.name }}</span>
                            <span class="rel-label">{{ rel.label }}</span>
                        </div>
                    </div>
                    <div v-else class="no-rel-hint">暂无关系</div>
                </div>
            </div>

            <!-- 详情面板 -->
            <transition name="slide">
                <div v-if="selectedNode !== null" class="detail-panel">
                    <div class="panel-header">
                        <h2 v-if="profile">{{ profile.name }}</h2>
                        <h2 v-else>加载中...</h2>
                        <button class="close-btn" @click="closePanel">
                            <svg width="14" height="14" viewBox="0 0 14 14" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><line x1="1" y1="1" x2="13" y2="13"/><line x1="13" y1="1" x2="1" y2="13"/></svg>
                        </button>
                    </div>

                    <div v-if="profileLoading" class="panel-loading">
                        <div class="spinner small"></div>
                    </div>

                    <div v-else-if="profile" class="panel-body">
                        <div v-if="profile.missing" class="profile-missing-hint">
                            未找到角色独立档案，当前展示基础信息。
                        </div>

                        <!-- 基本信息 -->
                        <div class="info-section">
                            <div class="info-row" v-if="profile.identity">
                                <span class="info-label">身份</span>
                                <span class="info-value">{{ profile.identity }}</span>
                            </div>
                            <div class="info-row" v-if="profile.realm">
                                <span class="info-label">境界</span>
                                <span class="info-value">{{ profile.realm }}</span>
                            </div>
                            <div class="info-row">
                                <span class="info-label">分类</span>
                                <span class="info-value tag" :style="{
                                    color: categoryColors[profile.category]?.text,
                                    background: categoryColors[profile.category]?.bg,
                                }">{{ profile.category }}</span>
                            </div>
                            <div class="info-row">
                                <span class="info-label">状态</span>
                                <span class="info-value">{{ profile.status }}</span>
                            </div>
                            <div class="info-row" v-if="profile.location">
                                <span class="info-label">地点</span>
                                <span class="info-value">{{ profile.location }}</span>
                            </div>
                            <div class="info-row" v-if="profile.firstAppear">
                                <span class="info-label">首次出场</span>
                                <span class="info-value">{{ profile.firstAppear }}</span>
                            </div>
                            <div class="info-row" v-if="profile.lastUpdateChapter">
                                <span class="info-label">最近更新</span>
                                <span class="info-value">{{ profile.lastUpdateChapter }}</span>
                            </div>
                        </div>

                        <!-- 关系 -->
                        <div class="info-section" v-if="characterCards.find(c => c.id === selectedNode)?.relations.length">
                            <h3>关系</h3>
                            <div class="tag-list">
                                <div
                                    v-for="(rel, i) in characterCards.find(c => c.id === selectedNode)?.relations"
                                    :key="'r'+i"
                                    class="tag-item rel-tag"
                                >
                                    <span class="rel-dot" :style="{ background: categoryColors[rel.category]?.dot }"></span>
                                    <span class="tag-name">{{ rel.name }}</span>
                                    <span class="tag-desc">{{ rel.label }}</span>
                                </div>
                            </div>
                        </div>

                        <!-- 宝物 -->
                        <div class="info-section" v-if="profile.treasures.length">
                            <h3>宝物</h3>
                            <div class="tag-list">
                                <div v-for="t in profile.treasures" :key="t.name" class="tag-item treasure-tag">
                                    <span class="tag-name">{{ t.name }}</span>
                                    <span class="tag-desc" v-if="t.desc">{{ t.desc }}</span>
                                </div>
                            </div>
                        </div>

                        <!-- 势力 -->
                        <div class="info-section" v-if="profile.factions.length">
                            <h3>势力</h3>
                            <div class="tag-list">
                                <div v-for="f in profile.factions" :key="f.name" class="tag-item faction-tag">
                                    <span class="tag-name">{{ f.name }}</span>
                                    <span class="tag-desc" v-if="f.desc">{{ f.desc }}</span>
                                </div>
                            </div>
                        </div>

                        <!-- 功法 -->
                        <div class="info-section" v-if="profile.techniques.length">
                            <h3>功法</h3>
                            <div class="tag-list">
                                <div v-for="t in profile.techniques" :key="t.name" class="tag-item tech-tag">
                                    <span class="tag-name">{{ t.name }}</span>
                                    <span class="tag-desc" v-if="t.desc">{{ t.desc }}</span>
                                </div>
                            </div>
                        </div>

                        <!-- 无额外信息 -->
                        <div v-if="!profile.treasures.length && !profile.factions.length && !profile.techniques.length
                            && !characterCards.find(c => c.id === selectedNode)?.relations.length"
                            class="no-extra">
                            暂无关联的宝物、势力或功法信息
                        </div>
                    </div>
                </div>
            </transition>
        </div>
    </div>
</template>

<style scoped>
/* ============================================================
   墨迹人物志 — Ink Character Chronicle
   Warm parchment, editorial refinement, amber-bronze accents
   ============================================================ */

.relation-view {
    max-width: 1400px;
    margin: 0 auto;
    padding: 1.75rem 2rem;
    height: calc(100vh - 4rem);
    display: flex;
    flex-direction: column;
    overflow: hidden;
}

/* ── Page Header ── */
.page-header {
    display: flex;
    justify-content: space-between;
    align-items: flex-start;
    margin-bottom: 1.5rem;
    flex-shrink: 0;
    padding-bottom: 1.25rem;
    border-bottom: 1px solid var(--border);
    position: relative;
}

.page-header::after {
    content: '';
    position: absolute;
    bottom: -1px;
    left: 0;
    width: 80px;
    height: 2px;
    background: var(--primary);
    border-radius: 1px;
}

.page-header h1 {
    font-size: 1.5rem;
    font-weight: 700;
    color: var(--text-primary);
    margin: 0;
    letter-spacing: 0.02em;
}

.stats {
    font-size: 0.78rem;
    color: var(--text-muted);
    margin-top: 0.4rem;
    display: flex;
    align-items: center;
    gap: 0.5rem;
}

.sep {
    color: var(--border);
    font-size: 0.6rem;
}

.protagonist-tag {
    color: #b45309;
    font-weight: 600;
    background: rgba(180, 83, 9, 0.08);
    padding: 0.1rem 0.45rem;
    border-radius: 4px;
    font-size: 0.75rem;
}

.refresh-btn {
    background: var(--bg-card);
    color: var(--text-secondary);
    border: 1px solid var(--border);
    padding: 0.45rem 1rem;
    border-radius: var(--radius-md);
    cursor: pointer;
    font-size: 0.82rem;
    font-weight: 500;
    transition: all 0.2s ease;
    display: inline-flex;
    align-items: center;
    gap: 0.35rem;
}

.refresh-btn:hover {
    background: var(--bg-hover);
    border-color: var(--border-hover);
    color: var(--text-primary);
}

.refresh-btn:disabled {
    opacity: 0.5;
    cursor: not-allowed;
}

/* ── Filter Bar ── */
.filter-bar {
    display: flex;
    gap: 0.5rem;
    margin-bottom: 1.25rem;
    flex-shrink: 0;
    flex-wrap: wrap;
}

.filter-btn {
    display: inline-flex;
    align-items: center;
    gap: 0.4rem;
    padding: 0.4rem 0.9rem;
    border-radius: 20px;
    border: 1px solid var(--border);
    background: var(--bg-card);
    color: var(--text-secondary);
    font-size: 0.8rem;
    font-weight: 500;
    cursor: pointer;
    transition: all 0.2s ease;
    user-select: none;
}

.filter-btn:hover {
    border-color: var(--primary);
    color: var(--primary);
    background: var(--primary-light);
}

.filter-btn.active {
    background: var(--primary);
    color: #fff;
    border-color: var(--primary);
    box-shadow: 0 1px 4px rgba(139, 115, 85, 0.25);
}

.filter-btn.active .cat-dot {
    background: #fff !important;
    box-shadow: 0 0 0 1px rgba(255, 255, 255, 0.3);
}

.cat-dot {
    width: 7px;
    height: 7px;
    border-radius: 50%;
    flex-shrink: 0;
    transition: all 0.2s;
}

.filter-count {
    font-size: 0.68rem;
    opacity: 0.6;
    margin-left: 0.1rem;
}

/* ── Main Layout ── */
.main-area {
    flex: 1;
    display: flex;
    gap: 1.25rem;
    overflow: hidden;
    min-height: 0;
}

/* ── Cards Grid ── */
.cards-grid {
    flex: 1;
    overflow-y: auto;
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(285px, 1fr));
    gap: 0.875rem;
    align-content: start;
    padding-bottom: 2rem;
    padding-right: 0.25rem;
    transition: all 0.25s ease;
}

/* Custom scrollbar for cards grid */
.cards-grid::-webkit-scrollbar {
    width: 5px;
}

.cards-grid::-webkit-scrollbar-track {
    background: transparent;
}

.cards-grid::-webkit-scrollbar-thumb {
    background: var(--border);
    border-radius: 3px;
}

.cards-grid::-webkit-scrollbar-thumb:hover {
    background: var(--border-hover);
}

.cards-grid.has-panel {
    grid-template-columns: repeat(auto-fill, minmax(240px, 1fr));
}

/* ── Character Card ── */
.char-card {
    background: var(--bg-card);
    border: 1px solid var(--border);
    border-radius: var(--radius-lg);
    padding: 1rem 1.1rem;
    cursor: pointer;
    transition: all 0.2s ease;
    position: relative;
}

.char-card::before {
    content: '';
    position: absolute;
    top: 0;
    left: 0;
    width: 3px;
    height: 0;
    background: var(--primary);
    border-radius: 0 0 2px 2px;
    transition: height 0.25s ease;
}

.char-card:hover {
    border-color: var(--border-hover);
    box-shadow: var(--shadow-sm);
    transform: translateY(-1px);
}

.char-card:hover::before {
    height: 100%;
    border-radius: var(--radius-lg) 0 0 var(--radius-lg);
}

.char-card.protagonist {
    border-color: rgba(180, 83, 9, 0.2);
    background: linear-gradient(135deg, #fefaf4, var(--bg-card));
}

.char-card.protagonist::before {
    background: #b45309;
}

.char-card.dead {
    opacity: 0.45;
    background: var(--bg-secondary);
}

.char-card.dead:hover {
    opacity: 0.65;
}

.char-card.dead::before {
    background: var(--text-muted);
}

.name-dead {
    text-decoration: line-through;
    color: var(--text-muted) !important;
}

.dead-badge {
    font-size: 0.62rem;
    font-weight: 600;
    color: var(--text-muted);
    background: var(--bg-secondary);
    padding: 0.1rem 0.4rem;
    border-radius: 3px;
    border: 1px solid var(--border);
    letter-spacing: 0.02em;
}

.char-card.selected {
    border-color: var(--primary);
    box-shadow: 0 0 0 2px rgba(139, 115, 85, 0.12), var(--shadow-sm);
}

.char-card.selected::before {
    height: 100%;
    border-radius: var(--radius-lg) 0 0 var(--radius-lg);
}

/* ── Card Header ── */
.card-top {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 0.75rem;
}

.card-name-row {
    display: flex;
    align-items: center;
    gap: 0.5rem;
}

.cat-indicator {
    width: 6px;
    height: 6px;
    border-radius: 50%;
    flex-shrink: 0;
    box-shadow: 0 0 0 2px rgba(0, 0, 0, 0.04);
}

.card-name {
    font-size: 0.95rem;
    font-weight: 700;
    color: var(--text-primary);
    letter-spacing: 0.01em;
}

.protag-badge {
    font-size: 0.62rem;
    font-weight: 600;
    color: #b45309;
    background: rgba(180, 83, 9, 0.1);
    padding: 0.12rem 0.45rem;
    border-radius: 3px;
    letter-spacing: 0.03em;
}

.card-category {
    font-size: 0.68rem;
    font-weight: 500;
    padding: 0.15rem 0.5rem;
    border-radius: 4px;
    border: 1px solid;
    white-space: nowrap;
}

/* ── Relations List (in-card) ── */
.relations-list {
    display: flex;
    flex-direction: column;
    gap: 0;
}

.relation-item {
    display: flex;
    align-items: center;
    gap: 0.45rem;
    font-size: 0.82rem;
    padding: 0.35rem 0;
    border-bottom: 1px dashed var(--border);
    transition: background 0.15s;
}

.relation-item:last-child {
    border-bottom: none;
}

.relation-item:hover {
    background: rgba(139, 115, 85, 0.03);
    margin: 0 -0.4rem;
    padding-left: 0.4rem;
    padding-right: 0.4rem;
    border-radius: 3px;
}

.rel-dot {
    width: 5px;
    height: 5px;
    border-radius: 50%;
    flex-shrink: 0;
}

.rel-name {
    font-weight: 600;
    color: var(--text-primary);
    white-space: nowrap;
}

.rel-label {
    color: var(--text-muted);
    font-size: 0.76rem;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
    margin-left: auto;
    font-style: italic;
}

.no-rel-hint {
    font-size: 0.8rem;
    color: var(--text-muted);
    text-align: center;
    padding: 0.75rem 0;
    font-style: italic;
    opacity: 0.6;
}

/* ========== Detail Panel ========== */
.detail-panel {
    width: 350px;
    flex-shrink: 0;
    background: var(--bg-card);
    border: 1px solid var(--border);
    border-radius: var(--radius-lg);
    display: flex;
    flex-direction: column;
    overflow: hidden;
    box-shadow: var(--shadow-sm);
}

.panel-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 1rem 1.25rem;
    border-bottom: 1px solid var(--border);
    flex-shrink: 0;
    background: linear-gradient(180deg, var(--bg-card), var(--bg-secondary));
}

.panel-header h2 {
    font-size: 1.1rem;
    font-weight: 700;
    color: var(--text-primary);
    margin: 0;
    letter-spacing: 0.02em;
}

.close-btn {
    width: 28px;
    height: 28px;
    display: flex;
    align-items: center;
    justify-content: center;
    background: var(--bg-secondary);
    border: 1px solid var(--border);
    border-radius: var(--radius-md);
    font-size: 1.1rem;
    color: var(--text-muted);
    cursor: pointer;
    line-height: 1;
    transition: all 0.15s;
}

.close-btn:hover {
    color: var(--text-primary);
    background: var(--bg-hover);
    border-color: var(--border-hover);
}

.panel-loading {
    flex: 1;
    display: flex;
    align-items: center;
    justify-content: center;
}

.panel-body {
    flex: 1;
    overflow-y: auto;
    padding: 1rem 1.25rem;
}

/* Panel scrollbar */
.panel-body::-webkit-scrollbar {
    width: 4px;
}

.panel-body::-webkit-scrollbar-track {
    background: transparent;
}

.panel-body::-webkit-scrollbar-thumb {
    background: var(--border);
    border-radius: 2px;
}

.profile-missing-hint {
    font-size: 0.78rem;
    color: #92400e;
    background: rgba(255, 251, 235, 0.8);
    border: 1px solid #fde68a;
    border-left: 3px solid #f59e0b;
    border-radius: 0 var(--radius-md) var(--radius-md) 0;
    padding: 0.55rem 0.7rem;
    margin-bottom: 1rem;
    line-height: 1.5;
}

/* ── Info Sections ── */
.info-section {
    margin-bottom: 1.25rem;
}

.info-section h3 {
    font-size: 0.72rem;
    font-weight: 600;
    color: var(--text-muted);
    text-transform: uppercase;
    letter-spacing: 0.08em;
    margin: 0 0 0.65rem 0;
    padding-bottom: 0.45rem;
    border-bottom: 1px solid var(--border);
    position: relative;
}

.info-section h3::after {
    content: '';
    position: absolute;
    bottom: -1px;
    left: 0;
    width: 32px;
    height: 1.5px;
    background: var(--primary);
    border-radius: 1px;
}

.info-row {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 0.38rem 0;
    font-size: 0.84rem;
}

.info-row + .info-row {
    border-top: 1px dotted rgba(224, 219, 210, 0.5);
}

.info-label {
    color: var(--text-muted);
    font-size: 0.8rem;
    flex-shrink: 0;
}

.info-value {
    color: var(--text-primary);
    font-weight: 500;
    text-align: right;
}

.info-value.tag {
    font-size: 0.74rem;
    padding: 0.12rem 0.5rem;
    border-radius: 4px;
}

/* ── Tag List (detail panel) ── */
.tag-list {
    display: flex;
    flex-direction: column;
    gap: 0.45rem;
}

.tag-item {
    padding: 0.55rem 0.75rem;
    border-radius: var(--radius-md);
    border: 1px solid var(--border);
    background: var(--bg-background);
    transition: all 0.15s;
}

.tag-item:hover {
    background: var(--bg-hover);
    border-color: var(--border-hover);
}

.tag-name {
    font-size: 0.84rem;
    font-weight: 600;
    color: var(--text-primary);
    display: block;
}

.tag-desc {
    font-size: 0.74rem;
    color: var(--text-muted);
    margin-top: 0.2rem;
    display: block;
    line-height: 1.5;
}

/* Tag accent colors — warm palette, no purple */
.rel-tag { border-left: 3px solid var(--primary); }
.treasure-tag { border-left: 3px solid #d97706; }
.faction-tag { border-left: 3px solid #059669; }
.tech-tag { border-left: 3px solid #0284c7; }

.rel-tag .tag-item .rel-dot {
    display: inline-block;
}

.no-extra {
    font-size: 0.84rem;
    color: var(--text-muted);
    text-align: center;
    padding: 2.5rem 0;
    font-style: italic;
    opacity: 0.6;
}

/* ── Slide Transition ── */
.slide-enter-active {
    transition: all 0.25s cubic-bezier(0.16, 1, 0.3, 1);
}

.slide-leave-active {
    transition: all 0.18s ease-in;
}

.slide-enter-from {
    opacity: 0;
    transform: translateX(24px);
}

.slide-leave-to {
    opacity: 0;
    transform: translateX(24px);
}

/* ── State Pages ── */
.loading-state, .empty-state, .error-state {
    flex: 1;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    color: var(--text-muted);
}

.spinner {
    width: 32px;
    height: 32px;
    border: 2.5px solid var(--border);
    border-top-color: var(--primary);
    border-radius: 50%;
    animation: spin 0.8s linear infinite;
    margin-bottom: 0.85rem;
}

.spinner.small {
    width: 22px;
    height: 22px;
    border-width: 2px;
    margin-bottom: 0;
}

@keyframes spin {
    100% { transform: rotate(360deg); }
}

.error-text {
    color: var(--danger);
    margin-bottom: 0.5rem;
    font-size: 0.9rem;
}

.retry-btn {
    background: var(--primary);
    color: #fff;
    border: none;
    padding: 0.45rem 1.1rem;
    border-radius: var(--radius-md);
    cursor: pointer;
    font-size: 0.84rem;
    font-weight: 500;
    transition: all 0.15s;
}

.retry-btn:hover {
    background: var(--primary-dark);
}

.empty-state h2 {
    font-size: 1.1rem;
    color: var(--text-primary);
    margin-bottom: 0.3rem;
}

.empty-state p {
    font-size: 0.88rem;
}

/* ── Responsive ── */
@media (max-width: 768px) {
    .relation-view {
        padding: 1rem;
        height: calc(100vh - 2rem);
    }

    .page-header {
        flex-direction: column;
        gap: 0.75rem;
    }

    .page-header::after {
        width: 60px;
    }

    .filter-bar {
        overflow-x: auto;
        flex-wrap: nowrap;
        padding-bottom: 0.25rem;
        -webkit-overflow-scrolling: touch;
    }

    .filter-btn {
        flex-shrink: 0;
    }

    .main-area {
        flex-direction: column;
    }

    .cards-grid {
        grid-template-columns: 1fr;
    }

    .cards-grid.has-panel {
        grid-template-columns: 1fr;
    }

    .detail-panel {
        width: 100%;
        max-height: 50vh;
        border-radius: var(--radius-lg) var(--radius-lg) 0 0;
        border-bottom: none;
    }
}
</style>
