<!-- Copyright (c) 2026 左岚. All rights reserved. -->
<!-- RagView.vue - 知识检索(sticky 搜索 + 示例/最近查询) -->
<script setup>
import { ref } from 'vue'
import { BrainCircuit, Search, History, X } from 'lucide-vue-next'
import { ragApi } from '../api'

const query = ref('')
const mode = ref('hybrid')
const topK = ref(10)
const results = ref([])
const stats = ref(null)
const loading = ref(false)
const message = ref('')
const searched = ref(false)

const RECENT_KEY = 'wnw-rag-recent'
const recentQueries = ref(loadRecent())

const exampleQueries = [
    '主角目前的境界和功法',
    '还没回收的伏笔有哪些',
    '主角和反派的最近一次冲突',
    '金手指的能力和限制',
]

const sourceLabel = { hybrid: '混合', vector: '语义', bm25: '关键词' }

function loadRecent() {
    try {
        return JSON.parse(localStorage.getItem(RECENT_KEY) || '[]')
    } catch { return [] }
}

function saveRecent(q) {
    const list = [q, ...recentQueries.value.filter(item => item !== q)].slice(0, 8)
    recentQueries.value = list
    localStorage.setItem(RECENT_KEY, JSON.stringify(list))
}

function clearRecent() {
    recentQueries.value = []
    localStorage.removeItem(RECENT_KEY)
}

async function search() {
    if (!query.value.trim()) return
    loading.value = true
    message.value = ''
    try {
        const { data } = await ragApi.search(query.value, mode.value, topK.value)
        searched.value = true
        if (data.error) {
            message.value = '注意: ' + data.error
            results.value = []
        } else {
            results.value = data.results
            message.value = `找到 ${results.value.length} 条相关内容`
            saveRecent(query.value.trim())
        }
    } catch (e) {
        searched.value = true
        message.value = '检索失败：' + e.message
        results.value = []
    } finally {
        loading.value = false
    }
}

function searchWith(q) {
    query.value = q
    search()
}

async function loadStats() {
    try {
        const { data } = await ragApi.getStats()
        stats.value = data.stats
    } catch (e) { console.error('Failed to load stats:', e) }
}
loadStats()

function highlightContent(content) {
    if (!query.value) return content
    const escaped = query.value.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
    const regex = new RegExp(`(${escaped})`, 'gi')
    return content.replace(regex, '<mark>$1</mark>')
}
</script>

<template>
  <div class="rag-layout">
    <!-- sticky 搜索区 -->
    <div class="search-sticky">
      <div class="rag-container">
        <div class="rag-header">
          <h1 class="page-title">知识检索</h1>
          <p class="page-subtitle">深度搜索全书剧情、设定与伏笔，写作时随手回顾</p>
        </div>

        <div class="search-box">
          <div class="search-input-wrapper">
            <Search :size="16" :stroke-width="1.75" class="input-icon" />
            <input
              v-model="query"
              class="main-search-input"
              placeholder="输入关键词或问题（如：主角是在哪里获得金手指的？）"
              @keyup.enter="search"
              autofocus
            />
            <button class="btn btn-ai btn-search" @click="search" :disabled="loading || !query.trim()">
              {{ loading ? '检索中...' : '检索' }}
            </button>
          </div>

          <div class="search-options">
            <div class="option-group">
              <span class="option-label">模式</span>
              <select v-model="mode" class="option-select">
                <option value="hybrid">混合检索 (推荐)</option>
                <option value="vector">语义向量</option>
                <option value="bm25">关键词匹配</option>
              </select>
            </div>
            <div class="option-group">
              <span class="option-label">数量</span>
              <select v-model="topK" class="option-select">
                <option :value="5">5</option>
                <option :value="10">10</option>
                <option :value="20">20</option>
              </select>
            </div>

            <div class="stats-mini" v-if="stats">
              <span class="stat-pill" title="已索引向量数">向量 {{ stats.vectors }}</span>
              <span class="stat-pill" title="已索引章节">章节 {{ stats.max_chapter }}</span>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- 结果区 -->
    <div class="rag-container">
      <main class="results-area">
        <div v-if="loading" class="loading-state">
           <div class="pulse-ring"></div>
           <p>正在检索全书记忆...</p>
        </div>

        <div v-else-if="results.length > 0" class="results-list">
          <div class="results-meta">{{ message }}</div>

          <div v-for="(result, index) in results" :key="result.chunk_id" class="result-card">
            <div class="card-header">
              <div class="header-left">
                <span class="rank-badge tnum">{{ index + 1 }}</span>
                <span class="chapter-info">第 {{ result.chapter }} 章</span>
                <span class="scene-info" v-if="result.scene_index">场景 {{ result.scene_index }}</span>
              </div>
              <div class="header-right">
                <span class="score-text">{{ (result.score * 100).toFixed(1) }}%</span>
                <span class="source-tag" :class="result.source">{{ sourceLabel[result.source] || result.source }}</span>
              </div>
            </div>

            <div class="card-content" v-html="highlightContent(result.content)"></div>
          </div>
        </div>

        <div v-else class="empty-state">
           <div v-if="message" class="error-msg">{{ message }}</div>
           <template v-else>
             <div class="placeholder-icon"><BrainCircuit :size="36" :stroke-width="1.25" /></div>
             <h3>问点什么吧</h3>
             <p>可以回顾剧情、查找遗忘的设定，或确认伏笔状态</p>

             <div class="suggest-block">
               <span class="suggest-label">试试这些</span>
               <div class="suggest-chips">
                 <button v-for="q in exampleQueries" :key="q" class="suggest-chip" @click="searchWith(q)">
                   {{ q }}
                 </button>
               </div>
             </div>

             <div v-if="recentQueries.length" class="suggest-block">
               <span class="suggest-label">
                 <History :size="12" :stroke-width="1.75" />
                 最近查询
                 <button class="recent-clear" @click="clearRecent" title="清空最近查询" aria-label="清空最近查询">
                   <X :size="11" :stroke-width="2" />
                 </button>
               </span>
               <div class="suggest-chips">
                 <button v-for="q in recentQueries" :key="q" class="suggest-chip recent" @click="searchWith(q)">
                   {{ q }}
                 </button>
               </div>
             </div>
           </template>
        </div>
      </main>
    </div>
  </div>
