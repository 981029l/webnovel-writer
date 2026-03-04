<script setup>
// Copyright (c) 2026 左岚. All rights reserved.
import { ref, onMounted, computed } from 'vue'
import { entitiesApi } from '../api'

const entities = ref([])
const loading = ref(true)
const selectedType = ref('all')
const entityTypes = ref([])

// Drawer state
const selectedEntity = ref(null)
const isDrawerOpen = ref(false)

async function loadEntities() {
    loading.value = true
    try {
        const params = selectedType.value !== 'all' ? { type: selectedType.value } : {}
        const { data } = await entitiesApi.getAll(params)
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
    setTimeout(() => { selectedEntity.value = null }, 300)
}
const getCategoryIcon = (type) => {
    switch(type) {
        case '角色': case 'character': return '👤'
        case '地点': case 'location': return '📍'
        case '物品': case 'item': return '🎁'
        case '势力': case 'faction': return '🏰'
        case '功法': case 'skill': return '⚔️'
        case '伏笔': case 'foreshadowing': return '🔮'
        default: return '📌'
    }
}

const getCategoryName = (type) => {
    switch(type) {
        case 'character': return '角色'
        case 'location': return '地点'
        case 'item': return '物品'
        case 'faction': return '势力'
        case 'skill': return '招式/技能'
        case 'foreshadowing': return '伏笔'
        default: return type
    }
}

onMounted(async () => {
    await loadTypes()
    await loadEntities()
})
</script>

<template>
    <div class="entity-view" :class="{ 'drawer-open': isDrawerOpen }">
        <header class="page-header glass-panel">
            <div class="header-content">
                <h1>📚 全景设定集</h1>
                <p class="subtitle">管理角色、地点、道具等世界设定枢纽</p>
            </div>
            <div class="filter-bar">
                <select v-model="selectedType" @change="loadEntities" class="glass-select">
                    <option value="all">👁️ 全部类型</option>
                    <option v-for="t in entityTypes" :key="t.id || t" :value="t.id || t">{{ t.icon || getCategoryIcon(t.name || t) }} {{ t.name || t }}</option>
                </select>
            </div>
        </header>

        <div v-if="loading" class="loading glass-panel">
            <div class="spinner"></div>
            <p>正在同步天地法则...</p>
        </div>
        
        <div v-else-if="entities.length === 0" class="empty-state glass-panel">
            <div class="empty-icon">📭</div>
            <h2>暂无设定数据</h2>
            <p class="hint">当您开始撰写章节时，AI 将自动从文字中提取并收容实体信息。</p>
        </div>

        <div v-else class="masonry-grid">
            <div v-for="entity in entities" :key="entity.id" class="entity-card glass-card" @click="openDrawer(entity)">
                <div class="card-header">
                    <span class="entity-type-badge">
                        {{ getCategoryIcon(entity.type) }} {{ getCategoryName(entity.type) }}
                    </span>
                    <span class="entity-chapter-badge" v-if="entity.first_appearance">
                        初始卷章: {{ entity.first_appearance }}
                    </span>
                </div>
                <h3 class="entity-title">{{ entity.name }}</h3>
                <p class="entity-desc">{{ entity.description || '暂无描述' }}</p>
                <div class="card-footer">
                    <button class="view-btn">查看宗卷 →</button>
                </div>
            </div>
        </div>

        <!-- Glassmorphism Drawer -->
        <div class="drawer-overlay" :class="{ 'active': isDrawerOpen }" @click="closeDrawer"></div>
        <div class="entity-drawer glass-drawer" :class="{ 'open': isDrawerOpen }">
            <div v-if="selectedEntity" class="drawer-content">
                <button class="close-btn" @click="closeDrawer">×</button>
                
                <div class="drawer-header">
                    <span class="drawer-badge">{{ getCategoryIcon(selectedEntity.type) }} {{ getCategoryName(selectedEntity.type) }}</span>
                    <h2 class="drawer-title">{{ selectedEntity.name }}</h2>
                </div>
                
                <div class="drawer-body">
                    <div class="info-section">
                        <h4>基本描述</h4>
                        <div class="markdown-preview glass-inset">
                            <!-- TODO: 以后接入完整的Markdown编辑器，目前只做纯文本显示 -->
                            <p v-for="(line, idx) in (selectedEntity.description || '').split('\n')" :key="idx" class="markdown-paragraph">
                                {{ line }}
                            </p>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    </div>
</template>

<style scoped>
/* Page Layout */
.entity-view {
    max-width: 1400px;
    margin: 0 auto;
    padding: 2rem;
    transition: transform 0.3s cubic-bezier(0.4, 0, 0.2, 1);
    position: relative;
    background-color: #f3f4f6; /* light gray backend bg */
    min-height: calc(100vh - 4rem);
    color: #111827;
}

.entity-view.drawer-open {
    transform: scale(0.98) translateX(-10px);
}

/* Light Theme Utilities */
.glass-panel, .glass-card, .glass-drawer, .glass-inset {
    background: #ffffff;
    border: 1px solid #e5e7eb;
    box-shadow: 0 1px 3px rgba(0, 0, 0, 0.05);
}

.glass-select {
    background-color: #ffffff;
    border: 1px solid #d1d5db;
    color: #111827;
}

/* Header */
.page-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    border-radius: 12px;
    padding: 1.5rem 2rem;
    margin-bottom: 2.5rem;
}

