<!-- Copyright (c) 2026 左岚. All rights reserved. -->
<!-- DashboardView.vue - 作家仪表盘(晴窗编辑部) -->
<script setup>
import { useProjectStore } from '../stores/project'
import { useRouter } from 'vue-router'
import { computed } from 'vue'
import {
  Sunrise, Sun, Moon,
  BookText, PenLine, Compass, Milestone,
  Map, Users, Search,
  Clock, Sparkles
} from 'lucide-vue-next'

const projectStore = useProjectStore()
const router = useRouter()

const recentActivity = computed(() => (projectStore.activities || []).slice(0, 5))

const greeting = computed(() => {
  const h = new Date().getHours()
  if (h < 5) return { icon: Moon, text: '夜深了，作家' }
  if (h < 11) return { icon: Sunrise, text: '早安，作家' }
  if (h < 18) return { icon: Sun, text: '午安，作家' }
  return { icon: Moon, text: '晚安，作家' }
})

function formatRelativeTime(timestamp) {
  const now = Math.floor(Date.now() / 1000)
  const diff = now - timestamp

  if (diff < 60) return '刚刚'
  if (diff < 3600) return Math.floor(diff / 60) + '分钟前'
  if (diff < 86400) return Math.floor(diff / 3600) + '小时前'
  if (diff < 604800) return Math.floor(diff / 86400) + '天前'

  return new Date(timestamp * 1000).toLocaleDateString()
}

const activityMeta = {
  write: { icon: PenLine, label: '写作' },
  outline: { icon: BookText, label: '大纲' },
  entity: { icon: Users, label: '设定' },
  ai: { icon: Sparkles, label: 'AI' }
}
function activityIcon(type) { return (activityMeta[type] || { icon: Clock }).icon }
function activityLabel(type) { return (activityMeta[type] || { label: '动态' }).label }

const stats = computed(() => [
  { icon: BookText, value: projectStore.totalChapters, unit: '', key: '总章节', to: '/workspace/write' },
  { icon: PenLine, value: (projectStore.totalWords / 10000).toFixed(1), unit: '万', key: '总字数', to: '/workspace/write' },
  { icon: Compass, value: projectStore.genre || '未设定', unit: '', key: '题材', ellipsis: true, to: '/workspace/project' },
  { icon: Milestone, value: projectStore.currentChapter, unit: '', key: '当前进度', ellipsis: true, to: '/workspace/write' }
])

const quickActions = [
  { icon: PenLine, label: '继续写作', desc: '回到上次的章节', action: () => router.push('/workspace/write') },
  { icon: BookText, label: '大纲规划', desc: '梳理剧情脉络', action: () => router.push('/workspace/outline') },
  { icon: Users, label: '角色设定', desc: '管理世界观与人物', action: () => router.push('/workspace/characters') },
  { icon: Search, label: 'RAG 助手', desc: '智能知识检索', action: () => router.push('/workspace/rag') }
]

const wordCountProgress = computed(() => {
  const target = projectStore.targetWords || 100000
  const current = projectStore.totalWords
  return Math.min((current / target) * 100, 100)
})

const targetDisplay = computed(() => {
  const target = projectStore.targetWords || 100000
  if (target >= 10000) return (target / 10000).toFixed(0) + '万字'
  return target + '字'
})

const remainingWords = computed(() => {
  const target = projectStore.targetWords || 100000
  return Math.max(target - projectStore.totalWords, 0).toLocaleString()
})
</script>

