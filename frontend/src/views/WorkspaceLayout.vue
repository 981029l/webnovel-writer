<!-- Copyright (c) 2026 左岚. All rights reserved. -->
<!-- WorkspaceLayout.vue - 工作台布局（侧边栏包装器） -->
<script setup>
import { RouterLink, RouterView, useRoute, useRouter } from 'vue-router'
import { useProjectStore } from '../stores/project'
import { onMounted, onUnmounted, ref } from 'vue'

const route = useRoute()
const router = useRouter()
const projectStore = useProjectStore()
const isMobileViewport = ref(false)
const showMobileWorkspaceNav = ref(false)
const floatingMenuPos = ref({ x: 0, y: 0 })
const isDraggingMenu = ref(false)
let dragOffsetX = 0
let dragOffsetY = 0

function clampFloatingMenu() {
  if (typeof window === 'undefined') return
  const maxX = Math.max(12, window.innerWidth - 64)
  const maxY = Math.max(12, window.innerHeight - 64)
  floatingMenuPos.value = {
    x: Math.min(Math.max(12, floatingMenuPos.value.x), maxX),
    y: Math.min(Math.max(12, floatingMenuPos.value.y), maxY)
  }
}

function setDefaultFloatingMenuPos() {
  if (typeof window === 'undefined') return
  floatingMenuPos.value = { x: window.innerWidth - 68, y: window.innerHeight - 84 }
  clampFloatingMenu()
}

function onFloatingMenuPointerMove(event) {
  if (!isDraggingMenu.value) return
  floatingMenuPos.value = { x: event.clientX - dragOffsetX, y: event.clientY - dragOffsetY }
  clampFloatingMenu()
}

function stopFloatingMenuDrag() {
  isDraggingMenu.value = false
}

function startFloatingMenuDrag(event) {
  isDraggingMenu.value = true
  dragOffsetX = event.clientX - floatingMenuPos.value.x
  dragOffsetY = event.clientY - floatingMenuPos.value.y
}

function syncMobileWorkspaceLayout() {
  if (typeof window === 'undefined') return
  isMobileViewport.value = window.innerWidth <= 768
  if (!isMobileViewport.value) {
    showMobileWorkspaceNav.value = false
  } else if (!floatingMenuPos.value.x && !floatingMenuPos.value.y) {
    setDefaultFloatingMenuPos()
  }
  clampFloatingMenu()
}

onMounted(() => {
  // Only fetch if store doesn't already have data (e.g., page refresh)
  // Avoids racing with child view's own fetchStatus()
  if (projectStore.projectRoot && !projectStore.title) {
    projectStore.fetchStatus()
  }
  syncMobileWorkspaceLayout()
  if (isMobileViewport.value) setDefaultFloatingMenuPos()
  window.addEventListener('resize', syncMobileWorkspaceLayout)
  window.addEventListener('pointermove', onFloatingMenuPointerMove)
  window.addEventListener('pointerup', stopFloatingMenuDrag)
})

onUnmounted(() => {
  window.removeEventListener('resize', syncMobileWorkspaceLayout)
  window.removeEventListener('pointermove', onFloatingMenuPointerMove)
  window.removeEventListener('pointerup', stopFloatingMenuDrag)
})