.header-content h1 {
    font-size: 2rem;
    margin-bottom: 0.5rem;
    color: #111827;
    font-weight: 800;
}

.subtitle { color: #6b7280; font-size: 1rem; margin: 0; }

.glass-select {
    padding: 0.75rem 1.25rem;
    border-radius: 8px;
    font-size: 0.95rem;
    cursor: pointer;
    outline: none;
    transition: all 0.2s;
    appearance: none;
    -webkit-appearance: none;
    background-image: url("data:image/svg+xml;charset=US-ASCII,%3Csvg%20xmlns%3D%22http%3A%2F%2Fwww.w3.org%2F2000%2Fsvg%22%20width%3D%22292.4%22%20height%3D%22292.4%22%3E%3Cpath%20fill%3D%22%236b7280%22%20d%3D%22M287%2069.4a17.6%2017.6%200%200%200-13-5.4H18.4c-5%200-9.3%201.8-12.9%205.4A17.6%2017.6%200%200%200%200%2082.2c0%205%201.8%209.3%205.4%2012.9l128%20127.9c3.6%203.6%207.8%205.4%2012.8%205.4s9.2-1.8%2012.8-5.4L287%2095c3.5-3.5%205.4-7.8%205.4-12.8%200-5-1.9-9.2-5.5-12.8z%22%2F%3E%3C%2Fsvg%3E");
    background-repeat: no-repeat;
    background-position: right .7rem top 50%;
    background-size: .65rem auto;
    padding-right: 2.5rem;
}

.glass-select:hover { border-color: #9ca3af; }

/* Grid / Masonry Layout */
.masonry-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(320px, 1fr));
    gap: 1.5rem;
    align-items: start;
}

/* Cards */
.entity-card {
    border-radius: 12px;
    padding: 1.5rem;
    transition: all 0.2s cubic-bezier(0.4, 0, 0.2, 1);
    cursor: pointer;
    position: relative;
    overflow: hidden;
}

.entity-card:hover {
    transform: translateY(-2px);
    box-shadow: 0 10px 15px -3px rgba(0, 0, 0, 0.1), 0 4px 6px -2px rgba(0, 0, 0, 0.05);
    border-color: #a5b4fc;
}

.card-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 1rem;
}

.entity-type-badge {
    font-size: 0.75rem;
    font-weight: 600;
    color: #6b5840;
    background: #f0ebe3;
    padding: 0.3rem 0.6rem;
    border-radius: 20px;
    border: 1px solid #c7d2fe;
}

.entity-chapter-badge {
    font-size: 0.7rem;
    color: #6b7280;
    background: #f3f4f6;
    padding: 0.2rem 0.5rem;
    border-radius: 4px;
}

.entity-title {
    font-size: 1.25rem;
    font-weight: 700;
    color: #111827;
    margin-bottom: 0.75rem;
    line-height: 1.3;
}

