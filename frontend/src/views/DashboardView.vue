<!-- Copyright (c) 2026 左岚. All rights reserved. -->
<!-- DashboardView.vue - 作家仪表盘 (Premium Redesign) -->
<script setup>
import { useProjectStore } from '../stores/project'
import { useRouter } from 'vue-router'
import { ref, computed } from 'vue'

const projectStore = useProjectStore()
const router = useRouter()

const recentActivity = computed(() => (projectStore.activities || []).slice(0, 5))

function formatRelativeTime(timestamp) {
  const now = Math.floor(Date.now() / 1000)
  const diff = now - timestamp

  if (diff < 60) return '刚刚'
  if (diff < 3600) return Math.floor(diff / 60) + '分钟前'
  if (diff < 86400) return Math.floor(diff / 3600) + '小时前'
  if (diff < 604800) return Math.floor(diff / 86400) + '天前'

  return new Date(timestamp * 1000).toLocaleDateString()
}

function getActivityIcon(type) {
  switch (type) {
    case 'write':
      return '<svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor" class="size-5"><path stroke-linecap="round" stroke-linejoin="round" d="m16.862 4.487 1.687-1.688a1.875 1.875 0 1 1 2.652 2.652L10.582 16.07a4.5 4.5 0 0 1-1.897 1.13L6 18l.8-2.685a4.5 4.5 0 0 1 1.13-1.897l8.932-8.931Zm0 0L19.5 7.125M18 14v4.75A2.25 2.25 0 0 1 15.75 21H5.25A2.25 2.25 0 0 1 3 18.75V8.25A2.25 2.25 0 0 1 5.25 6H10" /></svg>'
    case 'outline':
      return '<svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor" class="size-5"><path stroke-linecap="round" stroke-linejoin="round" d="M12 6.042A8.967 8.967 0 0 0 6 3.75c-1.052 0-2.062.18-3 .512v14.25A8.987 8.987 0 0 1 6 18c2.305 0 4.408.867 6 2.292m0-14.25a8.966 8.966 0 0 1 6-2.292c1.052 0 2.062.18 3 .512v14.25A8.987 8.987 0 0 0 18 18a8.967 8.967 0 0 0-6 2.292m0-14.25v14.25" /></svg>'
    case 'entity':
      return '<svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor" class="size-5"><path stroke-linecap="round" stroke-linejoin="round" d="M15.75 6a3.75 3.75 0 1 1-7.5 0 3.75 3.75 0 0 1 7.5 0ZM4.501 20.118a7.5 7.5 0 0 1 14.998 0A17.933 17.933 0 0 1 12 21.75c-2.676 0-5.216-.584-7.499-1.632Z" /></svg>'
    case 'ai':
      return '<svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor" class="size-5"><path stroke-linecap="round" stroke-linejoin="round" d="M9.813 15.904 9 18.75l-.813-2.846a4.5 4.5 0 0 0-3.09-3.09L2.25 12l2.846-.813a4.5 4.5 0 0 0 3.09-3.09L9 5.25l.813 2.846a4.5 4.5 0 0 0 3.09 3.09L15.75 12l-2.846.813a4.5 4.5 0 0 0-3.09 3.09ZM18.259 8.715 18 9.75l-.259-1.035a3.375 3.375 0 0 0-2.455-2.456L14.25 6l1.036-.259a3.375 3.375 0 0 0 2.455-2.456L18 2.25l.259 1.035a3.375 3.375 0 0 0 2.456 2.456L21.75 6l-1.035.259a3.375 3.375 0 0 0-2.456 2.456ZM16.894 20.567 16.5 21.75l-.394-1.183a2.25 2.25 0 0 0-1.423-1.423L13.5 18.75l1.183-.394a2.25 2.25 0 0 0 1.423-1.423l.394-1.183.394 1.183a2.25 2.25 0 0 0 1.423 1.423l1.183.394-1.183.394a2.25 2.25 0 0 0-1.423 1.423Z" /></svg>'
    default:
      return '<svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor" class="size-5"><path stroke-linecap="round" stroke-linejoin="round" d="M12 6v6h4.5m4.5 0a9 9 0 1 1-18 0 9 9 0 0 1 18 0Z" /></svg>'
  }
}

