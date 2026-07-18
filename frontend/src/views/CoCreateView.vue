<!-- Copyright (c) 2026 左岚. All rights reserved. -->
<!-- CoCreateView.vue - AI 共创金手指（独立页面，单栏分步） -->
<script setup>
import { computed, ref, onMounted, watch } from 'vue'
import { useRouter } from 'vue-router'
import { projectsApi, aiApi } from '../api'
import { useProjectStore } from '../stores/project'
import GoldenFingerChat from '../components/GoldenFingerChat.vue'
import { Lightbulb, Wand2 } from 'lucide-vue-next'
import { useToast } from '../composables/useToast'

const router = useRouter()
const projectStore = useProjectStore()
const toast = useToast()

const genres = ref([])
const genre = ref('玄幻')
const substyle = ref('')
const creating = ref(false)
// 用于在题材变更后重建对话组件（重置对话历史）
const chatKey = ref(0)

onMounted(loadGenres)

async function loadGenres() {
  try {
    const { data } = await aiApi.getGenres()
    genres.value = normalizeGenres(data.genres || [])
  } catch (e) {
    console.warn('加载题材列表失败，使用默认', e)
    genres.value = normalizeGenres([
      { id: '玄幻', name: '玄幻', default_substyle: '热血升级流', substyles: [{ id: '热血升级流', name: '热血升级流' }] },
      { id: '规则怪谈', name: '规则怪谈', default_substyle: '规则生存流', substyles: [{ id: '规则生存流', name: '规则生存流' }] },
      { id: '现代言情', name: '现代言情', default_substyle: '高甜拉扯', substyles: [{ id: '高甜拉扯', name: '高甜拉扯' }] }
    ])
  }
  const first = genres.value[0]
  genre.value = first?.id || '玄幻'
  substyle.value = pickSubstyleId(first)
}

function normalizeGenres(items = []) {
  return items.map(item => ({
    ...item,
    aliases: item.aliases || [],
    substyles: item.substyles || []
  }))
}

function findGenreOption(value) {
  if (!value) return null
  const raw = String(value).trim()
  return genres.value.find(g =>
    g.id === raw || g.name === raw || (g.aliases || []).includes(raw)
  ) || null
}

function pickSubstyleId(genreOption, preferred = '') {
  const options = genreOption?.substyles || []
  if (!options.length) return ''
  const raw = String(preferred || '').trim()
  const matched = options.find(s => s.id === raw || s.name === raw)
  return matched?.id || genreOption.default_substyle || options[0].id
}

const availableSubstyles = computed(() => findGenreOption(genre.value)?.substyles || [])

watch(genre, (newVal) => {
  const matched = findGenreOption(newVal)
  substyle.value = pickSubstyleId(matched, substyle.value)
  // 题材切换后重开对话，避免风格串味
  chatKey.value++
})

function goBack() {
  router.push('/')
}

// 聊完点「用这个创建」→ 建项目 → 存金手指 → 跳初始化
async function handleApply({ title, goldenFingerDesign }) {
  const name = (title || '').trim()
  if (!name) {
    toast.info('请先选择或填写一个书名')
    return
  }
  creating.value = true
  try {
    const payload = {
      name,
      path: `./data/${name}`,
      genre: genre.value,
      substyle: substyle.value
    }
    const { data } = await projectsApi.create(payload)
    const resolvedPath = data.project?.path || payload.path
    await projectStore.setCurrentProject(resolvedPath)
    if (goldenFingerDesign) {
      sessionStorage.setItem('pendingGoldenFinger', goldenFingerDesign)
    } else {
      sessionStorage.removeItem('pendingGoldenFinger')
    }
    router.push('/workspace/project')
  } catch (e) {
    toast.error('创建项目失败：' + (e.response?.data?.detail || e.message))
  } finally {
    creating.value = false
  }
}
</script>