const navItems = [
  {
    path: '/workspace/dashboard',
    icon: '<svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor" class="size-6"><path stroke-linecap="round" stroke-linejoin="round" d="m2.25 12 8.954-8.955c.44-.439 1.152-.439 1.591 0L21.75 12M4.5 9.75v10.125c0 .621.504 1.125 1.125 1.125H9.75v-4.875c0-.621.504-1.125 1.125-1.125h2.25c.621 0 1.125.504 1.125 1.125V21h4.125c.621 0 1.125-.504 1.125-1.125V9.75M8.25 21h8.25" /></svg>',
    label: '仪表盘'
  },
  {
    path: '/workspace/project',
    icon: '<svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor" class="size-6"><path stroke-linecap="round" stroke-linejoin="round" d="M3.75 6A2.25 2.25 0 0 1 6 3.75h2.25A2.25 2.25 0 0 1 10.5 6v2.25a2.25 2.25 0 0 1-2.25 2.25H6a2.25 2.25 0 0 1-2.25-2.25V6ZM3.75 15.75A2.25 2.25 0 0 1 6 13.5h2.25a2.25 2.25 0 0 1 2.25 2.25V18a2.25 2.25 0 0 1-2.25 2.25H6A2.25 2.25 0 0 1 3.75 18v-2.25ZM13.5 6a2.25 2.25 0 0 1 2.25-2.25H18A2.25 2.25 0 0 1 20.25 6v2.25A2.25 2.25 0 0 1 18 10.5h-2.25a2.25 2.25 0 0 1-2.25-2.25V6ZM13.5 15.75a2.25 2.25 0 0 1 2.25-2.25H18a2.25 2.25 0 0 1 2.25 2.25V18A2.25 2.25 0 0 1 18 20.25h-2.25a2.25 2.25 0 0 1-2.25-2.25v-2.25Z" /></svg>',
    label: '项目管理'
  },
  {
    path: '/workspace/prompts',
    icon: '<svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor" class="size-6"><path stroke-linecap="round" stroke-linejoin="round" d="M16.5 3.75v16.5m-9-12.75h9m-9 4.5h9m-9 4.5h4.5M6 3.75h12A2.25 2.25 0 0 1 20.25 6v12A2.25 2.25 0 0 1 18 20.25H6A2.25 2.25 0 0 1 3.75 18V6A2.25 2.25 0 0 1 6 3.75Z" /></svg>',
    label: '提示词配置'
  },
  {
    path: '/workspace/outline',
    icon: '<svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor" class="size-6"><path stroke-linecap="round" stroke-linejoin="round" d="M12 6.042A8.967 8.967 0 0 0 6 3.75c-1.052 0-2.062.18-3 .512v14.25A8.987 8.987 0 0 1 6 18c2.305 0 4.408.867 6 2.292m0-14.25a8.966 8.966 0 0 1 6-2.292c1.052 0 2.062.18 3 .512v14.25A8.987 8.987 0 0 0 18 18a8.967 8.967 0 0 0-6 2.292m0-14.25v14.25" /></svg>',
    label: '大纲编辑'
  },
  {
    path: '/workspace/write',
    icon: '<svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor" class="size-6"><path stroke-linecap="round" stroke-linejoin="round" d="m16.862 4.487 1.687-1.688a1.875 1.875 0 1 1 2.652 2.652L10.582 16.07a4.5 4.5 0 0 1-1.897 1.13L6 18l.8-2.685a4.5 4.5 0 0 1 1.13-1.897l8.932-8.931Zm0 0L19.5 7.125M18 14v4.75A2.25 2.25 0 0 1 15.75 21H5.25A2.25 2.25 0 0 1 3 18.75V8.25A2.25 2.25 0 0 1 5.25 6H10" /></svg>',
    label: '章节创作'
  },
  // {
  //   path: '/workspace/entities',
  //   icon: '<svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor" class="size-6"><path stroke-linecap="round" stroke-linejoin="round" d="m21 7.5-9-5.25L3 7.5m18 0-9 5.25m9-5.25v9l-9 5.25M3 7.5l9 5.25M3 7.5v9l9 5.25m0-9v9" /></svg>',
  //   label: '实体管理'
  // },
  {
    path: '/workspace/rag',
    icon: '<svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor" class="size-6"><path stroke-linecap="round" stroke-linejoin="round" d="m21 21-5.197-5.197m0 0A7.5 7.5 0 1 0 5.196 5.196a7.5 7.5 0 0 0 10.607 10.607Z" /></svg>',
    label: 'RAG 检索'
  },
  {
    path: '/workspace/characters',
    icon: '<svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor" class="size-6"><path stroke-linecap="round" stroke-linejoin="round" d="M15 19.128a9.38 9.38 0 0 0 2.625.372 9.337 9.337 0 0 0 4.121-.952 4.125 4.125 0 0 0-7.533-2.493M15 19.128v-.003c0-1.113-.285-2.16-.786-3.07M15 19.128v.106A12.318 12.318 0 0 1 8.624 21c-2.331 0-4.512-.645-6.374-1.766l-.001-.109a6.375 6.375 0 0 1 11.964-3.07M12 6.375a3.375 3.375 0 1 1-6.75 0 3.375 3.375 0 0 1 6.75 0Zm8.25 2.25a2.625 2.625 0 1 1-5.25 0 2.625 2.625 0 0 1 5.25 0Z" /></svg>',
    label: '角色管理'
  },
  {
    path: '/workspace/relations',
    icon: '<svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor" class="size-6"><path stroke-linecap="round" stroke-linejoin="round" d="M7.217 10.907a2.25 2.25 0 1 0 0 2.186m0-2.186c.18.324.283.696.283 1.093s-.103.77-.283 1.093m0-2.186 9.566-5.314m-9.566 7.5 9.566 5.314m0 0a2.25 2.25 0 1 0 3.935 2.186 2.25 2.25 0 0 0-3.935-2.186Zm0-12.814a2.25 2.25 0 1 0 3.933-2.185 2.25 2.25 0 0 0-3.933 2.185Z" /></svg>',
    label: '关系图谱'
  },
  {
    path: '/workspace/fanqie',
    icon: '<svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor" class="size-6"><path stroke-linecap="round" stroke-linejoin="round" d="M3 16.5v2.25A2.25 2.25 0 0 0 5.25 21h13.5A2.25 2.25 0 0 0 21 18.75V16.5m-13.5-9L12 3m0 0 4.5 4.5M12 3v13.5" /></svg>',
    label: '番茄上传'
  }
]