</template>

<style scoped>
/* Main Layout — 白纸内容页,自身为滚动容器 */
.rag-layout {
  height: 100%;
  width: 100%;
  overflow-y: auto;
  padding-bottom: 4rem;
}

.rag-container {
  max-width: 800px;
  margin: 0 auto;
  padding: 0 1.5rem;
}

/* sticky 搜索区 */
.search-sticky {
  position: sticky;
  top: 0;
  z-index: var(--z-sticky);
  background: var(--card);
  border-bottom: 1px solid var(--border);
  padding-bottom: 1rem;
}

.rag-header {
  padding: 1.5rem 0 1rem;
}

.page-title {
  font-size: 1.375rem;
  font-weight: 600;
  margin-bottom: 0.25rem;
  color: var(--ink-primary);
  letter-spacing: -0.01em;
}

.page-subtitle {
  color: var(--ink-muted);
  font-size: 0.875rem;
  margin: 0;
}

/* Search Box */
.search-box {
  background: var(--card);
  border: 1px solid var(--border);
  border-radius: var(--radius-lg);
  padding: 1rem;
  transition: border-color var(--dur-fast) var(--ease-standard), box-shadow var(--dur-fast) var(--ease-standard);
}

.search-box:focus-within {
  border-color: var(--primary);
  box-shadow: 0 0 0 3px var(--primary-tint);
}

.search-input-wrapper {
  position: relative;
  display: flex;
  gap: 0.625rem;
  margin-bottom: 0.875rem;
  align-items: center;
}

.input-icon {
  position: absolute;
  left: 0.875rem;
  color: var(--ink-muted);
  pointer-events: none;
}

.main-search-input {
  flex: 1;
  border: 1px solid var(--border);
  background: var(--surface);
  padding: 0.7rem 1rem 0.7rem 2.4rem;
  border-radius: var(--radius-md);
  font-size: 0.9375rem;
  color: var(--ink-primary);
  outline: none;
  transition: border-color var(--dur-fast) var(--ease-standard), background-color var(--dur-fast) var(--ease-standard);
}

.main-search-input:focus {
  border-color: var(--primary);
  background: var(--card);
}

.main-search-input::placeholder { color: var(--ink-muted); }

.btn-search {
  padding: 0 1.5rem;
  font-weight: 500;
  align-self: stretch;
}

.search-options {
  display: flex;
  align-items: center;
  gap: 1.5rem;
  padding-top: 0.75rem;
  border-top: 1px solid var(--border);
}

.option-group { display: flex; align-items: center; gap: 0.5rem; }
.option-label { font-size: 0.75rem; color: var(--ink-muted); font-weight: 500; }
.option-select {
  background: transparent;
  border: none;
  color: var(--ink-secondary);
  font-size: 0.875rem;
  cursor: pointer;
}

.stats-mini { margin-left: auto; display: flex; gap: 0.5rem; }
.stat-pill {
  font-family: var(--font-mono);
  font-feature-settings: "tnum";
  font-size: 0.6875rem;
  background: var(--surface);
  border: 1px solid var(--border);
  padding: 2px 8px;
  border-radius: var(--radius-sm);
  color: var(--ink-muted);
}

/* Results */
.results-area { margin-top: 1.25rem; }

.results-meta {
  margin-bottom: 1rem;
  font-size: 0.8125rem;
  color: var(--ink-muted);
}