<template>
  <div class="cocreate-page">
    <!-- Top bar with gradient -->
    <header class="cc-top-bar">
      <div class="cc-top-content">
        <button class="cc-back-btn" @click="goBack" title="返回首页">
          <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor" class="size-5">
            <path stroke-linecap="round" stroke-linejoin="round" d="M15.75 19.5 8.25 12l7.5-7.5" />
          </svg>
          <span>返回</span>
        </button>

        <div class="cc-title">
          <div class="cc-title-icon">
            <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor" class="size-6">
              <path stroke-linecap="round" stroke-linejoin="round" d="M9.813 15.904 9 18.75l-.813-2.846a4.5 4.5 0 0 0-3.09-3.09L2.25 12l2.846-.813a4.5 4.5 0 0 0 3.09-3.09L9 5.25l.813 2.846a4.5 4.5 0 0 0 3.09 3.09L15.75 12l-2.846.813a4.5 4.5 0 0 0-3.09 3.09Z" />
            </svg>
          </div>
          <div class="cc-title-text">
            <h1>AI 共创金手指</h1>
            <p class="cc-subtitle">与 AI 对话，打磨你的核心设定</p>
          </div>
        </div>

        <!-- 题材/子风格选择 -->
        <div class="cc-genre-picker">
          <div class="picker-group">
            <label class="picker-label">题材</label>
            <select v-model="genre" class="cc-select">
              <option v-for="g in genres" :key="g.id" :value="g.id">{{ g.name }}</option>
            </select>
          </div>
          <div class="picker-group" v-if="availableSubstyles.length">
            <label class="picker-label">子风格</label>
            <select v-model="substyle" class="cc-select">
              <option v-for="s in availableSubstyles" :key="s.id" :value="s.id">{{ s.name }}</option>
            </select>
          </div>
        </div>
      </div>
    </header>

    <!-- 主体区域 -->
    <main class="cc-body">
      <div class="cc-container">
        <!-- 左侧提示卡片 -->
        <aside class="cc-hints">
          <div class="hint-card">
            <div class="hint-icon"><Lightbulb :size="20" :stroke-width="1.5" /></div>
            <h3 class="hint-title">设计建议</h3>
            <ul class="hint-list">
              <li>描述金手指的核心能力</li>
              <li>说明使用的代价或限制</li>
              <li>解释成长和升级路径</li>
              <li>考虑与主线剧情的关联</li>
            </ul>
          </div>

          <div class="hint-card hint-card-accent">
            <div class="hint-icon"><Wand2 :size="20" :stroke-width="1.5" /></div>
            <h3 class="hint-title">共创流程</h3>
            <div class="flow-steps">
              <div class="flow-step">
                <div class="flow-number">1</div>
                <span>自由对话，讲清想法</span>
              </div>
              <div class="flow-step">
                <div class="flow-number">2</div>
                <span>AI 生成完整设定</span>
              </div>
              <div class="flow-step">
                <div class="flow-number">3</div>
                <span>选择书名，创建项目</span>
              </div>
            </div>
          </div>
        </aside>

        <!-- 右侧对话区 -->
        <div class="cc-chat-area">
          <GoldenFingerChat
            :key="chatKey"
            :genre="genre"
            :substyle="substyle"
            :creating="creating"
            :embedded="true"
            @apply="handleApply"
            @close="goBack"
          />
        </div>
      </div>
    </main>
  </div>
</template>

<style scoped>
.cocreate-page {
  height: 100%;
  width: 100%;
  display: flex;
  flex-direction: column;
  background: var(--bg);
  overflow: hidden;
}

/* Top Bar */
.cc-top-bar {
  background: var(--card);
  border-bottom: 1px solid var(--border);
  flex-shrink: 0;
  position: relative;
}

.cc-top-content {
  max-width: 1400px;
  margin: 0 auto;
  padding: 1rem 2rem;
  display: flex;
  align-items: center;
  gap: 2rem;
}

.cc-back-btn {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  background: var(--card);
  border: 1px solid var(--border);
  color: var(--ink-secondary);
  padding: 0.5rem 0.875rem;
  border-radius: var(--radius-md);
  cursor: pointer;
  font-size: 0.875rem;
  font-weight: 500;
  transition: background-color var(--dur-fast) var(--ease-standard), border-color var(--dur-fast) var(--ease-standard), color var(--dur-fast) var(--ease-standard);
  flex-shrink: 0;
}

.cc-back-btn:hover {
  background: var(--hover);
  color: var(--ink-primary);
  border-color: var(--border-strong);
}

.cc-back-btn svg {
  width: 1.125rem;
  height: 1.125rem;
}

/* Title Section */
.cc-title {
  display: flex;
  align-items: center;
  gap: 1rem;
  flex: 1;
}

.cc-title-icon {
  width: 2.75rem;
  height: 2.75rem;
  border-radius: var(--radius-md);
  background: var(--primary);
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--on-primary);
}

.cc-title-icon svg {
  width: 1.375rem;
  height: 1.375rem;
}