.entity-desc {
    font-size: 0.95rem;
    color: #4b5563;
    line-height: 1.6;
    margin-bottom: 1.5rem;
    display: -webkit-box;
    -webkit-line-clamp: 4;
    -webkit-box-orient: vertical;
    overflow: hidden;
}

.card-footer {
    display: flex;
    justify-content: flex-end;
}

.view-btn {
    background: transparent;
    border: none;
    color: #6b5840;
    font-size: 0.85rem;
    font-weight: 600;
    cursor: pointer;
    padding: 0;
    transition: color 0.2s, transform 0.2s;
}

.entity-card:hover .view-btn {
    color: #5c4a32;
    transform: translateX(3px);
}

/* States */
.loading, .empty-state {
    text-align: center;
    padding: 5rem 2rem;
    border-radius: 12px;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
}

.spinner {
    width: 40px; height: 40px;
    border: 3px solid #e5e7eb;
    border-top-color: #6b5840;
    border-radius: 50%;
    animation: spin 1s linear infinite;
    margin-bottom: 1rem;
}

@keyframes spin { 100% { transform: rotate(360deg); } }

.empty-icon { font-size: 4rem; margin-bottom: 1rem; color: #9ca3af; }
.empty-state h2 { font-size: 1.5rem; color: #111827; margin-bottom: 0.5rem; }
.hint { color: #6b7280; }

/* Drawer Component */
.drawer-overlay {
    position: fixed;
    top: 0; left: 0; right: 0; bottom: 0;
    background: rgba(17, 24, 39, 0.5); /* darker backdrop for white drawer */
    backdrop-filter: blur(2px);
    -webkit-backdrop-filter: blur(2px);
    z-index: 99;
    opacity: 0;
    pointer-events: none;
    transition: opacity 0.3s ease;
}

.drawer-overlay.active {
    opacity: 1;
    pointer-events: auto;
}

.entity-drawer {
    position: fixed;
    top: 0; right: 0; bottom: 0;
    width: 500px;
    max-width: 90vw;
    z-index: 100;
    transform: translateX(100%);
    transition: transform 0.4s cubic-bezier(0.16, 1, 0.3, 1);
    border-left: 1px solid #e5e7eb;
    border-radius: 24px 0 0 24px;
    padding: 2.5rem;
    overflow-y: auto;
    background: #ffffff; 
}

.entity-drawer.open {
    transform: translateX(0);
    box-shadow: -20px 0 60px rgba(0, 0, 0, 0.1);
}

.close-btn {
    position: absolute;
    top: 1.5rem; right: 1.5rem;
    background: #f3f4f6;
    border: 1px solid #d1d5db;
    color: #4b5563;
    width: 36px; height: 36px;
    border-radius: 50%;
    font-size: 1.2rem;
    display: flex; align-items: center; justify-content: center;
    cursor: pointer;
    transition: all 0.2s;
}

.close-btn:hover {
    background: #e5e7eb;
    color: #111827;
    transform: rotate(90deg);
}

.drawer-header {
    margin-bottom: 2rem;
    padding-right: 2rem;
}

.drawer-badge {
    display: inline-block;
    font-size: 0.85rem;
    color: #6b5840;
    background: #f0ebe3;
    padding: 0.4rem 0.8rem;
    border-radius: 6px;
    margin-bottom: 1rem;
}

.drawer-title {
    font-size: 2.2rem;
    font-weight: 800;
    color: #111827;
    line-height: 1.2;
}

.info-section h4 {
    font-size: 1.1rem;
    color: #111827;
    margin-bottom: 1rem;
    font-weight: 600;
}

.glass-inset {
    background: #f9fafb;
    border-radius: 12px;
    padding: 1.5rem;
    border: 1px solid #e5e7eb;
    box-shadow: inset 0 2px 4px rgba(0,0,0,0.02);
}

.markdown-paragraph {
    color: #374151;
    line-height: 1.7;
    margin-bottom: 1rem;
    font-size: 1rem;
}
.markdown-paragraph:last-child { margin-bottom: 0; }
</style>