<template>
  <div class="dashboard-scroll-container">
    <div class="dashboard-container">
      <!-- 顶部欢迎区 -->
      <header class="header-section">
        <h1 class="welcome-text">
          <component :is="greeting.icon" class="welcome-icon" :size="22" :stroke-width="1.75" />
          {{ greeting.text }}
        </h1>
        <p class="project-info">
          正在创作：<span class="project-name">{{ projectStore.title || '未命名项目' }}</span>
        </p>
      </header>

      <!-- 未初始化引导 -->
      <div v-if="!projectStore.initialized" class="init-guide">
        <div class="init-guide-card">
          <Sparkles class="init-guide-icon" :size="40" :stroke-width="1.25" />
          <h3>项目尚未初始化</h3>
          <p>前往项目管理页面，使用 AI 一键初始化来生成大纲和世界观设定</p>
          <button class="btn btn-primary" @click="router.push('/workspace/project')">
            前往初始化
            <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor" class="size-5">
              <path stroke-linecap="round" stroke-linejoin="round" d="M13.5 4.5 21 12m0 0-7.5 7.5M21 12H3" />
            </svg>
          </button>
        </div>
      </div>

      <template v-if="projectStore.initialized">
      <!-- 核心数据看板 -->
      <section class="stats-grid">
        <div
          v-for="stat in stats"
          :key="stat.key"
          class="stat-card clickable"
          role="link"
          tabindex="0"
          :title="'前往' + (stat.to === '/workspace/project' ? '项目管理' : '章节创作')"
          @click="router.push(stat.to)"
          @keydown.enter="router.push(stat.to)"
        >
          <div class="stat-head">
            <component :is="stat.icon" :size="15" :stroke-width="1.75" />
            <span class="stat-key">{{ stat.key }}</span>
          </div>
          <span class="stat-value" :class="{ 'text-ellipsis': stat.ellipsis }">{{ stat.value }}<span v-if="stat.unit" class="unit">{{ stat.unit }}</span></span>
        </div>
      </section>

      <!-- 主要内容网格 -->
      <div class="main-content-grid">
        <!-- 左侧：快捷操作与目标 -->
        <div class="content-left">

          <!-- 快捷操作卡片 -->
          <div class="panel actions-card">
            <h3 class="card-title">快捷操作</h3>
            <div class="actions-grid">
              <button
                v-for="action in quickActions"
                :key="action.label"
                class="action-item"
                @click="action.action"
              >
                <div class="action-icon-box">
                  <component :is="action.icon" :size="20" :stroke-width="1.5" />
                </div>
                <div class="action-text">
                  <span class="action-label">{{ action.label }}</span>
                  <span class="action-desc">{{ action.desc }}</span>
                </div>
              </button>
            </div>
          </div>

          <!-- 创作里程碑卡片 -->
          <div class="panel goal-card">
            <div class="card-header">
              <h3 class="card-title">创作里程碑</h3>
              <span class="goal-target">目标 {{ targetDisplay }}</span>
            </div>
            <div class="progress-wrapper">
              <div class="progress-track">
                <div class="progress-fill" :style="{ width: wordCountProgress + '%' }"></div>
              </div>
              <span class="progress-pct tnum">{{ wordCountProgress.toFixed(0) }}%</span>
            </div>
            <p class="goal-hint">
              还剩 <span class="highlight tnum">{{ remainingWords }}</span> 字达成目标。
            </p>
          </div>
        </div>

        <!-- 右侧：动态时间轴 -->
        <div class="content-right">
          <div class="panel activity-card">
            <h3 class="card-title">最近动态</h3>

            <div v-if="recentActivity.length > 0" class="timeline-container">
              <div v-for="(item, index) in recentActivity" :key="item.id" class="timeline-item">
                <div class="timeline-line" v-if="index !== recentActivity.length - 1"></div>
                <div class="timeline-marker">
                  <component :is="activityIcon(item.type)" :size="13" :stroke-width="1.75" />
                </div>
                <div class="timeline-content">
                  <div class="timeline-header">
                    <span class="timeline-title">{{ item.title }}</span>
                    <span class="timeline-time">{{ formatRelativeTime(item.timestamp) }}</span>
                  </div>
                  <span class="type-badge">{{ activityLabel(item.type) }}</span>
                </div>
              </div>
            </div>

            <div v-else class="empty-timeline">
              <PenLine class="empty-icon" :size="36" :stroke-width="1.25" />
              <p>暂无活动</p>
              <button class="btn btn-primary btn-sm" @click="router.push('/workspace/write')">开始第一章</button>
            </div>
          </div>
        </div>
      </div>
      </template>
    </div>
  </div>
</template>