const quickActions = [
  {
    icon: '<svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor" class="size-6"><path stroke-linecap="round" stroke-linejoin="round" d="m16.862 4.487 1.687-1.688a1.875 1.875 0 1 1 2.652 2.652L10.582 16.07a4.5 4.5 0 0 1-1.897 1.13L6 18l.8-2.685a4.5 4.5 0 0 1 1.13-1.897l8.932-8.931Zm0 0L19.5 7.125M18 14v4.75A2.25 2.25 0 0 1 15.75 21H5.25A2.25 2.25 0 0 1 3 18.75V8.25A2.25 2.25 0 0 1 5.25 6H10" /></svg>',
    label: '继续写作',
    desc: '回到上次的章节',
    action: () => router.push('/workspace/write'),
    theme: 'indigo'
  },
  {
    icon: '<svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor" class="size-6"><path stroke-linecap="round" stroke-linejoin="round" d="M12 6.042A8.967 8.967 0 0 0 6 3.75c-1.052 0-2.062.18-3 .512v14.25A8.987 8.987 0 0 1 6 18c2.305 0 4.408.867 6 2.292m0-14.25a8.966 8.966 0 0 1 6-2.292c1.052 0 2.062.18 3 .512v14.25A8.987 8.987 0 0 0 18 18a8.967 8.967 0 0 0-6 2.292m0-14.25v14.25" /></svg>',
    label: '大纲规划',
    desc: '梳理剧情脉络',
    action: () => router.push('/workspace/outline'),
    theme: 'emerald'
  },
  {
    icon: '<svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor" class="size-6"><path stroke-linecap="round" stroke-linejoin="round" d="M15.75 6a3.75 3.75 0 1 1-7.5 0 3.75 3.75 0 0 1 7.5 0ZM4.501 20.118a7.5 7.5 0 0 1 14.998 0A17.933 17.933 0 0 1 12 21.75c-2.676 0-5.216-.584-7.499-1.632Z" /></svg>',
    label: '角色设定',
    desc: '管理世界观与人物',
    action: () => router.push('/workspace/entities'),
    theme: 'amber'
  },
  {
    icon: '<svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor" class="size-6"><path stroke-linecap="round" stroke-linejoin="round" d="m21 21-5.197-5.197m0 0A7.5 7.5 0 1 0 5.196 5.196a7.5 7.5 0 0 0 10.607 10.607Z" /></svg>',
    label: 'RAG 助手',
    desc: '智能知识检索',
    action: () => router.push('/workspace/rag'),
    theme: 'purple'
  }
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
      <header class="header-section fade-in">
        <div class="header-content">
          <h1 class="welcome-text">
            <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor" class="welcome-icon"><path stroke-linecap="round" stroke-linejoin="round" d="M12 3v2.25m6.364.386-1.591 1.591M21 12h-2.25m-.386 6.364-1.591-1.591M12 18.75V21m-4.773-4.227-1.591 1.591M5.25 12H3m4.227-4.773L5.636 5.636M15.75 12a3.75 3.75 0 1 1-7.5 0 3.75 3.75 0 0 1 7.5 0Z" /></svg>
            早安，作家
          </h1>
          <p class="project-info">
            正在创作：<span class="project-name">{{ projectStore.title || '未命名项目' }}</span>
          </p>
        </div>
      </header>

      <!-- 未初始化引导 -->
      <div v-if="!projectStore.initialized" class="init-guide fade-in">
        <div class="init-guide-card">
          <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor" class="init-guide-icon">
            <path stroke-linecap="round" stroke-linejoin="round" d="M9.813 15.904 9 18.75l-.813-2.846a4.5 4.5 0 0 0-3.09-3.09L2.25 12l2.846-.813a4.5 4.5 0 0 0 3.09-3.09L9 5.25l.813 2.846a4.5 4.5 0 0 0 3.09 3.09L15.75 12l-2.846.813a4.5 4.5 0 0 0-3.09 3.09ZM18.259 8.715 18 9.75l-.259-1.035a3.375 3.375 0 0 0-2.455-2.456L14.25 6l1.036-.259a3.375 3.375 0 0 0 2.455-2.456L18 2.25l.259 1.035a3.375 3.375 0 0 0 2.456 2.456L21.75 6l-1.035.259a3.375 3.375 0 0 0-2.456 2.456Z" />
          </svg>
          <h3>项目尚未初始化</h3>
          <p>前往项目管理页面，使用 AI 一键初始化来生成大纲和世界观设定</p>
          <button class="btn btn-primary" @click="router.push('/workspace/project')">
            <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor" class="size-5">
              <path stroke-linecap="round" stroke-linejoin="round" d="M13.5 4.5 21 12m0 0-7.5 7.5M21 12H3" />
            </svg>
            前往初始化
          </button>
        </div>
      </div>

      <!-- 核心数据看板 -->
      <template v-if="projectStore.initialized">
      <section class="stats-grid stagger-in">
        <div class="stat-card">
          <div class="stat-icon-wrapper indigo-gradient">
            <span class="stat-label-icon">章</span>
          </div>
          <div class="stat-details">
            <span class="stat-value">{{ projectStore.totalChapters }}</span>
            <span class="stat-key">总章节</span>
          </div>
        </div>

        <div class="stat-card">
          <div class="stat-icon-wrapper pink-gradient">
            <span class="stat-label-icon">字</span>
          </div>
          <div class="stat-details">
            <span class="stat-value">{{ (projectStore.totalWords / 10000).toFixed(1) }}<span class="unit">万</span></span>
            <span class="stat-key">总字数</span>
          </div>
        </div>

        <div class="stat-card">
          <div class="stat-icon-wrapper orange-gradient">
            <span class="stat-label-icon">类</span>
          </div>
          <div class="stat-details">
            <span class="stat-value text-ellipsis">{{ projectStore.genre || '未设定' }}</span>
            <span class="stat-key">题材</span>
          </div>
        </div>

        <div class="stat-card">
          <div class="stat-icon-wrapper teal-gradient">
            <span class="stat-label-icon">进</span>
          </div>
          <div class="stat-details">
            <span class="stat-value text-ellipsis">{{ projectStore.currentChapter }}</span>
            <span class="stat-key">当前进度</span>
          </div>
        </div>
      </section>

      <!-- 主要内容网格 -->
      <div class="main-content-grid">
        <!-- 左侧：快捷操作与目标 -->
        <div class="content-left stagger-in-2">

          <!-- 快捷操作卡片 -->
          <div class="premium-card actions-card">
            <h3 class="card-title">快捷工坊</h3>
            <div class="actions-grid">
              <button
                v-for="action in quickActions"
                :key="action.label"
                class="action-item"
                :class="`theme-${action.theme}`"
                @click="action.action"
              >
                <div class="action-icon-box" v-html="action.icon"></div>
                <div class="action-text">
                  <span class="action-label">{{ action.label }}</span>
                  <span class="action-desc">{{ action.desc }}</span>
                </div>
              </button>
            </div>
          </div>

          <!-- 创作目标卡片 -->
          <div class="premium-card goal-card">
            <div class="card-header">
              <h3 class="card-title">创作里程碑</h3>
              <span class="goal-target">目标 {{ targetDisplay }}</span>
            </div>
            <div class="progress-wrapper">
              <div class="progress-track">
                <div class="progress-fill" :style="{ width: wordCountProgress + '%' }">
                  <div class="progress-glow"></div>
                </div>
              </div>
            </div>
            <p class="goal-hint">
              <span class="highlight">{{ remainingWords }}</span> 字待完成，保持热爱，奔赴山海。
            </p>
          </div>
        </div>

        <!-- 右侧：动态时间轴 -->
        <div class="content-right stagger-in-3">
          <div class="premium-card activity-card">
            <h3 class="card-title">最近动态</h3>

            <div v-if="recentActivity.length > 0" class="timeline-container">
              <div v-for="(item, index) in recentActivity" :key="item.id" class="timeline-item">
                <div class="timeline-line" v-if="index !== recentActivity.length - 1"></div>
                <div class="timeline-marker" :class="`marker-${item.type}`">
                  <div class="marker-dot"></div>
                </div>
                <div class="timeline-content">
                  <div class="timeline-header">
                    <span class="timeline-title">{{ item.title }}</span>
                    <span class="timeline-time">{{ formatRelativeTime(item.timestamp) }}</span>
                  </div>
                  <div class="timeline-type">
                    <span class="type-badge" :class="`badge-${item.type}`" v-html="getActivityIcon(item.type) + ' ' + (item.type === 'write' ? '写作' : item.type === 'outline' ? '大纲' : '设定')"></span>
                  </div>
                </div>
              </div>
            </div>

            <div v-else class="empty-timeline">
              <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor" class="empty-icon"><path stroke-linecap="round" stroke-linejoin="round" d="m16.862 4.487 1.687-1.688a1.875 1.875 0 1 1 2.652 2.652L10.582 16.07a4.5 4.5 0 0 1-1.897 1.13L6 18l.8-2.685a4.5 4.5 0 0 1 1.13-1.897l8.932-8.931Zm0 0L19.5 7.125M18 14v4.75A2.25 2.25 0 0 1 15.75 21H5.25A2.25 2.25 0 0 1 3 18.75V8.25A2.25 2.25 0 0 1 5.25 6H10" /></svg>
              <p>暂无活动，开始您的第一章吧</p>
            </div>
          </div>
        </div>
      </div>
      </template>
    </div>
  </div>
</template>

<style scoped>
/* Scoped Fonts & Variables */
.dashboard-scroll-container {
  height: 100%;
  width: 100%;
  overflow-y: auto;
  background-color: var(--bg-background);
  padding: 2.5rem 2rem;
}

.dashboard-container {
  max-width: 1100px;
  margin: 0 auto;
}

/* Base Typography */
h1, h2, h3, p { margin: 0; }
.card-title {
  font-size: 1.125rem;
  font-weight: 700;
  color: var(--text-primary);
  margin-bottom: 1.25rem;
  letter-spacing: -0.01em;
}

/* Header */
.header-section { margin-bottom: 2.5rem; }
.welcome-text {
  font-size: 2.25rem;
  font-weight: 800;
  color: var(--text-primary);
  letter-spacing: -0.03em;
  margin-bottom: 0.5rem;
  display: flex;
  align-items: center;
  gap: 0.75rem;
}
.welcome-icon {
  width: 2.5rem;
  height: 2.5rem;
  color: var(--primary);
}
.project-info { color: var(--text-secondary); font-size: 1.05rem; }
.project-name { color: var(--primary); font-weight: 600; background: rgba(139, 115, 85, 0.08); padding: 0.1rem 0.5rem; border-radius: 6px; }

/* Animations */
.fade-in { animation: fadeIn 0.6s ease-out; }
.stagger-in { animation: slideUp 0.6s ease-out 0.1s backwards; }
.stagger-in-2 { animation: slideUp 0.6s ease-out 0.2s backwards; }
.stagger-in-3 { animation: slideUp 0.6s ease-out 0.3s backwards; }
@keyframes fadeIn { from { opacity: 0; } to { opacity: 1; } }
@keyframes slideUp { from { opacity: 0; transform: translateY(20px); } to { opacity: 1; transform: translateY(0); } }

/* Stats Grid */
.stats-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 1.5rem;
  margin-bottom: 2.5rem;
}