.cc-title-text h1 {
  font-size: 1.25rem;
  font-weight: 600;
  color: var(--ink-primary);
  margin: 0;
  line-height: 1.25;
  letter-spacing: -0.01em;
}

.cc-subtitle {
  font-size: 0.8125rem;
  color: var(--ink-muted);
  margin: 0.25rem 0 0 0;
  font-weight: 400;
}

/* Genre Picker */
.cc-genre-picker {
  display: flex;
  align-items: flex-end;
  gap: 1rem;
  flex-shrink: 0;
}

.picker-group {
  display: flex;
  flex-direction: column;
  gap: 0.375rem;
}

.picker-label {
  font-size: 0.75rem;
  font-weight: 500;
  color: var(--ink-muted);
}

.cc-select {
  padding: 0.55rem 0.875rem;
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  font-size: 0.875rem;
  font-weight: 500;
  color: var(--ink-primary);
  background: var(--card);
  cursor: pointer;
  transition: border-color var(--dur-fast) var(--ease-standard), box-shadow var(--dur-fast) var(--ease-standard);
  min-width: 120px;
}

.cc-select:hover {
  border-color: var(--border-strong);
}

.cc-select:focus {
  outline: none;
  border-color: var(--primary);
  box-shadow: 0 0 0 3px var(--primary-tint);
}

/* Main Body */
.cc-body {
  flex: 1;
  min-height: 0;
  display: flex;
  justify-content: center;
  padding: 1.25rem 2rem 2rem;
  overflow: hidden;
}

.cc-container {
  flex: 1;
  max-width: 1400px;
  display: grid;
  grid-template-columns: 280px 1fr;
  gap: 1rem;
  min-height: 0;
}

/* Hints Sidebar */
.cc-hints {
  display: flex;
  flex-direction: column;
  gap: 0.875rem;
  overflow-y: auto;
  padding-right: 0.25rem;
}

.hint-card {
  background: var(--card);
  border: 1px solid var(--border);
  border-radius: var(--radius-lg);
  padding: 1.25rem;
}

.hint-card-accent {
  background: var(--primary-tint);
  border-color: transparent;
}

.hint-icon {
  margin-bottom: 0.75rem;
  display: block;
  color: var(--primary-text);
}

.hint-card-accent .hint-icon {
  color: var(--primary-on-tint);
}

.hint-title {
  font-size: 0.9375rem;
  font-weight: 600;
  color: var(--ink-primary);
  margin: 0 0 0.875rem 0;
}

.hint-list {
  list-style: none;
  padding: 0;
  margin: 0;
  display: flex;
  flex-direction: column;
  gap: 0.625rem;
}

.hint-list li {
  padding-left: 1.25rem;
  position: relative;
  font-size: 0.8125rem;
  color: var(--ink-secondary);
  line-height: 1.55;
  font-weight: 400;
}

.hint-list li::before {
  content: '•';
  position: absolute;
  left: 0.375rem;
  color: var(--primary-text);
  font-weight: bold;
}

.hint-card-accent .hint-list li::before {
  color: var(--primary-on-tint);
}

/* Flow Steps */
.flow-steps {
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
}

.flow-step {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  font-size: 0.8125rem;
  color: var(--ink-secondary);
  font-weight: 400;
}

.flow-number {
  width: 1.5rem;
  height: 1.5rem;
  border-radius: 50%;
  background: var(--primary);
  color: var(--on-primary);
  display: flex;
  align-items: center;
  justify-content: center;
  font-weight: 600;
  font-size: 0.6875rem;
  flex-shrink: 0;
  font-family: var(--font-mono);
}

/* Chat Area */
.cc-chat-area {
  min-height: 0;
  display: flex;
  flex-direction: column;
  background: var(--card);
  border: 1px solid var(--border);
  border-radius: var(--radius-lg);
  box-shadow: var(--shadow-sm);
  padding: 1.5rem;
  overflow: hidden;
}

/* Responsive */
@media (max-width: 1024px) {
  .cc-container {
    grid-template-columns: 1fr;
  }

  .cc-hints {
    display: none;
  }
}

@media (max-width: 768px) {
  .cc-top-content {
    flex-direction: column;
    align-items: stretch;
    gap: 1rem;
  }

  .cc-title {
    flex-direction: column;
    align-items: flex-start;
    gap: 0.75rem;
  }

  .cc-genre-picker {
    flex-direction: column;
    align-items: stretch;
  }

  .cc-body {
    padding: 1rem;
  }

  .cc-chat-area {
    padding: 1.25rem;
  }
}
</style>