<style scoped>
.dashboard-scroll-container {
  height: 100%;
  width: 100%;
  overflow-y: auto;
  padding: 2rem;
}

.dashboard-container {
  max-width: 1100px;
  margin: 0 auto;
}

/* Base Typography */
h1, h2, h3, p { margin: 0; }
.card-title {
  font-size: 1rem;
  font-weight: 600;
  color: var(--ink-primary);
  margin-bottom: 1.1rem;
}

/* Header */
.header-section { margin-bottom: 1.75rem; }
.welcome-text {
  font-size: 1.375rem;
  font-weight: 600;
  color: var(--ink-primary);
  letter-spacing: -0.01em;
  margin-bottom: 0.5rem;
  display: flex;
  align-items: center;
  gap: 0.625rem;
}
.welcome-icon { color: var(--primary-text); }
.project-info { color: var(--ink-secondary); font-size: 0.9375rem; }
.project-name { color: var(--primary-on-tint); font-weight: 500; background: var(--primary-tint); padding: 0.15rem 0.5rem; border-radius: var(--radius-sm); }

/* Stats Grid — 白纸上的平边框卡 */
.stats-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 0.875rem;
  margin-bottom: 1.5rem;
}

.stat-card {
  background: var(--card);
  border: 1px solid var(--border);
  border-radius: var(--radius-lg);
  padding: 1rem 1.1rem;
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
  min-width: 0;
}

.stat-card.clickable {
  cursor: pointer;
  transition: border-color var(--dur-fast) var(--ease-standard), box-shadow var(--dur-fast) var(--ease-standard);
}

.stat-card.clickable:hover {
  border-color: var(--border-strong);
  box-shadow: var(--shadow-md);
}

.stat-card.clickable:focus-visible {
  outline: 2px solid var(--primary);
  outline-offset: 2px;
}

.stat-head {
  display: flex;
  align-items: center;
  gap: 0.4rem;
  color: var(--ink-muted);
}

.stat-key { font-size: 0.8125rem; font-weight: 500; }

.stat-value {
  font-family: var(--font-mono);
  font-feature-settings: "tnum";
  font-size: 1.375rem;
  font-weight: 600;
  color: var(--ink-primary);
  line-height: 1.2;
}
.text-ellipsis { white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.unit { font-family: var(--font-ui); font-size: 0.8125rem; font-weight: 500; color: var(--ink-secondary); margin-left: 2px; }

/* Main Grid */
.main-content-grid {
  display: grid;
  grid-template-columns: 2fr 1.2fr;
  gap: 0.875rem;
  align-items: start;
}
.content-left, .content-right { display: flex; flex-direction: column; gap: 0.875rem; }

/* Panel — 白纸上的分区容器 */
.panel {
  background: var(--card);
  border: 1px solid var(--border);
  border-radius: var(--radius-lg);
  padding: 1.25rem;
}

/* Actions — 台面色瓷贴 */
.actions-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 0.625rem;
}
.action-item {
  display: flex; align-items: center; gap: 0.875rem;
  padding: 0.875rem 1rem;
  border: 1px solid transparent;
  border-radius: var(--radius-md);
  background: var(--surface);
  cursor: pointer;
  transition: background-color var(--dur-fast) var(--ease-standard), border-color var(--dur-fast) var(--ease-standard);
  text-align: left;
}
.action-item:hover { background: var(--hover); border-color: var(--border); }

.action-icon-box {
  width: 2.5rem; height: 2.5rem;
  flex-shrink: 0;
  border-radius: var(--radius-md);
  display: flex; align-items: center; justify-content: center;
  background: var(--card);
  border: 1px solid var(--border);
  color: var(--ink-secondary);
  transition: background-color var(--dur-fast) var(--ease-standard), color var(--dur-fast) var(--ease-standard), border-color var(--dur-fast) var(--ease-standard);
}
.action-item:hover .action-icon-box {
  background: var(--primary-tint);
  border-color: transparent;
  color: var(--primary-on-tint);
}
.action-text { display: flex; flex-direction: column; min-width: 0; }
.action-label { font-weight: 500; color: var(--ink-primary); font-size: 0.9375rem; }
.action-desc { font-size: 0.75rem; color: var(--ink-muted); margin-top: 2px; }