.stat-card {
  background: white;
  border-radius: 16px;
  padding: 1.5rem;
  display: flex;
  align-items: center;
  gap: 1.25rem;
  box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.02), 0 2px 4px -1px rgba(0, 0, 0, 0.02);
  border: 1px solid rgba(229, 231, 235, 0.5);
  transition: all 0.3s ease;
}
.stat-card:hover { transform: translateY(-4px); box-shadow: 0 10px 15px -3px rgba(0, 0, 0, 0.05), 0 4px 6px -2px rgba(0, 0, 0, 0.025); }

.stat-icon-wrapper {
  width: 3.5rem; height: 3.5rem;
  border-radius: 14px;
  display: flex; align-items: center; justify-content: center;
  color: white; font-weight: 700; font-size: 1.25rem;
  box-shadow: 0 4px 6px -1px rgba(0,0,0,0.1);
}
.indigo-gradient { background: linear-gradient(135deg, #a08d74, #8b7355); }
.pink-gradient { background: linear-gradient(135deg, #ec4899, #db2777); }
.orange-gradient { background: linear-gradient(135deg, #f97316, #ea580c); }
.teal-gradient { background: linear-gradient(135deg, #14b8a6, #0d9488); }

.stat-details { display: flex; flex-direction: column; overflow: hidden; }
.stat-value { font-size: 1.5rem; font-weight: 800; color: var(--text-primary); line-height: 1.2; }
.stat-key { color: var(--text-muted); font-size: 0.8rem; font-weight: 500; text-transform: uppercase; letter-spacing: 0.05em; margin-top: 2px; }
.text-ellipsis { white-space: nowrap; overflow: hidden; text-overflow: ellipsis; max-width: 120px; }
.unit { font-size: 0.875rem; font-weight: 600; color: var(--text-secondary); margin-left: 2px; }

/* Main Grid */
.main-content-grid {
  display: grid;
  grid-template-columns: 2fr 1.2fr;
  gap: 2rem;
}
.content-left, .content-right { display: flex; flex-direction: column; gap: 2rem; }

/* Premium Card Base */
.premium-card {
  background: white;
  border-radius: 20px;
  padding: 1.75rem;
  box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.02), 0 2px 4px -1px rgba(0, 0, 0, 0.02);
  border: 1px solid rgba(229, 231, 235, 0.5);
}

/* Actions */
.actions-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 1rem;
}
.action-item {
  display: flex; align-items: center; gap: 1rem;
  padding: 1.25rem;
  border: 1px solid #f3f4f6;
  border-radius: 14px;
  background: white;
  cursor: pointer;
  transition: all 0.2s cubic-bezier(0.4, 0, 0.2, 1);
  text-align: left;
}
.action-item:hover { border-color: transparent; transform: translateY(-2px); }

/* Action Themes */
.theme-indigo:hover { background: #faf8f4; border-color: #c7d2fe; }
.theme-indigo .action-icon-box { background: #f0ebe3; color: #5c4a32; }

.theme-emerald:hover { background: #ecfdf5; border-color: #a7f3d0; }
.theme-emerald .action-icon-box { background: #d1fae5; color: #047857; }

.theme-amber:hover { background: #fffbeb; border-color: #fde68a; }
.theme-amber .action-icon-box { background: #fef3c7; color: #b45309; }

.theme-purple:hover { background: #f5f3ff; border-color: #ddd6fe; }
.theme-purple .action-icon-box { background: #f0ebe3; color: #7c6545; }

.action-icon-box {
  width: 3rem; height: 3rem;
  flex-shrink: 0;
  border-radius: 12px;
  display: flex; align-items: center; justify-content: center;
  transition: all 0.2s;
}
.action-text { display: flex; flex-direction: column; }
.action-label { font-weight: 600; color: var(--text-primary); font-size: 1rem; }
.action-desc { font-size: 0.75rem; color: var(--text-muted); margin-top: 2px; }

/* Goal Card */
.card-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 1rem; }
.goal-target { font-size: 0.875rem; font-weight: 600; color: var(--primary); background: #faf8f4; padding: 2px 8px; border-radius: 6px; }

.progress-wrapper { margin: 1rem 0 1.5rem; }
.progress-track {
  height: 12px;
  background: #f3f4f6;
  border-radius: 10px;
  overflow: hidden;
}
.progress-fill {
  height: 100%;
  background: linear-gradient(90deg, #8b7355, #a08d74, #c9a96e);
  border-radius: 10px;
  position: relative;
  transition: width 0.8s cubic-bezier(0.34, 1.56, 0.64, 1);
}
.progress-glow {
  position: absolute; right: 0; top: 0; bottom: 0; width: 10px;
  background: white; opacity: 0.3; filter: blur(4px);
}
.goal-hint { color: var(--text-secondary); font-size: 0.9rem; }
.highlight { color: var(--text-primary); font-weight: 700; font-feature-settings: "tnum"; }

/* Timeline */
.timeline-container { padding: 0.5rem 0; }

.timeline-item {
  position: relative;
  padding-bottom: 1.5rem;
  padding-left: 1.5rem;
}
.timeline-item:last-child { padding-bottom: 0; }

.timeline-line {
  position: absolute; left: 7px; top: 22px; bottom: -10px;
  width: 2px; background: #e5e7eb;
}
.timeline-marker {
  position: absolute; left: 0; top: 5px;
  width: 16px; height: 16px;
  border-radius: 50%;
  display: flex; align-items: center; justify-content: center;
  z-index: 1;
  background: white;
}
.marker-dot { width: 8px; height: 8px; border-radius: 50%; background: #d1d5db; transition: all 0.3s; }
.timeline-item:hover .marker-dot { transform: scale(1.2); }

.timeline-content {
  background: white;
  padding: 0.875rem 1rem;
  border-radius: 12px;
  border: 1px solid #f3f4f6;
  transition: all 0.2s;
  box-shadow: 0 1px 2px 0 rgba(0, 0, 0, 0.03);
}
.timeline-content:hover {
  background: white;
  border-color: #e5e7eb;
  transform: translateX(4px);
  box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05);
}

.timeline-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: 0.35rem;
  gap: 1rem;
}
.timeline-title {
  font-weight: 600;
  color: var(--text-primary);
  font-size: 0.95rem;
  line-height: 1.4;
}
.timeline-time {
  font-size: 0.75rem;
  color: var(--text-muted);
  white-space: nowrap;
  flex-shrink: 0;
  margin-top: 2px;
}

.timeline-type { display: flex; align-items: center; }

.type-badge {
  display: inline-flex; align-items: center; gap: 4px;
  font-size: 0.75rem; padding: 2px 8px; border-radius: 6px; font-weight: 500;
  transition: all 0.2s;
}
.timeline-content:hover .type-badge { opacity: 0.9; }

.badge-write { background: #faf8f4; color: #5c4a32; }
.badge-outline { background: #ecfdf5; color: #065f46; }
.badge-entity { background: #fffbeb; color: #92400e; }
.badge-ai { background: #f5f3ff; color: #5b21b6; }
.badge-write svg, .badge-outline svg, .badge-entity svg, .badge-ai svg { width: 12px; height: 12px; }

.empty-timeline { text-align: center; color: var(--text-muted); padding: 2rem 0; }
.empty-icon { width: 2.5rem; height: 2.5rem; margin: 0 auto 0.5rem; opacity: 0.4; display: block; }

/* Init Guide */
.init-guide {
  display: flex;
  justify-content: center;
  padding: 3rem 0;
}

.init-guide-card {
  text-align: center;
  background: white;
  border-radius: 20px;
  padding: 3rem 2.5rem;
  max-width: 480px;
  box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.02), 0 2px 4px -1px rgba(0, 0, 0, 0.02);
  border: 1px solid rgba(229, 231, 235, 0.5);
}

.init-guide-icon {
  width: 3rem;
  height: 3rem;
  color: var(--primary);
  margin-bottom: 1rem;
}

.init-guide-card h3 {
  font-size: 1.25rem;
  font-weight: 700;
  color: var(--text-primary);
  margin-bottom: 0.5rem;
}

.init-guide-card p {
  color: var(--text-secondary);
  font-size: 0.9375rem;
  margin-bottom: 1.5rem;
  line-height: 1.6;
}

.init-guide-card .btn {
  gap: 0.375rem;
}
</style>
