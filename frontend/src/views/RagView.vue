<!-- Copyright (c) 2026 左岚. All rights reserved. -->
<!-- RagView.vue - 沉浸式检索中心 -->
<script setup>
import { ref } from 'vue'
import { ragApi } from '../api'

const query = ref('')
const mode = ref('hybrid')
const topK = ref(10)
const results = ref([])
const stats = ref(null)
const loading = ref(false)
const message = ref('')

async function search() {
  if (!query.value.trim()) return
  loading.value = true
  message.value = ''
  try {
    const { data } = await ragApi.search(query.value, mode.value, topK.value)
    if (data.error) {
      message.value = '注意: ' + data.error
      results.value = []
    } else {
      results.value = data.results
      message.value = `找到 ${results.value.length} 条相关内容`
    }
  } catch (e) {
    message.value = '检索失败：' + e.message
    results.value = []
  } finally {
    loading.value = false
  }
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
  const regex = new RegExp(`(${query.value})`, 'gi')
  return content.replace(regex, '<mark>$1</mark>')
}
</script>

<template>
  <div class="rag-layout">
    <div class="rag-container">
      <!-- 头部 / 搜索区 -->
      <header class="rag-header">
        <h1 class="page-title">知识检索</h1>
        <p class="page-subtitle">基于 RAG 技术，深度搜索全书剧情、设定与伏笔</p>
        
        <div class="search-box">
          <div class="search-input-wrapper">
            <input
              v-model="query"
              class="main-search-input"
              placeholder="输入关键词或问题（如：萧炎是在哪里遇到药老的？）"
              @keyup.enter="search"
              autofocus
            />
            <button class="btn btn-ai btn-search" @click="search" :disabled="loading">
              {{ loading ? 'Searching...' : 'Search' }}
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
      </header>

      <!-- 结果展示区 -->
      <main class="results-area">
        <div v-if="loading" class="loading-state">
           <div class="pulse-ring"></div>
           <p>正在穿越时空检索记忆...</p>
        </div>
        
        <div v-else-if="results.length > 0" class="results-list">
          <div class="results-meta">
            {{ message }}
          </div>
          
          <div v-for="(result, index) in results" :key="result.chunk_id" class="result-card">
            <div class="card-header">
              <div class="header-left">
                <span class="rank-badge">#{{ index + 1 }}</span>
                <span class="chapter-info">第 {{ result.chapter }} 章</span>
                <span class="scene-info" v-if="result.scene_index">Scene {{ result.scene_index }}</span>
              </div>
              <div class="header-right">
                <span class="score-text">匹配度 {{ (result.score * 100).toFixed(1) }}%</span>
                <span class="source-tag" :class="result.source">{{ result.source }}</span>
              </div>
            </div>
            
            <div class="card-content" v-html="highlightContent(result.content)"></div>
          </div>
        </div>
        
        <div v-else class="empty-state">
           <div v-if="message" class="error-msg">{{ message }}</div>
           <div v-else class="placeholder">
             <div class="placeholder-icon">🧠</div>
             <h3>等待指令</h3>
             <p>我可以帮您回顾之前的剧情、查找遗忘的设定，或者寻找灵感。</p>
           </div>
        </div>
      </main>
    </div>
  </div>
</template>

<style scoped>
/* Main Layout */
.rag-layout {
  height: 100%;
  width: 100%;
  overflow-y: auto;
  background-color: var(--bg-background);
  padding-bottom: 4rem;
}

.rag-container {
  max-width: 800px;
  margin: 0 auto;
  padding: 0 1.5rem;
}

/* Header */
.rag-header {
  padding: 3rem 0 2rem;
  text-align: center;
}

