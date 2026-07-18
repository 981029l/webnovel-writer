<!-- Copyright (c) 2026 左岚. All rights reserved. -->
<!-- WorkspaceLayout.vue - 工作台布局(顶部导航 + 白纸内容区) -->
<script setup>
import { RouterLink, RouterView, useRoute, useRouter } from 'vue-router'
import { useProjectStore } from '../stores/project'
import { onMounted, onUnmounted, ref, computed } from 'vue'
import { useTheme } from '../composables/useTheme'
import {
  Sun, Moon, ChevronLeft, ChevronDown, NotebookPen, Settings,
  LayoutDashboard, ListTree, PenLine, Users, Boxes, Share2, Search,
  FolderCog, SlidersHorizontal, UploadCloud
} from 'lucide-vue-next'

const route = useRoute()
const router = useRouter()
const projectStore = useProjectStore()
const { theme, toggle: toggleTheme } = useTheme()

const mainNav = [
  { path: '/workspace/dashboard', icon: LayoutDashboard, label: '仪表盘' },
  { path: '/workspace/outline', icon: ListTree, label: '大纲编辑' },
  { path: '/workspace/write', icon: PenLine, label: '章节创作' },
  { path: '/workspace/characters', icon: Users, label: '角色管理' },
  { path: '/workspace/entities', icon: Boxes, label: '设定集' },
  { path: '/workspace/relations', icon: Share2, label: '关系图谱' },
  { path: '/workspace/rag', icon: Search, label: 'RAG 检索' }
]

const settingsNav = [
  { path: '/workspace/project', icon: FolderCog, label: '项目管理' },
  { path: '/workspace/prompts', icon: SlidersHorizontal, label: '提示词配置' },
  { path: '/workspace/fanqie', icon: UploadCloud, label: '番茄上传' }
]

// 设置下拉
const showSettingsMenu = ref(false)
const settingsRef = ref(null)

const settingsActive = computed(() => settingsNav.some(item => route.path.startsWith(item.path)))

function isActiveRoute(itemPath) {
  if (itemPath === '/workspace/dashboard') {
    return route.path === '/workspace/dashboard'
  }
  return route.path.startsWith(itemPath)
}

function goBackToProjects() {
  projectStore.clearProject()
  router.push('/')
}

function goSetting(path) {
  showSettingsMenu.value = false
  router.push(path)
}

function onDocMousedown(e) {
  if (showSettingsMenu.value && settingsRef.value && !settingsRef.value.contains(e.target)) {
    showSettingsMenu.value = false
  }
}

function onKeydown(e) {
  if (e.key === 'Escape') showSettingsMenu.value = false
}

onMounted(() => {
  if (projectStore.projectRoot && !projectStore.title) {
    projectStore.fetchStatus()
  }
  document.addEventListener('mousedown', onDocMousedown)
  window.addEventListener('keydown', onKeydown)
})

onUnmounted(() => {
  document.removeEventListener('mousedown', onDocMousedown)
  window.removeEventListener('keydown', onKeydown)
})
</script>

<template>
  <div class="workspace-layout">
    <!-- 顶部导航栏 -->
    <header class="topbar">
      <div class="topbar-left">
        <button class="tb-back" @click="goBackToProjects" title="返回项目列表" aria-label="返回项目列表">
          <ChevronLeft :size="16" :stroke-width="1.75" />
        </button>
        <span class="tb-brand">
          <NotebookPen :size="14" :stroke-width="2" />
        </span>
        <span class="tb-project" :title="projectStore.title || '未命名项目'">{{ projectStore.title || '未命名项目' }}</span>
      </div>

      <nav class="tb-nav" aria-label="工作区导航">
        <RouterLink
          v-for="item in mainNav"
          :key="item.path"
          :to="item.path"
          class="tb-item"
          :class="{ active: isActiveRoute(item.path) }"
        >
          <component :is="item.icon" :size="15" :stroke-width="1.75" />
          <span class="tb-item-label">{{ item.label }}</span>
        </RouterLink>
      </nav>

      <div class="topbar-right">
        <div class="tb-settings" ref="settingsRef">
          <button
            class="tb-item tb-settings-btn"
            :class="{ active: settingsActive || showSettingsMenu }"
            @click="showSettingsMenu = !showSettingsMenu"
            aria-haspopup="menu"
            :aria-expanded="showSettingsMenu"
          >
            <Settings :size="15" :stroke-width="1.75" />
            <span class="tb-item-label">设置</span>
            <ChevronDown :size="13" :stroke-width="1.75" class="tb-chev" :class="{ open: showSettingsMenu }" />
          </button>
          <Transition name="menu-pop">
            <div v-if="showSettingsMenu" class="tb-menu" role="menu">
              <button
                v-for="item in settingsNav"
                :key="item.path"
                class="tb-menu-item"
                :class="{ active: isActiveRoute(item.path) }"
                role="menuitem"
                @click="goSetting(item.path)"
              >
                <component :is="item.icon" :size="15" :stroke-width="1.75" />
                {{ item.label }}
              </button>
            </div>
          </Transition>
        </div>

        <button
          class="tb-icon-btn"
          @click="toggleTheme"
          :title="theme === 'dark' ? '切换到日间模式' : '切换到夜间模式'"
          :aria-label="theme === 'dark' ? '切换到日间模式' : '切换到夜间模式'"
        >
          <Sun v-if="theme === 'dark'" :size="16" :stroke-width="1.75" />
          <Moon v-else :size="16" :stroke-width="1.75" />
        </button>
      </div>
    </header>

    <!-- 内容区:灰画布上的白纸 -->
    <main class="main-content">
      <div class="content-sheet">
        <RouterView />
      </div>
    </main>
  </div>