function goBackToProjects() {
  projectStore.clearProject()
  router.push('/')
}

function closeMobileWorkspaceNav() {
  if (isMobileViewport.value) showMobileWorkspaceNav.value = false
}

function isActiveRoute(itemPath) {
  if (itemPath === '/workspace/dashboard') {
    return route.path === '/workspace/dashboard'
  }
  return route.path.startsWith(itemPath)
}
</script>

<template>
  <div class="workspace-layout">
    <div v-if="isMobileViewport && showMobileWorkspaceNav" class="workspace-mobile-backdrop" @click="showMobileWorkspaceNav = false"></div>

    <!-- Sidebar -->
    <aside class="sidebar" :class="{ 'mobile-overlay': isMobileViewport, 'mobile-open': showMobileWorkspaceNav }">
      <div class="sidebar-header">
        <div class="sidebar-header-row sidebar-header-row-end">
          <button v-if="isMobileViewport" class="mobile-close-btn" @click="showMobileWorkspaceNav = false" title="关闭导航">
            <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor" class="size-5">
              <path stroke-linecap="round" stroke-linejoin="round" d="M6 18 18 6M6 6l12 12" />
            </svg>
          </button>
        </div>
      </div>

      <!-- Current project name -->
      <div class="project-name-wrapper">
        <div class="project-name-display">
          <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor" class="size-5">
            <path stroke-linecap="round" stroke-linejoin="round" d="M12 6.042A8.967 8.967 0 0 0 6 3.75c-1.052 0-2.062.18-3 .512v14.25A8.987 8.987 0 0 1 6 18c2.305 0 4.408.867 6 2.292m0-14.25a8.966 8.966 0 0 1 6-2.292c1.052 0 2.062.18 3 .512v14.25A8.987 8.987 0 0 0 18 18a8.967 8.967 0 0 0-6 2.292m0-14.25v14.25" />
          </svg>
          <span class="project-title">{{ projectStore.title || '未命名项目' }}</span>
        </div>
      </div>

      <!-- Navigation -->
      <nav class="sidebar-nav">
        <RouterLink
          v-for="item in navItems"
          :key="item.path"
          :to="item.path"
          class="nav-item"
          @click="closeMobileWorkspaceNav"
          :class="{ active: isActiveRoute(item.path) }"
        >
          <span class="nav-icon" v-html="item.icon"></span>
          <span class="nav-label">{{ item.label }}</span>
          <div v-if="isActiveRoute(item.path)" class="active-indicator"></div>
        </RouterLink>
      </nav>

      <!-- Footer -->
      <div class="sidebar-footer">
        <div v-if="projectStore.initialized" class="project-info">
          <div class="project-genre">{{ projectStore.genre || '未设置题材' }}</div>
          <div class="project-stats">
            <span>{{ projectStore.totalChapters }} 章</span>
            <span class="separator">·</span>
            <span>{{ (projectStore.totalWords / 10000).toFixed(1) }} 万字</span>
          </div>
        </div>
        <div v-else class="project-empty">
          项目未初始化
        </div>
      </div>
    </aside>

    <!-- Main Content -->
    <main class="main-content">
      <button
        v-if="isMobileViewport && !showMobileWorkspaceNav"
        class="workspace-mobile-menu-btn"
        :style="{ left: `${floatingMenuPos.x}px`, top: `${floatingMenuPos.y}px` }"
        @click="!isDraggingMenu && (showMobileWorkspaceNav = true)"
        @pointerdown.prevent="startFloatingMenuDrag"
        title="打开全局导航"
      >☰</button>
      <div class="content-container">
        <RouterView />
      </div>
    </main>
  </div>
</template>

<style scoped>
.workspace-layout {
  display: flex;
  min-height: 100vh;
  height: 100%;
  width: 100%;
  background-color: var(--bg-background);
  color: var(--text-primary);
}

/* Sidebar Styling */
.workspace-mobile-backdrop {
  position: fixed;
  inset: 0;
  background: rgba(15, 23, 42, 0.28);
  backdrop-filter: blur(2px);
  z-index: 29;
}