.page-title {
  font-size: 2rem;
  font-weight: 800;
  margin-bottom: 0.5rem;
  background: linear-gradient(135deg, var(--text-primary) 0%, #8b5cf6 100%);
  -webkit-background-clip: text;
  background-clip: text;
  -webkit-background-clip: text;
}

.page-subtitle {
  color: var(--text-secondary);
  font-size: 1rem;
  margin-bottom: 2.5rem;
}

/* Search Box */
.search-box {
  background: var(--bg-card);
  border: 1px solid var(--border);
  border-radius: var(--radius-lg);
  padding: 1.5rem;
  box-shadow: var(--shadow-lg);
  transition: transform 0.2s, box-shadow 0.2s;
}

.search-box:focus-within {
  border-color: var(--primary);
  box-shadow: 0 0 0 2px rgba(99, 102, 241, 0.2), var(--shadow-lg);
  transform: translateY(-2px);
}

.search-input-wrapper {
  display: flex;
  gap: 1rem;
  margin-bottom: 1rem;
}

.main-search-input {
  flex: 1;
  border: none;
  background: var(--bg-background);
  padding: 1rem 1.25rem;
  border-radius: var(--radius-md);
  font-size: 1.125rem;
  color: var(--text-primary);
  outline: none;
  box-shadow: inset 0 2px 4px rgba(0,0,0,0.05);
}

.btn-search {
  padding: 0 2rem;
  font-weight: 600;
}

.search-options {
  display: flex;
  align-items: center;
  gap: 1.5rem;
  padding-top: 0.5rem;
  border-top: 1px solid var(--border);
}

.option-group { display: flex; align-items: center; gap: 0.5rem; }
.option-label { font-size: 0.75rem; color: var(--text-muted); font-weight: 600; text-transform: uppercase; }
.option-select {
  background: transparent;
  border: none;
  color: var(--text-secondary);
  font-size: 0.875rem;
  cursor: pointer;
}

.stats-mini { margin-left: auto; display: flex; gap: 0.75rem; }
.stat-pill {
  font-size: 0.75rem;
  background: var(--bg-secondary);
  padding: 2px 8px;
  border-radius: 999px;
  color: var(--text-muted);
}

/* Results */
.results-area { margin-top: 2rem; }

.results-meta {
  margin-bottom: 1rem;
  font-size: 0.875rem;
  color: var(--text-muted);
}

.result-card {
  background: var(--bg-card);
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  padding: 1.5rem;
  margin-bottom: 1rem;
  transition: transform 0.2s;
}

.result-card:hover { transform: translateY(-2px); box-shadow: var(--shadow-md); }

.card-header {
  display: flex;
  justify-content: space-between;
  margin-bottom: 1rem;
  font-size: 0.875rem;
}

.header-left { display: flex; gap: 0.75rem; align-items: center; }
.rank-badge {
  background: var(--primary);
  color: white;
  width: 24px; height: 24px;
  border-radius: 50%;
  display: flex; align-items: center; justify-content: center;
  font-weight: 700; font-size: 0.75rem;
}
.chapter-info { font-weight: 600; color: var(--text-primary); }
.scene-info { color: var(--text-muted); }

.header-right { display: flex; gap: 0.75rem; align-items: center; }
.score-text { color: var(--success); font-weight: 500; }
.source-tag { 
  font-size: 0.75rem; padding: 2px 6px; border-radius: 4px; text-transform: uppercase;
}
.hybrid { background: rgba(99, 102, 241, 0.1); color: var(--primary); }
.vector { background: rgba(34, 197, 94, 0.1); color: var(--success); }
.bm25 { background: rgba(245, 158, 11, 0.1); color: var(--warning); }

.card-content {
  color: var(--text-secondary);
  line-height: 1.7;
  font-size: 1rem;
}

.card-content :deep(mark) {
  background: rgba(251, 191, 36, 0.3);
  color: inherit;
  padding: 0 4px;
  border-radius: 2px;
}

/* Loading & Empty */
.loading-state { text-align: center; padding: 4rem 0; color: var(--text-muted); }
.pulse-ring {
  width: 40px; height: 40px; border: 3px solid var(--primary); border-radius: 50%;
  margin: 0 auto 1rem; animation: pulse 1.5s infinite;
}
@keyframes pulse { 0% { transform: scale(0.8); opacity: 0.8; } 100% { transform: scale(2); opacity: 0; } }

.empty-state { text-align: center; padding: 4rem 0; }
.placeholder-icon { font-size: 3rem; margin-bottom: 1rem; opacity: 0.5; }
.empty-state h3 { color: var(--text-secondary); margin-bottom: 0.5rem; }
.empty-state p { color: var(--text-muted); }
.error-msg { color: var(--error); background: rgba(239, 68, 68, 0.1); display: inline-block; padding: 0.5rem 1rem; border-radius: var(--radius-md); }
</style>