/* Goal Card */
.card-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.75rem; }
.card-header .card-title { margin-bottom: 0; }
.goal-target { font-size: 0.8125rem; font-weight: 500; color: var(--primary-on-tint); background: var(--primary-tint); padding: 3px 8px; border-radius: var(--radius-sm); }

.progress-wrapper { display: flex; align-items: center; gap: 0.875rem; margin: 0.875rem 0 1rem; }
.progress-track {
  flex: 1;
  height: 8px;
  background: var(--surface);
  border-radius: var(--radius-pill);
  overflow: hidden;
  border: 1px solid var(--border);
}
.progress-fill {
  height: 100%;
  background: var(--primary);
  border-radius: var(--radius-pill);
  transition: width 0.8s var(--ease-emerge);
}
.progress-pct { font-size: 0.875rem; font-weight: 500; color: var(--primary-text); min-width: 2.5rem; text-align: right; }
.goal-hint { color: var(--ink-secondary); font-size: 0.875rem; }
.highlight { color: var(--ink-primary); font-weight: 600; }

/* Timeline */
.timeline-container { padding: 0.25rem 0; }

.timeline-item {
  position: relative;
  padding-bottom: 1rem;
  padding-left: 2rem;
}
.timeline-item:last-child { padding-bottom: 0; }

.timeline-line {
  position: absolute; left: 12px; top: 26px; bottom: -6px;
  width: 1px; background: var(--border);
}
.timeline-marker {
  position: absolute; left: 0; top: 2px;
  width: 26px; height: 26px;
  border-radius: 50%;
  display: flex; align-items: center; justify-content: center;
  z-index: 1;
  background: var(--surface);
  border: 1px solid var(--border);
  color: var(--ink-secondary);
}

.timeline-content {
  background: var(--surface);
  padding: 0.75rem 0.875rem;
  border-radius: var(--radius-md);
  transition: background-color var(--dur-fast) var(--ease-standard);
}
.timeline-content:hover {
  background: var(--hover);
}

.timeline-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: 0.4rem;
  gap: 1rem;
}
.timeline-title {
  font-weight: 500;
  color: var(--ink-primary);
  font-size: 0.875rem;
  line-height: 1.4;
}
.timeline-time {
  font-family: var(--font-mono);
  font-feature-settings: "tnum";
  font-size: 0.6875rem;
  color: var(--ink-muted);
  white-space: nowrap;
  flex-shrink: 0;
  margin-top: 2px;
}

.type-badge {
  display: inline-flex; align-items: center;
  font-size: 0.75rem; padding: 2px 8px; border-radius: var(--radius-sm); font-weight: 500;
  background: var(--card);
  color: var(--ink-secondary);
  border: 1px solid var(--border);
}

.empty-timeline { text-align: center; color: var(--ink-muted); padding: 2rem 0; font-size: 0.875rem; }
.empty-icon { color: var(--ink-muted); opacity: 0.4; margin: 0 auto 0.5rem; display: block; }

/* Init Guide */
.init-guide {
  display: flex;
  justify-content: center;
  padding: 3rem 0;
}

.init-guide-card {
  text-align: center;
  background: var(--card);
  border-radius: var(--radius-lg);
  padding: 2.5rem 2.25rem;
  max-width: 480px;
  border: 1px solid var(--border);
}

.init-guide-icon {
  color: var(--primary-text);
  margin-bottom: 1rem;
}

.init-guide-card h3 {
  font-size: 1.125rem;
  font-weight: 600;
  color: var(--ink-primary);
  margin-bottom: 0.625rem;
}

.init-guide-card p {
  color: var(--ink-secondary);
  font-size: 0.9375rem;
  margin-bottom: 1.5rem;
  line-height: 1.6;
}

.init-guide-card .btn {
  gap: 0.5rem;
}

/* Responsive */
@media (max-width: 900px) {
  .stats-grid { grid-template-columns: repeat(2, 1fr); }
  .main-content-grid { grid-template-columns: 1fr; }
}
</style>