.sidebar {
  width: var(--sidebar-width);
  height: 100%;
  display: flex;
  flex-direction: column;
  background-color: var(--sidebar-bg);
  border-right: 1px solid var(--sidebar-border);
  transition: all 0.3s ease;
  z-index: 10;
  box-shadow: 0 0 0 1px rgba(255,255,255,0.3), 0 10px 30px rgba(15, 23, 42, 0.04);
}

.sidebar-header {
  padding: 1rem 1rem 0.75rem;
  position: relative;
}

.sidebar-header-row {
  display: flex;
  align-items: center;
  gap: 0.55rem;
}

.sidebar-header-row-end {
  justify-content: flex-end;
}

.mobile-close-btn {
  display: none;
}

/* Project Name */
.project-name-wrapper {
  padding: 0.5rem 1rem 1rem;
}

.project-name-display {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  padding: 0.875rem;
  background: linear-gradient(135deg, rgba(99, 102, 241, 0.08), rgba(129, 140, 248, 0.05));
  border-radius: 16px;
  border: 1px solid rgba(99, 102, 241, 0.12);
}

.project-name-display svg {
  color: var(--primary);
  flex-shrink: 0;
}

.project-title {
  font-weight: 600;
  font-size: 0.875rem;
  color: var(--text-primary);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

/* Navigation */
.sidebar-nav {
  flex: 1;
  padding: 0.5rem 1rem;
  display: flex;
  flex-direction: column;
  gap: 0.375rem;
  overflow-y: auto;
}

.nav-item {
  position: relative;
  display: flex;
  align-items: center;
  gap: 0.75rem;
  padding: 0.85rem 1rem;
  border-radius: 14px;
  color: var(--text-secondary);
  text-decoration: none;
  font-weight: 500;
  transition: all 0.2s;
}

.nav-item:hover {
  background-color: var(--bg-hover);
  color: var(--text-primary);
}

.nav-item.active {
  background-color: var(--bg-hover);
  color: var(--primary);
  font-weight: 600;
}

.nav-icon {
  font-size: 1.25rem;
  display: flex;
  align-items: center;
  justify-content: center;
  width: 1.5rem;
  flex-shrink: 0;
}

.active-indicator {
  position: absolute;
  left: 0;
  top: 50%;
  transform: translateY(-50%);
  width: 3px;
  height: 1.5rem;
  background-color: var(--primary);
  border-radius: 0 4px 4px 0;
}

/* Footer */
.sidebar-footer {
  padding: 1.25rem 1.5rem;
  border-top: 1px solid var(--border);
  background-color: var(--bg-secondary);
}

.project-info {
  display: flex;
  flex-direction: column;
  gap: 0.25rem;
}

.project-genre {
  font-size: 0.875rem;
  font-weight: 600;
  color: var(--text-primary);
}

.project-stats {
  font-size: 0.75rem;
  color: var(--text-muted);
  display: flex;
  gap: 0.5rem;
  flex-wrap: wrap;
}

.project-empty {
  font-size: 0.875rem;
  color: var(--text-muted);
  font-style: italic;
}

/* Main Content */
.main-content {
  flex: 1;
  background-color: var(--bg-background);
  overflow: hidden;
  position: relative;
  min-width: 0;
}

.content-container {
  width: 100%;
  height: 100%;
}

@media (max-width: 900px) {
  .workspace-layout {
    flex-direction: column;
  }

  .sidebar {
    width: 100%;
    height: auto;
    border-right: none;
    border-bottom: 1px solid var(--sidebar-border);
    box-shadow: none;
  }

  .sidebar-header {
    padding: 0.875rem 0.875rem 0.5rem;
  }

  .project-name-wrapper {
    padding: 0.25rem 0.875rem 0.75rem;
  }

  .sidebar-nav {
    display: grid;
    grid-template-columns: repeat(4, minmax(0, 1fr));
    overflow: visible;
    padding: 0 0.875rem 0.875rem;
    gap: 0.5rem;
  }

  .nav-item {
    min-width: 0;
    width: 100%;
    padding: 0.7rem 0.55rem;
    gap: 0.32rem;
    border: 1px solid var(--border);
    background: var(--bg-card);
    flex-direction: column;
    justify-content: center;
    text-align: center;
  }

  .nav-label {
    white-space: nowrap;
    font-size: 0.76rem;
    line-height: 1.1;
    overflow: hidden;
    text-overflow: ellipsis;
    max-width: 100%;
  }

  .active-indicator {
    left: 50%;
    top: auto;
    bottom: 0;
    width: 46%;
    height: 3px;
    transform: translateX(-50%);
    border-radius: 999px 999px 0 0;
  }

  .sidebar-footer {
    display: none;
  }

  .main-content {
    overflow: auto;
  }
}

@media (max-width: 768px) {
  .sidebar.mobile-overlay {
    position: fixed;
    top: 0;
    left: 0;
    width: min(86vw, 320px);
    max-width: 320px;
    height: 100dvh;
    z-index: 30;
    border-right: 1px solid var(--sidebar-border);
    border-bottom: none;
    transform: translateX(-100%);
    transition: transform 0.24s ease;
    box-shadow: 10px 0 32px rgba(15, 23, 42, 0.18);
    background: rgba(255,255,255,0.98);
    backdrop-filter: blur(12px);
  }

  .sidebar.mobile-overlay.mobile-open {
    transform: translateX(0);
  }

  .mobile-close-btn {
    position: static;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    width: 34px;
    height: 34px;
    border: 1px solid var(--border);
    border-radius: 10px;
    background: white;
    color: var(--text-secondary);
    flex-shrink: 0;
  }

  .workspace-mobile-menu-btn {
    position: fixed;
    z-index: 31;
    width: 46px;
    height: 46px;
    border: 1px solid var(--border);
    background: rgba(255,255,255,0.94);
    backdrop-filter: blur(8px);
    border-radius: 999px;
    padding: 0;
    font-size: 1rem;
    color: var(--text-secondary);
    box-shadow: 0 8px 22px rgba(15, 23, 42, 0.16);
    display: inline-flex;
    align-items: center;
    justify-content: center;
    touch-action: none;
    user-select: none;
  }

  .sidebar.mobile-overlay .sidebar-nav {
    display: flex;
    flex-direction: column;
    grid-template-columns: none;
    padding: 0 0.875rem 0.875rem;
    gap: 0.45rem;
    overflow-y: auto;
  }

  .sidebar.mobile-overlay .nav-item {
    width: 100%;
    min-width: 0;
    flex-direction: row;
    justify-content: flex-start;
    text-align: left;
    padding: 0.78rem 0.9rem;
    gap: 0.7rem;
  }

  .sidebar.mobile-overlay .nav-label {
    font-size: 0.82rem;
    line-height: 1.2;
    white-space: normal;
    overflow: visible;
    text-overflow: unset;
  }

  .sidebar.mobile-overlay .nav-icon {
    width: 1.2rem;
    flex-shrink: 0;
  }

  .sidebar.mobile-overlay .active-indicator {
    left: 0;
    top: 50%;
    bottom: auto;
    width: 3px;
    height: 1.4rem;
    transform: translateY(-50%);
    border-radius: 0 4px 4px 0;
  }
}

@media (max-width: 640px) {
  .sidebar {
    position: sticky;
    top: 0;
    z-index: 20;
    background: rgba(255,255,255,0.95);
    backdrop-filter: blur(12px);
  }

  .sidebar-header {
    padding: 0.5rem 0.55rem 0.3rem;
  }

  .project-name-wrapper {
    padding: 0 0.55rem 0.35rem;
  }

  .sidebar-nav {
    grid-template-columns: repeat(4, minmax(0, 1fr));
    padding: 0 0.55rem 0.45rem;
    gap: 0.32rem;
  }

  .back-btn {
    padding: 0.5rem 0.62rem;
    font-size: 0.72rem;
    border-radius: 10px;
    flex: 1;
  }

  .project-name-display {
    padding: 0.54rem 0.6rem;
    border-radius: 10px;
  }

  .project-title {
    font-size: 0.76rem;
  }

  .nav-item {
    padding: 0.48rem 0.28rem;
    border-radius: 10px;
    gap: 0.22rem;
  }

  .nav-label {
    font-size: 0.68rem;
  }

  .nav-icon {
    width: 1rem;
  }

  .nav-icon :deep(svg) {
    width: 0.92rem;
    height: 0.92rem;
  }
}

@media (max-width: 480px) {
  .sidebar-header {
    padding: 0.45rem 0.5rem 0.28rem;
  }

  .project-name-wrapper {
    padding: 0 0.5rem 0.32rem;
  }

  .sidebar-nav {
    padding: 0 0.5rem 0.42rem;
    gap: 0.28rem;
  }

  .back-btn {
    padding: 0.46rem 0.58rem;
    font-size: 0.7rem;
  }

  .project-name-display {
    padding: 0.5rem 0.56rem;
  }

  .project-title {
    font-size: 0.74rem;
  }

  .nav-item {
    padding: 0.44rem 0.22rem;
    gap: 0.18rem;
  }

  .nav-label {
    font-size: 0.64rem;
  }

  .active-indicator {
    width: 52%;
  }
}
</style>