</template>

<style scoped>
.workspace-layout {
  display: flex;
  flex-direction: column;
  height: 100%;
  width: 100%;
  background-color: var(--bg);
  color: var(--ink-primary);
}

/* ─── 顶栏 ─── */
.topbar {
  height: 52px;
  flex-shrink: 0;
  display: flex;
  align-items: center;
  gap: 0.5rem;
  padding: 0 0.875rem;
  background: var(--card);
  border-bottom: 1px solid var(--border);
  z-index: var(--z-sticky);
}

.topbar-left {
  display: flex;
  align-items: center;
  gap: 0.55rem;
  flex-shrink: 0;
  min-width: 0;
}

.tb-back {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 28px;
  height: 28px;
  flex-shrink: 0;
  background: transparent;
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  color: var(--ink-muted);
  cursor: pointer;
  transition: color var(--dur-fast) var(--ease-standard), border-color var(--dur-fast) var(--ease-standard), background-color var(--dur-fast) var(--ease-standard);
}

.tb-back:hover {
  color: var(--ink-primary);
  border-color: var(--border-strong);
  background: var(--hover);
}

.tb-brand {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 26px;
  height: 26px;
  flex-shrink: 0;
  background: var(--primary);
  color: var(--on-primary);
  border-radius: var(--radius-md);
}

.tb-project {
  font-size: 0.875rem;
  font-weight: 600;
  color: var(--ink-primary);
  max-width: 180px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

/* ─── 主导航 ─── */
.tb-nav {
  display: flex;
  align-items: center;
  gap: 2px;
  flex: 1;
  min-width: 0;
  margin-left: 0.5rem;
  padding-left: 0.75rem;
  border-left: 1px solid var(--border);
  overflow-x: auto;
  scrollbar-width: none;
}
.tb-nav::-webkit-scrollbar { display: none; }

.tb-item {
  display: inline-flex;
  align-items: center;
  gap: 0.4rem;
  padding: 0.375rem 0.65rem;
  border-radius: var(--radius-md);
  color: var(--ink-secondary);
  text-decoration: none;
  font-size: 0.8125rem;
  font-weight: 500;
  white-space: nowrap;
  border: none;
  background: transparent;
  cursor: pointer;
  transition: color var(--dur-fast) var(--ease-standard), background-color var(--dur-fast) var(--ease-standard);
  flex-shrink: 0;
}

.tb-item:hover {
  background: var(--hover);
  color: var(--ink-primary);
}

.tb-item.active {
  background: var(--primary-tint);
  color: var(--primary-on-tint);
}

/* ─── 右侧:设置下拉 + 主题 ─── */
.topbar-right {
  display: flex;
  align-items: center;
  gap: 0.375rem;
  flex-shrink: 0;
}

.tb-settings { position: relative; }

.tb-settings-btn {
  font-family: var(--font-ui);
}

.tb-chev {
  transition: transform var(--dur-fast) var(--ease-standard);
}
.tb-chev.open { transform: rotate(180deg); }

.tb-menu {
  position: absolute;
  right: 0;
  top: calc(100% + 8px);
  min-width: 156px;
  background: var(--card);
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  box-shadow: var(--shadow-md);
  padding: 4px;
  display: flex;
  flex-direction: column;
  z-index: var(--z-dropdown);
}

.tb-menu-item {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  width: 100%;
  text-align: left;
  padding: 0.5rem 0.625rem;
  border: none;
  background: transparent;
  border-radius: var(--radius-sm);
  font-size: 0.8125rem;
  font-weight: 500;
  font-family: var(--font-ui);
  color: var(--ink-secondary);
  cursor: pointer;
  transition: background-color var(--dur-fast) var(--ease-standard), color var(--dur-fast) var(--ease-standard);
  white-space: nowrap;
}

.tb-menu-item:hover {
  background: var(--hover);
  color: var(--ink-primary);
}

.tb-menu-item.active {
  background: var(--primary-tint);
  color: var(--primary-on-tint);
}

.menu-pop-enter-active {
  transition: opacity var(--dur-fast) var(--ease-emerge), transform var(--dur-fast) var(--ease-emerge);
}
.menu-pop-leave-active {
  transition: opacity 0.1s ease-in;
}
.menu-pop-enter-from {
  opacity: 0;
  transform: translateY(-4px);
}
.menu-pop-leave-to {
  opacity: 0;
}

.tb-icon-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 30px;
  height: 30px;
  background: transparent;
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  color: var(--ink-secondary);
  cursor: pointer;
  transition: color var(--dur-fast) var(--ease-standard), border-color var(--dur-fast) var(--ease-standard), background-color var(--dur-fast) var(--ease-standard);
}

.tb-icon-btn:hover {
  color: var(--ink-primary);
  border-color: var(--border-strong);
  background: var(--hover);
}

/* ─── 内容区:白纸 Content Sheet ─── */
.main-content {
  flex: 1;
  min-height: 0;
  padding: var(--sheet-gap);
  overflow: hidden;
  position: relative;
}

.content-sheet {
  width: 100%;
  height: 100%;
  background: var(--card);
  border: 1px solid var(--border);
  border-radius: var(--radius-lg);
  box-shadow: var(--shadow-sm);
  overflow: hidden;
}

/* ─── 响应式 ─── */
@media (max-width: 960px) {
  .tb-project { display: none; }
  .topbar { padding: 0 0.625rem; }
  .tb-nav { margin-left: 0.25rem; padding-left: 0.5rem; }
}

@media (max-width: 680px) {
  .tb-item-label { display: none; }
  .tb-item { padding: 0.375rem 0.5rem; }
}
</style>