.result-card {
  background: var(--card);
  border: 1px solid var(--border);
  border-radius: var(--radius-lg);
  padding: 1.1rem 1.25rem;
  margin-bottom: 0.75rem;
  transition: border-color var(--dur-fast) var(--ease-standard), box-shadow var(--dur-fast) var(--ease-standard);
}

.result-card:hover { border-color: var(--border-strong); box-shadow: var(--shadow-md); }

.card-header {
  display: flex;
  justify-content: space-between;
  margin-bottom: 0.75rem;
  font-size: 0.875rem;
}

.header-left { display: flex; gap: 0.625rem; align-items: center; }

.rank-badge {
  font-family: var(--font-mono);
  background: var(--surface);
  border: 1px solid var(--border);
  color: var(--ink-muted);
  min-width: 22px;
  height: 22px;
  padding: 0 4px;
  border-radius: var(--radius-sm);
  display: flex;
  align-items: center;
  justify-content: center;
  font-weight: 500;
  font-size: 0.6875rem;
}

.chapter-info { font-weight: 600; color: var(--ink-primary); }
.scene-info { color: var(--ink-muted); font-size: 0.8125rem; }

.header-right { display: flex; gap: 0.625rem; align-items: center; }
.score-text {
  color: var(--success);
  font-weight: 500;
  font-family: var(--font-mono);
  font-feature-settings: "tnum";
  font-size: 0.8125rem;
}
.source-tag {
  font-size: 0.6875rem;
  font-weight: 500;
  padding: 2px 7px;
  border-radius: var(--radius-sm);
}
.hybrid { background: var(--primary-tint); color: var(--primary-on-tint); }
.vector { background: var(--success-tint); color: var(--success); }
.bm25 { background: var(--warning-tint); color: var(--warning-strong); }

.card-content {
  color: var(--ink-secondary);
  line-height: 1.7;
  font-size: 0.9375rem;
}

.card-content :deep(mark) {
  background: var(--warning-tint);
  color: inherit;
  padding: 0 4px;
  border-radius: 2px;
}

/* Loading & Empty */
.loading-state { text-align: center; padding: 4rem 0; color: var(--ink-muted); }
.pulse-ring {
  width: 40px; height: 40px; border: 3px solid var(--primary); border-radius: 50%;
  margin: 0 auto 1rem; animation: pulse 1.5s infinite;
}
@keyframes pulse { 0% { transform: scale(0.8); opacity: 0.8; } 100% { transform: scale(2); opacity: 0; } }
@media (prefers-reduced-motion: reduce) {
  .pulse-ring { animation: none; opacity: 0.6; }
}

.empty-state { text-align: center; padding: 3rem 0; }
.placeholder-icon { margin-bottom: 1rem; opacity: 0.5; color: var(--ink-muted); }
.empty-state h3 { color: var(--ink-primary); font-size: 1.125rem; font-weight: 600; margin-bottom: 0.5rem; }
.empty-state p { color: var(--ink-muted); font-size: 0.875rem; margin: 0; }
.error-msg { color: var(--danger); background: var(--danger-tint); display: inline-block; padding: 0.5rem 1rem; border-radius: var(--radius-md); font-size: 0.875rem; }

/* 示例 / 最近查询 */
.suggest-block {
  margin-top: 1.75rem;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 0.625rem;
}

.suggest-label {
  display: inline-flex;
  align-items: center;
  gap: 0.3rem;
  font-size: 0.75rem;
  font-weight: 500;
  color: var(--ink-muted);
}

.recent-clear {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 16px; height: 16px;
  border: none;
  background: var(--hover);
  color: var(--ink-muted);
  border-radius: 50%;
  cursor: pointer;
  margin-left: 0.2rem;
}
.recent-clear:hover { color: var(--ink-primary); }

.suggest-chips {
  display: flex;
  flex-wrap: wrap;
  justify-content: center;
  gap: 0.5rem;
  max-width: 560px;
}

.suggest-chip {
  padding: 0.4rem 0.85rem;
  background: var(--card);
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  color: var(--ink-secondary);
  font-size: 0.8125rem;
  cursor: pointer;
  transition: border-color var(--dur-fast) var(--ease-standard), color var(--dur-fast) var(--ease-standard), background-color var(--dur-fast) var(--ease-standard);
  max-width: 100%;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.suggest-chip:hover {
  border-color: var(--primary);
  color: var(--primary-text);
  background: var(--primary-tint);
}

.suggest-chip.recent {
  background: var(--surface);
  border-color: transparent;
}

/* 响应式 */
@media (max-width: 960px) {
  .rag-container { padding: 0 1rem; }
  .rag-header { padding: 1rem 0 0.75rem; }
  .search-options { flex-wrap: wrap; gap: 0.75rem 1.25rem; }
  .stats-mini { margin-left: 0; }
}
</style>
