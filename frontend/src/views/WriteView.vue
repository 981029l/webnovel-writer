<!-- Copyright (c) 2026 左岚. All rights reserved. -->
<!-- WriteView.vue - 沉浸式创作页面 -->
<script setup>
import { ref, onMounted, onUnmounted, watch, computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { chaptersApi, aiApi, outlinesApi } from '../api'
import { useProjectStore } from '../stores/project'
import { useAiTaskStore } from '../stores/aiTask'
import ConfirmDialog from '../components/ConfirmDialog.vue'
import ExtractionPreviewDialog from '../components/ExtractionPreviewDialog.vue'

const route = useRoute()
const router = useRouter()
const projectStore = useProjectStore()

const chapters = ref([])
const volumeTree = ref([])  // 卷大纲树
const expandedVolumes = ref(new Set())  // 展开的卷
const currentChapter = ref(null)
const editContent = ref('')
const editTitle = ref('')
const loading = ref(false)
const saving = ref(false)
const saveType = ref(null)
const aiWriting = ref(false)
const aiPolishing = ref(false)
const aiReviewing = ref(false)
const copying = ref(false)
const message = ref('')

// 弹窗提示状态
const showPopup = ref(false)
const popupMessage = ref('')
const popupType = ref('info') // info, success, warning

// Dialog State
const showPolishDialog = ref(false)
const polishDialogMessage = ref('')
const showDeleteDialog = ref(false)

// AI Ending Mode State
const showEndingDialog = ref(false)
const endingPlan = ref(null)
const generatingEnding = ref(false)
const remainingChapters = ref(5)

// Extraction Preview State
const extracting = ref(false)
const showExtractionPreview = ref(false)
const extractionResult = ref(null)
const applyingExtraction = ref(false)

async function copyContent() {
  if (!editContent.value) return
  copying.value = true
  try {
    await navigator.clipboard.writeText(editContent.value)
    message.value = '✓ 已复制到剪贴板'
    setTimeout(() => { if (message.value === '✓ 已复制到剪贴板') message.value = '' }, 2000)
  } catch (err) {
    message.value = '✗ 复制失败'
  } finally {
    copying.value = false
  }
}
const reviewResult = ref(null)
const showSidebar = ref(true)

onMounted(async () => {
  await loadChapters()
  await loadOutlineTree()
  if (route.params.chapter) {
    await loadChapter(parseInt(route.params.chapter))
  } else {
    // 自动跳转到第一个未写的章节
    autoNavigateToFirstUnwritten()
  }
  window.addEventListener('keydown', handleKeydown)
})

// 自动跳转到第一个未完成章节
function autoNavigateToFirstUnwritten() {
  // 从大纲中找第一个未写的章节
  for (const vol of volumeTree.value) {
    for (const ch of vol.children || []) {
      const existing = chapters.value.find(c => c.id === ch.chapter)
      if (!existing || !existing.word_count || existing.word_count === 0) {
        // 自动展开该卷并跳转
        expandedVolumes.value.add(vol.volume)
        expandedVolumes.value = new Set(expandedVolumes.value)
        router.push(`/workspace/write/${ch.chapter}`)
        return
      }
    }
  }
  // 如果所有章节都写完了，跳转到最后一章
  if (chapters.value.length > 0) {
    const lastChapter = chapters.value[chapters.value.length - 1]
    router.push(`/workspace/write/${lastChapter.id}`)
  }
}
onUnmounted(() => {
  window.removeEventListener('keydown', handleKeydown)
})

function handleKeydown(e) {
  if ((e.ctrlKey || e.metaKey) && e.key === 's') {
    e.preventDefault()
    saveOnly()
  }
}

watch(() => route.params.chapter, async (newChapter) => {
  if (newChapter) {
    await loadChapter(parseInt(newChapter))
  }
})

watch(() => projectStore.projectRoot, async (newRoot, oldRoot) => {
  if (!newRoot || newRoot === oldRoot) return
  chapters.value = []
  volumeTree.value = []
  expandedVolumes.value = new Set()
  currentChapter.value = null
  editContent.value = ''
  editTitle.value = ''
  await loadChapters()
  await loadOutlineTree()
  if (route.params.chapter) {
    await loadChapter(parseInt(route.params.chapter))
  } else {
    autoNavigateToFirstUnwritten()
  }
})

async function loadChapters() {
  try {
    const { data } = await chaptersApi.getAll()
    chapters.value = data.chapters
  } catch (e) {
    console.error('Failed to load chapters:', e)
  }
}

async function loadOutlineTree() {
  try {
    const { data } = await outlinesApi.getTree()
    volumeTree.value = data.tree.filter(item => item.type === 'volume')
    // 自动展开当前章节所在卷
    if (currentChapter.value) {
      const chapterId = currentChapter.value.id
      for (const vol of volumeTree.value) {
        if (vol.children?.some(ch => ch.chapter === chapterId)) {
          expandedVolumes.value.add(vol.volume)
        }
      }
    }
  } catch (e) {
    console.error('Failed to load outline tree:', e)
  }
}

function toggleVolume(volume) {
  if (expandedVolumes.value.has(volume)) {
    expandedVolumes.value.delete(volume)
  } else {
    expandedVolumes.value.add(volume)
  }
  expandedVolumes.value = new Set(expandedVolumes.value) // 触发响应式
}

async function loadChapter(id) {
  const setDraftChapter = () => {
    const outlineTitle = findChapterTitleFromOutline(id)
    currentChapter.value = { id, title: outlineTitle || `第${id}章`, content: '', word_count: 0 }
    editContent.value = ''
    editTitle.value = outlineTitle || `第${id}章`
    message.value = '📝 新章节，开始创作吧！'
    setTimeout(() => { if (message.value.includes('新章节')) message.value = '' }, 3000)
  }

  loading.value = true
  reviewResult.value = null
  const existsInList = chapters.value.some(c => c.id === id)

  if (!existsInList) {
    setDraftChapter()
    loading.value = false
    return
  }

  try {
    const { data } = await chaptersApi.get(id)
    currentChapter.value = data
    editContent.value = data.content
    editTitle.value = data.title
    
    // 如果数据库中的标题是默认格式（如"第109章"），尝试从大纲获取更有意义的标题
    if (/^第\d+章$/.test(data.title)) {
      const outlineTitle = findChapterTitleFromOutline(id)
      if (outlineTitle) {
        editTitle.value = outlineTitle
      }
    }
  } catch (e) {
    // 章节不存在时，尝试从大纲创建
    if (e.response?.status === 404) {
      setDraftChapter()
    } else {
      message.value = '✗ 加载失败'
      currentChapter.value = null
    }
  } finally {
    loading.value = false
  }
}

// 从大纲中查找章节标题
function findChapterTitleFromOutline(chapterId) {
  for (const vol of volumeTree.value) {
    const ch = vol.children?.find(c => c.chapter === chapterId)
    if (ch) {
      // 去掉"第N章"前缀和《》符号，只保留标题
      return ch.title?.replace(/^第\d+章\s*/, '').replace(/[《》]/g, '') || null
    }
  }
  return null
}

function selectChapter(chapter) {
  router.push(`/workspace/write/${chapter.id}`)
}

async function saveOnly() {
  if (!currentChapter.value) return
  saving.value = true
  saveType.value = 'only'
  message.value = ''
  try {
    const reviewRaw = reviewText.value || ''
    const { data } = await chaptersApi.update(currentChapter.value.id, {
      title: editTitle.value,
      content: editContent.value,
      trigger_extraction: false,
      review_raw: reviewRaw
    })
    message.value = '✓ 已保存'
    setTimeout(() => { if (message.value === '✓ 已保存') message.value = '' }, 2000)

    // 刷新章节列表状态
    await loadChapters()
  } catch (e) {
    message.value = '✗ 保存失败'
    console.error(e)
  } finally {
    saving.value = false
    saveType.value = null
  }
}

// 提取世界观预览
async function handleExtractPreview() {
  if (!currentChapter.value || extracting.value) return

  extracting.value = true
  popupMessage.value = 'AI 正在分析设定数据...'
  popupType.value = 'info'
  showPopup.value = true

  try {
    const { data } = await chaptersApi.extractPreview(currentChapter.value.id, editContent.value)
    if (data.success && data.task_id) {
      // 轮询等待提取完成
      const startTime = Date.now()
      const TIMEOUT_MS = 300 * 1000
      let interval = 1000

      const pollTask = async () => {
        if (Date.now() - startTime > TIMEOUT_MS) {
          popupMessage.value = '提取超时，请重试'
          popupType.value = 'warning'
          setTimeout(() => { showPopup.value = false }, 3000)
          extracting.value = false
          return
        }

        try {
          const { data: status } = await chaptersApi.getTaskStatus(data.task_id)

          if (status.status === 'completed') {
            chaptersApi.ackTask(data.task_id).catch(() => {})
            showPopup.value = false
            extracting.value = false
            if (status.result) {
              extractionResult.value = status.result
              showExtractionPreview.value = true
            } else {
              popupMessage.value = '本章未提取到新设定'
              popupType.value = 'info'
              showPopup.value = true
              setTimeout(() => { showPopup.value = false }, 2500)
            }
          } else if (status.status === 'error') {
            chaptersApi.ackTask(data.task_id).catch(() => {})
            popupMessage.value = '提取失败: ' + status.message
            popupType.value = 'warning'
            setTimeout(() => { showPopup.value = false }, 3000)
            extracting.value = false
          } else if (status.status === 'running') {
            popupMessage.value = status.message || 'AI 正在分析设定数据...'
            if (interval < 5000) interval += 500
            setTimeout(pollTask, interval)
          } else {
            showPopup.value = false
            extracting.value = false
          }
        } catch (e) {
          console.error('Poll extract preview failed:', e)
          setTimeout(pollTask, 5000)
        }
      }

      setTimeout(pollTask, 1000)
    }
  } catch (e) {
    popupMessage.value = '启动同步失败: ' + (e.response?.data?.detail || e.message)
    popupType.value = 'warning'
    setTimeout(() => { showPopup.value = false }, 3000)
    extracting.value = false
  }
}

async function handleExtractionConfirm(filtered) {
  if (!currentChapter.value) return
  applyingExtraction.value = true
  try {
    const { data } = await chaptersApi.extractApply(currentChapter.value.id, filtered, editContent.value)
    showExtractionPreview.value = false
    extractionResult.value = null
    popupMessage.value = `✓ 设定同步完成（新增 ${data.created_files || 0} 文件，更新 ${data.updated_entities || 0} 实体）`
    popupType.value = 'success'
    showPopup.value = true
    setTimeout(() => { showPopup.value = false }, 3000)
  } catch (e) {
    popupMessage.value = '写入失败: ' + (e.response?.data?.detail || e.message)
    popupType.value = 'warning'
    showPopup.value = true
    setTimeout(() => { showPopup.value = false }, 3000)
  } finally {
    applyingExtraction.value = false
  }
}

function handleExtractionCancel() {
  showExtractionPreview.value = false
  extractionResult.value = null
}


async function saveAndNext() {
  if (!currentChapter.value) return
  saving.value = true
  saveType.value = 'next'
  message.value = ''
  try {
    const reviewRaw = reviewText.value || ''
    await chaptersApi.update(currentChapter.value.id, {
      title: editTitle.value,
      content: editContent.value,
      trigger_extraction: false,
      review_raw: reviewRaw
    })
    
    // Auto-create next chapter logic
    const nextId = currentChapter.value.id + 1
    // strict check: if ANY chapter with nextId exists, do not create
    const nextChapterExists = chapters.value.some(c => c.id === nextId)
    
    if (!nextChapterExists) {
      let nextTitle = `第${nextId}章`
      try {
        const volume = Math.ceil(nextId / 50)
        const { data: volumeData } = await outlinesApi.getVolume(volume)
        if (volumeData.chapters) {
          const chapterInfo = volumeData.chapters.find(c => c.chapter === nextId)
          if (chapterInfo && chapterInfo.title) nextTitle = chapterInfo.title
        }
      } catch (e) {
         // silent error
      }
      
      await chaptersApi.update(nextId, { title: nextTitle, content: '', trigger_extraction: false })
      await loadChapters() // Reload to get the new chapter
    }
    
    router.push(`/workspace/write/${nextId}`)
  } catch (e) {
    message.value = '✗ 保存失败：' + e.message
  } finally {
    saving.value = false
    saveType.value = null
  }
}

function confirmDelete() {
  if (!currentChapter.value) return
  showDeleteDialog.value = true
}

async function handleDeleteConfirm() {
  showDeleteDialog.value = false
  if (!currentChapter.value) return
  try {
    await chaptersApi.delete(currentChapter.value.id)
    currentChapter.value = null
    editTitle.value = ''
    editContent.value = ''
    await loadChapters()
    if (chapters.value.length > 0) router.push(`/workspace/write/${chapters.value[0].id}`)
    else router.push('/workspace/write')
  } catch (e) {
    message.value = '✗ 删除失败：' + e.message
  }
}

function createNewChapter() {
  const nextId = chapters.value.length > 0 
    ? Math.max(...chapters.value.map(c => c.id)) + 1 
    : 1
  currentChapter.value = { id: nextId, title: '', content: '' }
  editTitle.value = ''
  editContent.value = ''
  reviewResult.value = null
}

async function aiWriteChapter() {
  if (!currentChapter.value) return
  const aiTaskStore = useAiTaskStore()
  aiTaskStore.startTask('AI 写作', `第 ${currentChapter.value.id} 章`)
  aiWriting.value = true
  editContent.value = '' // 清空旧内容，显示流式输出
  
  try {
    const response = await aiApi.writeChapterStream(currentChapter.value.id)
    if (!response.ok) {
      const raw = await response.text()
      let detail = raw
      try {
        const obj = JSON.parse(raw)
        detail = obj?.detail || obj?.message || raw
      } catch (_) {}
      throw new Error(`写作请求失败（${response.status}）：${detail}`)
    }
    const reader = response.body.getReader()
    const decoder = new TextDecoder()

    let fullContent = ''
    let buffer = ''
    while (true) {
      const { done, value } = await reader.read()
      if (done) break

      buffer += decoder.decode(value, { stream: true })
      const parts = buffer.split('\n\n')
      buffer = parts.pop()

      for (const part of parts) {
        const line = part.trim()
        if (line.startsWith('data: ')) {
          let data
          try {
            data = JSON.parse(line.substring(6))
          } catch (e) {
            console.error('Error parsing SSE:', e)
            continue
          }

          if (data.type === 'step') {
            aiTaskStore.updateStep({ step: data.name, name: data.name, status: data.status === 'processing' ? 'active' : 'completed' })
            message.value = data.name + '...'
          } else if (data.type === 'content') {
            if (data.replace && typeof data.full === 'string') {
              fullContent = data.full
            } else if (typeof data.full === 'string' && !data.chunk) {
              fullContent = data.full
            } else {
              fullContent += (data.chunk || '')
            }
            editContent.value = fullContent // 实时更新编辑器内容
          } else if (data.type === 'error') {
            if (data.level === 'warning') {
              message.value = `⚠️ ${data.message || '后台步骤告警'}`
              continue
            }
            throw new Error(data.message)
          } else if (data.type === 'review') {
            reviewResult.value = data.result
            message.value = '✓ AI 审查完成'
          } else if (data.type === 'consistency_guard') {
            const report = data.result || {}
            const fixes = Number(report.rename_applied || 0)
            const rewritten = report.ai_rewrite_applied ? 1 : 0
            if (fixes > 0 || rewritten > 0) {
              message.value = `一致性修正：术语替换 ${fixes} 处${rewritten ? '，并执行结构化修复' : ''}`
            }
          } else if (data.type === 'done') {
            // 后端可能在流式生成后执行一致性修正，最终正文以 done.content 为准
            if (typeof data.content === 'string' && data.content.trim()) {
              fullContent = data.content
              editContent.value = fullContent
            }
            const reviewRaw = (reviewResult.value && reviewResult.value.raw_review) ? reviewResult.value.raw_review : (reviewText.value || '')
            await chaptersApi.update(currentChapter.value.id, {
              title: editTitle.value,
              content: fullContent,
              trigger_extraction: false,
              review_raw: reviewRaw
            })
            aiTaskStore.completeTask(true, `第 ${currentChapter.value.id} 章创作完成并已保存`)
            message.value = `✓ 第 ${currentChapter.value.id} 章创作完成并已保存`
            await loadChapters()
          }
        }
      }
    }
  } catch (e) {
    aiTaskStore.failTask(e.message)
    message.value = '✗ AI 写作失败：' + e.message
  } finally {
    aiWriting.value = false
  }
}

async function aiReviewChapter() {
  if (!currentChapter.value) return
  aiReviewing.value = true
  try {
    const { data } = await aiApi.reviewChapter(currentChapter.value.id)
    if (data.success) {
      reviewResult.value = data
    }
  } catch (e) {
    console.error('Review error:', e)
    message.value = '✗ 审查失败：' + (e.response?.data?.detail || e.message)
  } finally {
    aiReviewing.value = false
  }
}

function openPolishConfirm() {
  if (!currentChapter.value) return
  
  const hints = reviewText.value || ''
  polishDialogMessage.value = hints 
    ? `确认要根据审查建议进行智能润色吗？\n此操作将覆盖当前章节内容，建议您先复制备份。`
    : `确认要进行通用智能润色吗？\n此操作将覆盖当前章节内容，建议您先复制备份。`
  
  showPolishDialog.value = true
}

async function handlePolishConfirm() {
  showPolishDialog.value = false
  aiPolishing.value = true

  const hints = reviewText.value || ''
  const originalContent = editContent.value // Hold original content

  // Clear editor to show typing effect
  editContent.value = ''
  message.value = 'AI 正在润色...'

  try {
    const response = await aiApi.polishChapterStream(
      currentChapter.value.id,
      originalContent,
      hints
    )

    const reader = response.body.getReader()
    const decoder = new TextDecoder()
    let fullContent = ''
    let buffer = ''

    while (true) {
      const { done, value } = await reader.read()
      if (done) break

      buffer += decoder.decode(value, { stream: true })
      const parts = buffer.split('\n\n')
      buffer = parts.pop()

      for (const part of parts) {
        const line = part.trim()
        if (!line.startsWith('data: ')) continue
        const data = JSON.parse(line.substring(6))
        if (data.type === 'error') {
          throw new Error(data.message)
        } else if (data.type === 'content') {
          if (typeof data.full === 'string' && !data.chunk) {
            fullContent = data.full
          } else {
            fullContent += (data.chunk || '')
          }
          editContent.value = fullContent
        } else if (data.type === 'step') {
          message.value = data.name
        } else if (data.type === 'done') {
          message.value = '✓ 润色完成，正在重新审查...'
          // Auto-save and re-review
          await saveOnly()
          await aiReviewChapter()
        }
      }
    }
  } catch (e) {
    message.value = '✗ 润色失败：' + (e.response?.data?.detail || e.message)
    // If failed, restore original content
    if (!editContent.value) {
        editContent.value = originalContent
    }
  } finally {
    aiPolishing.value = false
  }
}

async function openEndingDialog() {
  endingPlan.value = null
  remainingChapters.value = 5
  showEndingDialog.value = true
}

async function generateEnding() {
  generatingEnding.value = true
  try {
    const { data } = await aiApi.generateEndingPlan(remainingChapters.value)
    if (data.success) {
      endingPlan.value = data.plan
    } else {
      message.value = '✗ 生成失败: ' + data.error
    }
  } catch (e) {
    message.value = '✗ 生成失败: ' + (e.response?.data?.detail || e.message)
  } finally {
    generatingEnding.value = false
  }
}

async function applyEndingPlan() {
  if (!endingPlan.value) return
  message.value = '✓ 收尾规划已应用！'
  showEndingDialog.value = false
}

const wordCount = ref(0)
watch(editContent, (val) => wordCount.value = val ? val.length : 0)

// 自动清除消息提示
let messageTimer = null
watch(message, (val) => {
  if (messageTimer) clearTimeout(messageTimer)
  if (val && (val.startsWith('✓') || val.startsWith('✗'))) {
    messageTimer = setTimeout(() => { message.value = '' }, 3000)
  }
})

// 审查结果文本（可编辑）
const reviewText = computed({
  get: () => {
    if (!reviewResult.value) return ''
    if (reviewResult.value.raw_review) return reviewResult.value.raw_review
    // 兼容旧格式：拼接 summary + issues
    let text = reviewResult.value.summary || ''
    if (reviewResult.value.issues?.length) {
      text += '\n\n' + reviewResult.value.issues.map(i => typeof i === 'string' ? i : (i.problem || i.title || '')).join('\n')
    }
    return text || '审查完成'
  },
  set: (val) => { if (reviewResult.value) reviewResult.value.raw_review = val }
})
</script>

<template>
  <div class="write-layout">
    <!-- 状态消息 -->
    <Transition name="toast">
      <div v-if="message" class="status-toast" :class="{ error: message.startsWith('✗'), success: message.startsWith('✓') }">
        {{ message }}
      </div>
    </Transition>

    <!-- 弹窗提示 -->
    <Transition name="popup">
      <div v-if="showPopup" class="popup-notification" :class="popupType">
        <div class="popup-icon">
          <svg v-if="popupType === 'info'" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor">
            <path stroke-linecap="round" stroke-linejoin="round" d="M16.023 9.348h4.992v-.001M2.985 19.644v-4.992m0 0h4.992m-4.993 0 3.181 3.183a8.25 8.25 0 0 0 13.803-3.7M4.031 9.865a8.25 8.25 0 0 1 13.803-3.7l3.181 3.182m0-4.991v4.99" />
          </svg>
        </div>
        <div class="popup-content">
          <div class="popup-title">后台任务进行中</div>
          <div class="popup-message">{{ popupMessage }}</div>
        </div>
        <button class="popup-close" @click="showPopup = false">×</button>
      </div>
    </Transition>
    <!-- 左侧章节导航 -->
    <aside class="chapter-nav" :class="{ collapsed: !showSidebar }">
      <div class="nav-header">
        <h2 class="nav-title">
          <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor" class="size-5 mr-2"><path stroke-linecap="round" stroke-linejoin="round" d="M12 6.042A8.967 8.967 0 0 0 6 3.75c-1.052 0-2.062.18-3 .512v14.25A8.987 8.987 0 0 1 6 18c2.305 0 4.408.867 6 2.292m0-14.25a8.966 8.966 0 0 1 6-2.292c1.052 0 2.062.18 3 .512v14.25A8.987 8.987 0 0 0 18 18a8.967 8.967 0 0 0-6 2.292m0-14.25v14.25" /></svg>
          章节目录
        </h2>
        <button class="icon-btn" @click="createNewChapter" title="新建章节">
          <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor" class="size-5"><path stroke-linecap="round" stroke-linejoin="round" d="M12 4.5v15m7.5-7.5h-15" /></svg>
        </button>
      </div>
      
      <div class="chapter-list">
        <div v-if="loading && chapters.length === 0" class="loading-state">
           <span class="spinner-sm"></span> 加载中...
        </div>
        
        <!-- 按卷分组显示 -->
        <template v-else-if="volumeTree.length > 0">
          <div v-for="vol in volumeTree" :key="vol.id" class="volume-group">
            <div class="volume-header" @click="toggleVolume(vol.volume)">
              <svg :class="['volume-arrow', { expanded: expandedVolumes.has(vol.volume) }]" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="2" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" d="m8.25 4.5 7.5 7.5-7.5 7.5" /></svg>
              <span class="volume-title">{{ vol.title?.replace(/[《》]/g, '') }}</span>
              <span class="volume-count">{{ vol.children?.length || 0 }}章</span>
            </div>
            <div v-show="expandedVolumes.has(vol.volume)" class="volume-chapters">
              <div 
                v-for="ch in vol.children" 
                :key="ch.id"
                class="chapter-item"
                :class="{ active: currentChapter?.id === ch.chapter }"
                @click="selectChapter({ id: ch.chapter })"
              >
                <span class="chapter-num">{{ ch.chapter }}</span>
                <span class="chapter-name" :title="ch.title">
                  {{ ch.title?.replace(/^第\d+章\s*/, '').replace(/[《》]/g, '') || '无标题' }}
                </span>
              </div>
            </div>
          </div>
        </template>
        
        <!-- 无大纲时显示扁平列表 -->
        <template v-else>
          <div 
            v-for="chapter in chapters" 
            :key="chapter.id"
            class="chapter-item"
            :class="{ active: currentChapter?.id === chapter.id }"
            @click="selectChapter(chapter)"
          >
            <span class="chapter-num">{{ chapter.id }}</span>
            <span class="chapter-name">{{ chapter.title || '无标题' }}</span>
            <svg v-if="chapter.word_count > 0" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor" class="chapter-done-icon"><path stroke-linecap="round" stroke-linejoin="round" d="m4.5 12.75 6 6 9-13.5" /></svg>
          </div>
        </template>
      </div>
      
      <div class="nav-footer">
        <button class="toggle-btn" @click="showSidebar = !showSidebar">
          <svg v-if="showSidebar" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor" class="size-5"><path stroke-linecap="round" stroke-linejoin="round" d="M15.75 19.5 8.25 12l7.5-7.5" /></svg>
          <svg v-else xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor" class="size-5"><path stroke-linecap="round" stroke-linejoin="round" d="m8.25 4.5 7.5 7.5-7.5 7.5" /></svg>
        </button>
        
        <button v-if="showSidebar" class="toggle-btn ending-btn" @click="openEndingDialog" title="智能收尾模式">
          <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor" class="size-5"><path stroke-linecap="round" stroke-linejoin="round" d="M3 3v1.5M3 21v-6m0 0 2.77-.693a9 9 0 0 1 6.208.682l.108.054a9 9 0 0 0 6.086.71l3.114-.732a48.524 48.524 0 0 1-.005-10.499l-3.11.732a9 9 0 0 1-6.085-.711l-.108-.054a9 9 0 0 0-6.208-.682L3 4.5M3 15V4.5" /></svg>
        </button>
      </div>
    </aside>

    <!-- 主编辑区 -->
    <main class="editor-main">
      <!-- 侧边栏展开按钮 (当侧边栏收起时显示, 移到外层以保证在空状态下也由于) -->
      <button 
        v-if="!showSidebar" 
        class="expand-sidebar-btn" 
        @click="showSidebar = true"
        title="展开侧边栏"
      >
        <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor" class="size-5"><path stroke-linecap="round" stroke-linejoin="round" d="m8.25 4.5 7.5 7.5-7.5 7.5" /></svg>
      </button>

      <div v-if="currentChapter" class="editor-area">
      <div class="editor-container">

        <!-- 顶部工具栏 -->
        <header class="editor-toolbar">
          <!-- 第一行：章节标题 + 字数 -->
          <div class="toolbar-row">
            <div class="toolbar-left">
              <input
                v-model="editTitle"
                class="title-input"
                placeholder="输入章节标题..."
              />
            </div>
            <span class="word-count-badge">{{ wordCount.toLocaleString() }} 字</span>
          </div>
          <!-- 第二行：操作按钮分组 -->
          <div class="toolbar-row toolbar-actions">
            <div class="toolbar-group">
              <button class="btn img-btn-ghost" @click="confirmDelete" title="删除当前章节">
                <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor" class="size-5"><path stroke-linecap="round" stroke-linejoin="round" d="M14.74 9l-.346 9m-4.788 0L9.26 9m9.968-3.21c.342.052.682.107 1.022.166m-1.022-.165L18.16 19.673a2.25 2.25 0 01-2.244 2.077H8.084a2.25 2.25 0 01-2.244-2.077L4.772 5.79m14.456 0a48.108 48.108 0 00-3.478-.397m-12 .562c.34-.059.68-.114 1.022-.165m0 0a48.11 48.11 0 013.478-.397m7.5 0v-.916c0-1.18-.91-2.164-2.09-2.201a51.964 51.964 0 00-3.32 0c-1.18.037-2.09 1.022-2.09 2.201v.916m7.5 0a48.667 48.667 0 00-7.5 0" /></svg>
              </button>
            </div>
            <div class="toolbar-divider"></div>
            <div class="toolbar-group">
              <button class="btn btn-secondary btn-sm" @click="copyContent" :disabled="!editContent" title="复制内容">
                <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor" class="size-4 mr-1"><path stroke-linecap="round" stroke-linejoin="round" d="M15.75 17.25v3.375c0 .621-.504 1.125-1.125 1.125h-9.75a1.125 1.125 0 0 1-1.125-1.125V7.875c0-.621.504-1.125 1.125-1.125H6.75a9.06 9.06 0 0 1 1.5.124m7.5 10.376h3.375c.621 0 1.125-.504 1.125-1.125V11.25c0-4.46-3.243-8.161-7.5-8.876a9.06 9.06 0 0 0-1.5-.124H9.375c-.621 0-1.125.504-1.125 1.125v3.5m7.5 10.375H9.375a1.125 1.125 0 0 1-1.125-1.125v-9.25m12 6.625v-1.875a3.375 3.375 0 0 0-3.375-3.375h-1.5a1.125 1.125 0 0 1-1.125-1.125v-1.5a3.375 3.375 0 0 0-3.375-3.375H9.75" /></svg>
                {{ copying ? '复制中' : '复制' }}
              </button>
              <button class="btn btn-secondary btn-sm" @click="aiReviewChapter" :disabled="aiReviewing">
                <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor" class="size-4 mr-1"><path stroke-linecap="round" stroke-linejoin="round" d="M2.036 12.322a1.012 1.012 0 0 1 0-.639C3.423 7.51 7.36 4.5 12 4.5c4.638 0 8.573 3.007 9.963 7.178.07.207.07.431 0 .639C20.577 16.49 16.64 19.5 12 19.5c-4.638 0-8.573-3.007-9.963-7.178Z" /><path stroke-linecap="round" stroke-linejoin="round" d="M15 12a3 3 0 1 1-6 0 3 3 0 0 1 6 0Z" /></svg>
                {{ aiReviewing ? '审查中' : '审查' }}
              </button>
              <button class="btn btn-secondary btn-sm" @click="openPolishConfirm" :disabled="aiPolishing || !reviewResult" title="先审查，再润色">
                <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor" class="size-4 mr-1"><path stroke-linecap="round" stroke-linejoin="round" d="M9.813 15.904 9 18.75l-.813-2.846a4.5 4.5 0 0 0-3.09-3.09L2.25 12l2.846-.813a4.5 4.5 0 0 0 3.09-3.09L9 5.25l.813 2.846a4.5 4.5 0 0 0 3.09 3.09L15.75 12l-2.846.813a4.5 4.5 0 0 0-3.09 3.09ZM18.259 8.715 18 9.75l-.259-1.035a3.375 3.375 0 0 0-2.455-2.456L14.25 6l1.036-.259a3.375 3.375 0 0 0 2.455-2.456L18 2.25l.259 1.035a3.375 3.375 0 0 0 2.456 2.456L21.75 6l-1.035.259a3.375 3.375 0 0 0-2.456 2.456ZM16.894 20.567 16.5 21.75l-.394-1.183a2.25 2.25 0 0 0-1.423-1.423L13.5 18.75l1.183-.394a2.25 2.25 0 0 0 1.423-1.423l.394-1.183.394 1.183a2.25 2.25 0 0 0 1.423 1.423l1.183.394-1.183.394a2.25 2.25 0 0 0-1.423 1.423Z" /></svg>
                {{ aiPolishing ? '润色中' : '润色' }}
              </button>
            </div>
            <div class="toolbar-divider"></div>
            <div class="toolbar-group">
              <button class="btn btn-ai btn-sm" @click="aiWriteChapter" :disabled="aiWriting">
                <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor" class="size-4 mr-1"><path stroke-linecap="round" stroke-linejoin="round" d="M9.813 15.904 9 18.75l-.813-2.846a4.5 4.5 0 0 0-3.09-3.09L2.25 12l2.846-.813a4.5 4.5 0 0 0 3.09-3.09L9 5.25l.813 2.846a4.5 4.5 0 0 0 3.09 3.09L15.75 12l-2.846.813a4.5 4.5 0 0 0-3.09 3.09ZM18.259 8.715 18 9.75l-.259-1.035a3.375 3.375 0 0 0-2.455-2.456L14.25 6l1.036-.259a3.375 3.375 0 0 0 2.455-2.456L18 2.25l.259 1.035a3.375 3.375 0 0 0 2.456 2.456L21.75 6l-1.035.259a3.375 3.375 0 0 0-2.456 2.456ZM16.894 20.567 16.5 21.75l-.394-1.183a2.25 2.25 0 0 0-1.423-1.423L13.5 18.75l1.183-.394a2.25 2.25 0 0 0 1.423-1.423l.394-1.183.394 1.183a2.25 2.25 0 0 0 1.423 1.423l1.183.394-1.183.394a2.25 2.25 0 0 0-1.423 1.423Z" /></svg>
                {{ aiWriting ? '生成中' : '生成' }}
              </button>
            </div>
            <div class="toolbar-divider"></div>
            <div class="toolbar-group">
              <button class="btn btn-secondary btn-sm" @click="handleExtractPreview" :disabled="extracting || !editContent?.trim()" title="从章节内容同步设定数据">
                <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor" class="size-4 mr-1"><path stroke-linecap="round" stroke-linejoin="round" d="M20.25 6.375c0 2.278-3.694 4.125-8.25 4.125S3.75 8.653 3.75 6.375m16.5 0c0-2.278-3.694-4.125-8.25-4.125S3.75 4.097 3.75 6.375m16.5 0v11.25c0 2.278-3.694 4.125-8.25 4.125s-8.25-1.847-8.25-4.125V6.375m16.5 0v3.75m-16.5-3.75v3.75m16.5 0v3.75C20.25 16.153 16.556 18 12 18s-8.25-1.847-8.25-4.125v-3.75m16.5 0c0 2.278-3.694 4.125-8.25 4.125s-8.25-1.847-8.25-4.125" /></svg>
                {{ extracting ? '同步中...' : '设定同步' }}
              </button>
            </div>
            <div class="toolbar-divider"></div>
            <div class="toolbar-group toolbar-group-end">
              <button class="btn btn-secondary btn-sm" @click="saveOnly" :disabled="saving" title="保存 (Ctrl+S)">
                <svg v-if="!(saving && saveType === 'only')" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor" class="size-4 mr-1"><path stroke-linecap="round" stroke-linejoin="round" d="m20.25 7.5-.625 10.632a2.25 2.25 0 0 1-2.247 2.118H6.622a2.25 2.25 0 0 1-2.247-2.118L3.75 7.5m8.25 3.25a3 3 0 0 0-3 3 .75.75 0 0 1-1.5 0 4.5 4.5 0 0 1 8 0 3 3 0 0 0 3-3 .75.75 0 0 1 1.5 0 4.5 4.5 0 1 1-9 0 4.5 4.5 0 0 1-.9.636l.9.636" /><path stroke-linecap="round" stroke-linejoin="round" d="M19.5 7.5c0-1.657-1.343-3-3-3h-9c-1.657 0-3 1.343-3 3" /></svg>
                {{ (saving && saveType === 'only') ? '保存中' : '保存' }}
              </button>
              <button class="btn btn-primary btn-sm" @click="saveAndNext" :disabled="saving">
                {{ (saving && saveType === 'next') ? '保存中...' : '下一章' }}
              </button>
            </div>
          </div>
        </header>

        <!-- 编辑器主体 -->
        <div class="editor-wrapper">
          <textarea 
            v-model="editContent" 
            class="main-textarea"
            placeholder="开始创作..."
            spellcheck="false"
          ></textarea>
        </div>

        <!-- 弹窗 -->
        <ConfirmDialog
          :is-open="showPolishDialog"
          title="智能润色确认"
          :message="polishDialogMessage"
          confirm-text="开始润色"
          type="primary"
          @confirm="handlePolishConfirm"
          @cancel="showPolishDialog = false"
        />

        <!-- 提取预览弹窗 -->
        <ExtractionPreviewDialog
          :is-open="showExtractionPreview"
          :chapter="currentChapter?.id || 0"
          :extraction="extractionResult?.extraction"
          :loading="applyingExtraction"
          @confirm="handleExtractionConfirm"
          @cancel="handleExtractionCancel"
        />

        <!-- 收尾规划弹窗 -->
        <div v-if="showEndingDialog" class="modal-overlay">
          <div class="modal-content ending-modal">
            <h3 class="modal-title">🏆 智能收尾规划</h3>
            
            <div v-if="!endingPlan" class="config-section">
              <p class="ending-desc">AI 将根据当前剧情和大纲，为您规划一个精彩的完结路线。</p>
              <div class="form-group ending-form-group">
                <label>预计完结章数</label>
                <div class="range-wrapper">
                  <input type="range" v-model.number="remainingChapters" min="3" max="15" step="1" />
                  <span class="range-val">{{ remainingChapters }} 章</span>
                </div>
              </div>
              <div class="modal-actions">
                <button class="btn btn-secondary" @click="showEndingDialog = false">取消</button>
                <button class="btn btn-ai" @click="generateEnding" :disabled="generatingEnding">
                  {{ generatingEnding ? 'AI 规划中...' : '生成收尾大纲' }}
                </button>
              </div>
            </div>

            <div v-else class="plan-preview">
              <div class="plan-strategy">
                <strong>策略：</strong> {{ endingPlan.ending_strategy || endingPlan.ending_straregy }}
              </div>
              <div class="plan-chapters">
                <div v-for="ch in endingPlan.chapters" :key="ch.chapter_num" class="plan-chapter-item">
                  <div class="plan-ch-title">{{ ch.title }}</div>
                  <div class="plan-ch-summary">{{ ch.summary }}</div>
                  <div class="plan-ch-purpose">{{ ch.purpose }}</div>
                </div>
              </div>
              <div class="modal-actions ending-actions">
                <button class="btn btn-secondary" @click="endingPlan = null">重试</button>
                <button class="btn btn-primary" @click="applyEndingPlan">应用规划并开始</button>
              </div>
            </div>
            
            <button class="close-btn" @click="showEndingDialog = false" v-if="!generatingEnding">×</button>
          </div>
        </div>

      </div>

      <!-- 右侧审查面板 -->
      <Transition name="review-slide">
        <div v-if="reviewResult" class="review-panel">
          <div class="review-header">
            <span class="review-title">📋 审查结果</span>
            <button class="close-review" @click="reviewResult = null">
              <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor" class="size-5"><path stroke-linecap="round" stroke-linejoin="round" d="M6 18 18 6M6 6l12 12" /></svg>
            </button>
          </div>
          <textarea
            v-model="reviewText"
            class="review-text-editor"
            placeholder="审查结果加载中..."
          ></textarea>
        </div>
      </Transition>
      </div>

      <div v-else class="empty-state">
        <div class="empty-content">
          <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor" class="empty-icon"><path stroke-linecap="round" stroke-linejoin="round" d="m16.862 4.487 1.687-1.688a1.875 1.875 0 1 1 2.652 2.652L10.582 16.07a4.5 4.5 0 0 1-1.897 1.13L6 18l.8-2.685a4.5 4.5 0 0 1 1.13-1.897l8.932-8.931Zm0 0L19.5 7.125M18 14v4.75A2.25 2.25 0 0 1 15.75 21H5.25A2.25 2.25 0 0 1 3 18.75V8.25A2.25 2.25 0 0 1 5.25 6H10" /></svg>
          <h3>准备好开始新的篇章了吗？</h3>
          <p>选择左侧章节，或点击下方按钮开始创作</p>
          <button class="btn btn-primary" @click="createNewChapter">
            <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor" class="size-5 mr-2"><path stroke-linecap="round" stroke-linejoin="round" d="M12 4.5v15m7.5-7.5h-15" /></svg>
            新建章节
          </button>
        </div>
      </div>
    </main>
    <ConfirmDialog 
      :is-open="showDeleteDialog"
      title="删除章节"
      :message="`确定要删除第 ${currentChapter?.id} 章吗？\n此操作不可恢复！`"
      confirm-text="确认删除"
      type="danger"
      @confirm="handleDeleteConfirm"
      @cancel="showDeleteDialog = false"
    />
  </div>
</template>

<style scoped>
/* ═══════════════════════════════════════════════════════
   WriteView — "墨砚书房" Aesthetic
   A warm literary workspace for immersive novel writing.
   Warm parchment tones, ink-dark accents, refined serif
   typography, and a sense of crafted depth throughout.
   ═══════════════════════════════════════════════════════ */

/* ─── Popup Notifications ─── */
.popup-notification {
  position: fixed;
  top: 24px;
  right: 24px;
  z-index: 9999;
  display: flex;
  align-items: center;
  gap: 14px;
  padding: 14px 20px;
  border-radius: 14px;
  box-shadow:
    0 12px 40px rgba(60, 50, 35, 0.2),
    0 0 0 1px rgba(255, 255, 255, 0.15) inset;
  backdrop-filter: blur(16px) saturate(1.4);
  color: white;
  max-width: 380px;
  font-size: 0.875rem;
  letter-spacing: 0.01em;
  background: linear-gradient(135deg, #5c4a32 0%, #8b7355 100%);
}

.popup-notification.info {
  background: linear-gradient(135deg, #4a3c2a 0%, #7c6545 100%);
}

.popup-notification.success {
  background: linear-gradient(135deg, #065f46 0%, #059669 100%);
}

.popup-notification.warning {
  background: linear-gradient(135deg, #92400e 0%, #d97706 100%);
}

.popup-icon svg {
  width: 22px;
  height: 22px;
  animation: spin 2s linear infinite;
  opacity: 0.9;
}

@keyframes spin {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}

.popup-content { flex: 1; }

.popup-title {
  font-weight: 600;
  font-size: 13px;
  margin-bottom: 3px;
  letter-spacing: 0.02em;
}

.popup-message {
  font-size: 12.5px;
  opacity: 0.85;
  line-height: 1.45;
}

.popup-close {
  background: rgba(255, 255, 255, 0.12);
  border: none;
  color: white;
  font-size: 16px;
  width: 26px;
  height: 26px;
  border-radius: 8px;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: background 0.2s;
  flex-shrink: 0;
}

.popup-close:hover {
  background: rgba(255, 255, 255, 0.25);
}

/* Popup Animation */
.popup-enter-active {
  transition: all 0.4s cubic-bezier(0.16, 1, 0.3, 1);
}
.popup-leave-active {
  transition: all 0.25s ease-in;
}

.popup-enter-from {
  opacity: 0;
  transform: translateX(80px) scale(0.95);
}

.popup-leave-to {
  opacity: 0;
  transform: translateX(60px) scale(0.97);
}

/* ─── Root Layout ─── */
.write-layout {
  display: flex;
  height: 100%;
  width: 100%;
  overflow: hidden;
  background-color: #f8f6f1;
}

/* ─── Chapter Sidebar ─── */
.chapter-nav {
  width: 280px;
  border-right: 1px solid #e8e4da;
  background: linear-gradient(180deg, #fdfcf9 0%, #f5f2eb 100%);
  display: flex;
  flex-direction: column;
  transition: width 0.35s cubic-bezier(0.4, 0, 0.2, 1);
  flex-shrink: 0;
  position: relative;
}

.chapter-nav::after {
  content: '';
  position: absolute;
  top: 0;
  right: 0;
  bottom: 0;
  width: 1px;
  background: linear-gradient(180deg, transparent, rgba(139, 115, 85, 0.08) 50%, transparent);
  pointer-events: none;
}

.chapter-nav.collapsed {
  width: 0;
  border: none;
  overflow: hidden;
}

.nav-header {
  padding: 1.25rem 1.25rem 1rem;
  display: flex;
  align-items: center;
  justify-content: space-between;
  border-bottom: 1px solid #e8e4da;
  background: rgba(255, 255, 255, 0.5);
}

.nav-title {
  font-size: 0.9375rem;
  font-weight: 700;
  color: var(--text-primary);
  margin: 0;
  display: flex;
  align-items: center;
  letter-spacing: 0.04em;
  text-transform: uppercase;
}

.nav-title svg {
  opacity: 0.5;
}

.icon-btn {
  background: rgba(255, 255, 255, 0.7);
  border: 1px solid #e0dbd2;
  cursor: pointer;
  padding: 0.375rem;
  border-radius: 8px;
  color: var(--text-secondary);
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all 0.25s cubic-bezier(0.4, 0, 0.2, 1);
}

.icon-btn:hover {
  border-color: var(--primary);
  color: var(--primary);
  background: white;
  box-shadow: 0 2px 8px rgba(139, 115, 85, 0.12);
  transform: translateY(-1px);
}

.chapter-list {
  flex: 1;
  overflow-y: auto;
  padding: 0.5rem 0.625rem;
  scrollbar-width: thin;
  scrollbar-color: rgba(139, 115, 85, 0.15) transparent;
}

.chapter-list::-webkit-scrollbar { width: 4px; }
.chapter-list::-webkit-scrollbar-track { background: transparent; }
.chapter-list::-webkit-scrollbar-thumb {
  background: rgba(139, 115, 85, 0.15);
  border-radius: 9999px;
}
.chapter-list::-webkit-scrollbar-thumb:hover {
  background: rgba(139, 115, 85, 0.3);
}

/* Volume Groups */
.volume-group {
  margin-bottom: 0.25rem;
}

.volume-header {
  display: flex;
  align-items: center;
  padding: 0.625rem 0.625rem 0.625rem 0.875rem;
  cursor: pointer;
  border-radius: 8px;
  transition: all 0.2s;
  font-weight: 650;
  font-size: 0.8125rem;
  color: var(--text-primary);
  border-left: 3px solid var(--primary);
  margin-left: 0.125rem;
  letter-spacing: 0.01em;
}

.volume-header:hover {
  background: rgba(139, 115, 85, 0.05);
}

.volume-arrow {
  width: 14px;
  height: 14px;
  margin-right: 0.5rem;
  transition: transform 0.25s cubic-bezier(0.4, 0, 0.2, 1);
  color: var(--text-muted);
  flex-shrink: 0;
}

.volume-arrow.expanded {
  transform: rotate(90deg);
}

.volume-title {
  flex: 1;
  font-size: 0.8125rem;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.volume-count {
  font-size: 0.6875rem;
  color: var(--text-muted);
  font-weight: 500;
  background: rgba(0, 0, 0, 0.04);
  padding: 1px 8px;
  border-radius: 9999px;
  flex-shrink: 0;
}

.volume-chapters {
  padding-left: 0.375rem;
  border-left: 1.5px solid rgba(139, 115, 85, 0.12);
  margin-left: 0.75rem;
  margin-top: 2px;
  margin-bottom: 4px;
}

/* Chapter Items */
.chapter-item {
  display: flex;
  align-items: center;
  padding: 0.5rem 0.75rem;
  border-radius: 8px;
  cursor: pointer;
  margin-bottom: 1px;
  color: var(--text-secondary);
  font-size: 0.8125rem;
  transition: all 0.2s cubic-bezier(0.4, 0, 0.2, 1);
  border: 1px solid transparent;
  position: relative;
}

.chapter-item:hover {
  background-color: rgba(139, 115, 85, 0.04);
  color: var(--text-primary);
}

.chapter-item.active {
  background: linear-gradient(135deg, rgba(139, 115, 85, 0.06), rgba(139, 115, 85, 0.1));
  color: var(--primary-dark);
  font-weight: 600;
  border-left: 3px solid var(--primary);
  border-radius: 0 8px 8px 0;
  box-shadow: 0 1px 3px rgba(139, 115, 85, 0.08);
}

.chapter-num {
  font-family: 'SF Mono', 'Cascadia Code', 'Fira Code', monospace;
  margin-right: 0.625rem;
  font-size: 0.6875rem;
  font-weight: 600;
  background: linear-gradient(135deg, rgba(139, 115, 85, 0.1), rgba(139, 115, 85, 0.12));
  color: var(--primary);
  padding: 2px 8px;
  border-radius: 6px;
  min-width: 1.75rem;
  text-align: center;
  flex-shrink: 0;
  line-height: 1.4;
}

.chapter-name {
  flex: 1;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  line-height: 1.4;
}

.chapter-done-icon {
  width: 0.8125rem;
  height: 0.8125rem;
  flex-shrink: 0;
  margin-left: auto;
  color: #059669;
  opacity: 0.7;
}

.nav-footer {
  padding: 0.75rem 1rem;
  border-top: 1px solid #e8e4da;
  display: flex;
  justify-content: flex-end;
  gap: 0.5rem;
  background: rgba(255, 255, 255, 0.3);
}

.toggle-btn {
  border: none;
  background: rgba(0, 0, 0, 0.03);
  color: var(--text-secondary);
  cursor: pointer;
  padding: 0.4375rem;
  border-radius: 8px;
  transition: all 0.2s;
  display: flex;
  align-items: center;
  justify-content: center;
}
.toggle-btn:hover {
  background: rgba(139, 115, 85, 0.08);
  color: var(--primary);
}

/* ─── Main Editor ─── */
.editor-main {
  flex: 1;
  display: flex;
  flex-direction: column;
  background-color: #f8f6f1;
  position: relative;
  min-width: 0;
}

.editor-area {
  display: flex;
  flex: 1;
  height: 100%;
  min-height: 0;
}

.editor-container {
  display: flex;
  flex-direction: column;
  flex: 1;
  min-width: 0;
  height: 100%;
  max-width: 920px;
  margin: 0 auto;
  width: 100%;
  position: relative;
}

/* ─── Toolbar ─── */
.editor-toolbar {
  padding: 0.875rem 1.5rem 0.75rem;
  display: flex;
  flex-direction: column;
  gap: 0.625rem;
  border-bottom: 1px solid #e8e4da;
  background: linear-gradient(180deg, #fffffe 0%, #fdfcf9 100%);
  box-shadow: 0 1px 4px rgba(60, 50, 35, 0.03);
  z-index: 10;
  position: relative;
}

.toolbar-row {
  display: flex;
  align-items: center;
  width: 100%;
}

.toolbar-actions {
  gap: 0.375rem;
  padding-top: 2px;
}

.toolbar-group {
  display: flex;
  align-items: center;
  gap: 0.25rem;
}

.toolbar-group-end {
  margin-left: auto;
}

.toolbar-divider {
  width: 1px;
  height: 1.25rem;
  background: linear-gradient(180deg, transparent, #d5d0c6, transparent);
  flex-shrink: 0;
  margin: 0 0.25rem;
}

.toolbar-left { flex: 1; min-width: 0; }
.toolbar-right { display: flex; align-items: center; gap: 0.5rem; }

.title-input {
  width: 100%;
  font-size: 1.375rem;
  font-weight: 700;
  border: none;
  background: transparent;
  outline: none;
  color: var(--text-primary);
  font-family: 'Georgia', 'Noto Serif SC', 'Source Han Serif SC', serif;
  letter-spacing: 0.01em;
}

.title-input::placeholder {
  color: #c4bfb4;
  font-style: italic;
  font-weight: 400;
}

.divider { display: none; }

.word-count-badge {
  font-size: 0.75rem;
  font-weight: 500;
  color: #9c958a;
  font-variant-numeric: tabular-nums;
  white-space: nowrap;
  background: rgba(0, 0, 0, 0.03);
  padding: 3px 10px;
  border-radius: 9999px;
  letter-spacing: 0.02em;
}

/* Ghost button */
.img-btn-ghost {
  background: transparent;
  border: none;
  padding: 0.375rem;
  box-shadow: none;
  border-radius: 8px;
  color: #b8b0a4;
  transition: all 0.2s;
}
.img-btn-ghost:hover {
  background: rgba(239, 68, 68, 0.06);
  color: #ef4444;
}

/* ─── Editor Writing Area ─── */
.editor-wrapper {
  flex: 1;
  overflow: hidden;
  background: linear-gradient(180deg, #fdfcf9 0%, #faf8f3 100%);
  position: relative;
}

.editor-wrapper::before {
  content: '';
  position: absolute;
  top: 0;
  left: 50%;
  transform: translateX(-50%);
  width: min(800px, 90%);
  height: 100%;
  background: white;
  box-shadow:
    -1px 0 0 #eee8dd,
    1px 0 0 #eee8dd,
    0 0 40px rgba(60, 50, 35, 0.03);
  pointer-events: none;
  z-index: 0;
}

.main-textarea {
  width: 100%;
  height: 100%;
  border: none;
  resize: none;
  background: transparent;
  font-size: 1.0625rem;
  line-height: 2;
  color: #2c2825;
  outline: none;
  font-family: 'Georgia', 'Noto Serif SC', 'Source Han Serif SC', serif;
  padding: 2.5rem 5rem;
  box-sizing: border-box;
  position: relative;
  z-index: 1;
  letter-spacing: 0.02em;
}

.main-textarea::placeholder {
  color: #cec7bb;
  font-style: italic;
}

/* ─── Review Panel ─── */
.review-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding-bottom: 0.75rem;
  border-bottom: 1px solid #e8e4da;
}

.review-title {
  font-weight: 700;
  font-size: 0.875rem;
  color: var(--text-primary);
  letter-spacing: 0.02em;
}

.review-text-editor {
  width: 100%;
  flex: 1;
  min-height: 200px;
  font-size: 0.8125rem;
  color: #3f3a35;
  line-height: 1.7;
  background: rgba(255, 255, 255, 0.6);
  border: 1px solid #e0dbd2;
  border-radius: 10px;
  resize: none;
  font-family: 'SF Mono', 'Cascadia Code', 'Menlo', monospace;
  outline: none;
  padding: 1rem;
  transition: all 0.25s;
}

.review-text-editor:hover {
  border-color: #d0cac0;
}

.review-text-editor:focus {
  background: rgba(255, 255, 255, 0.85);
  border-color: var(--primary);
  box-shadow: 0 0 0 3px rgba(139, 115, 85, 0.08);
}

.close-review {
  background: rgba(0, 0, 0, 0.04);
  border: none;
  cursor: pointer;
  color: var(--text-muted);
  padding: 0.3125rem;
  border-radius: 8px;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all 0.2s;
}

.close-review:hover {
  color: var(--text-primary);
  background: rgba(0, 0, 0, 0.08);
}

.close-review svg {
  width: 16px;
  height: 16px;
}

.review-panel {
  width: 360px;
  flex-shrink: 0;
  background: linear-gradient(180deg, #fdfcf9, #f8f6f1);
  border-left: 1px solid #e8e4da;
  padding: 1.25rem;
  display: flex;
  flex-direction: column;
  gap: 0.875rem;
  height: 100%;
  overflow-y: auto;
  scrollbar-width: thin;
  scrollbar-color: rgba(139, 115, 85, 0.12) transparent;
  position: relative;
}

.review-panel::before {
  content: '';
  position: absolute;
  top: 0;
  left: 0;
  bottom: 0;
  width: 1px;
  background: linear-gradient(180deg, transparent, rgba(139, 115, 85, 0.1) 50%, transparent);
  pointer-events: none;
}

/* Review slide transition */
.review-slide-enter-active {
  transition: all 0.35s cubic-bezier(0.16, 1, 0.3, 1);
}
.review-slide-leave-active {
  transition: all 0.2s ease-in;
}
.review-slide-enter-from {
  opacity: 0;
  transform: translateX(30px);
}
.review-slide-leave-to {
  opacity: 0;
  transform: translateX(30px);
}

/* ─── Expand Sidebar Button ─── */
.expand-sidebar-btn {
  position: absolute;
  left: 1rem;
  top: 1.25rem;
  z-index: 50;
  background: rgba(255, 255, 255, 0.85);
  backdrop-filter: blur(8px);
  border: 1px solid #e0dbd2;
  border-radius: 10px;
  padding: 0.4375rem;
  cursor: pointer;
  color: var(--text-secondary);
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.05);
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all 0.25s cubic-bezier(0.4, 0, 0.2, 1);
}
.expand-sidebar-btn:hover {
  background: white;
  color: var(--primary);
  box-shadow: 0 4px 16px rgba(139, 115, 85, 0.12);
  transform: translateY(-1px);
}

/* ─── Status Toast ─── */
.status-toast {
  position: fixed;
  top: 1.25rem;
  left: 50%;
  transform: translateX(-50%);
  background: #3c3224;
  color: white;
  padding: 0.5rem 1.25rem;
  border-radius: 10px;
  font-size: 0.8125rem;
  font-weight: 500;
  z-index: 200;
  box-shadow: 0 8px 24px rgba(60, 50, 35, 0.2);
  pointer-events: none;
  letter-spacing: 0.01em;
  backdrop-filter: blur(8px);
}
.status-toast.success {
  background: linear-gradient(135deg, #065f46, #059669);
}
.status-toast.error {
  background: linear-gradient(135deg, #991b1b, #dc2626);
}

/* ─── Empty State ─── */
.empty-state {
  display: flex;
  align-items: center;
  justify-content: center;
  height: 100%;
  background: linear-gradient(180deg, #fdfcf9, #f5f2eb);
}

.empty-content {
  text-align: center;
  max-width: 360px;
}

.empty-content h3 {
  font-size: 1.375rem;
  margin-bottom: 0.625rem;
  color: var(--text-primary);
  font-family: 'Georgia', 'Noto Serif SC', serif;
  font-weight: 700;
  letter-spacing: 0.02em;
}

.empty-content p {
  color: #9c958a;
  margin-bottom: 2rem;
  font-size: 0.9375rem;
  line-height: 1.6;
}

.empty-icon {
  width: 3.5rem;
  height: 3.5rem;
  color: #c4bfb4;
  margin: 0 auto 1.25rem;
  display: block;
}

/* ─── Toolbar Sizing ─── */
.btn-sm {
  padding: 0.3125rem 0.6875rem;
  font-size: 0.8125rem;
  border-radius: 8px;
  font-weight: 500;
  letter-spacing: 0.01em;
}

/* Header Actions */
.header-actions {
  display: flex;
  align-items: center;
  margin-left: 0.5rem;
}

/* ─── Ending Button ─── */
.ending-btn {
  margin-left: 0.5rem;
  background: #fefce8;
  color: #92400e;
  border: 1px solid #fde68a;
}
.ending-btn:hover {
  background: #fef9c3;
  color: #78350f;
  box-shadow: 0 2px 8px rgba(245, 158, 11, 0.15);
}

/* ─── Loading State ─── */
.loading-state {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  padding: 1.25rem;
  color: var(--text-muted);
  font-size: 0.8125rem;
}

.spinner-sm {
  width: 0.875rem;
  height: 0.875rem;
  border: 2px solid #e8e4da;
  border-top-color: var(--primary);
  border-radius: 50%;
  animation: spin 0.6s linear infinite;
}

/* ─── Modal Styles ─── */
.modal-overlay {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(60, 50, 35, 0.35);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 100;
  backdrop-filter: blur(6px);
}

.modal-content {
  background: #fdfcf9;
  padding: 2rem;
  border-radius: 16px;
  width: 90%;
  max-width: 500px;
  box-shadow:
    0 24px 64px rgba(60, 50, 35, 0.15),
    0 0 0 1px rgba(0, 0, 0, 0.04);
  position: relative;
  animation: modalPop 0.35s cubic-bezier(0.16, 1, 0.3, 1);
}

.ending-modal {
  max-width: 680px;
  max-height: 85vh;
  display: flex;
  flex-direction: column;
}

.modal-title {
  font-size: 1.375rem;
  font-weight: 700;
  margin-bottom: 1.25rem;
  color: var(--text-primary);
  text-align: center;
  letter-spacing: 0.02em;
}

.modal-actions {
  display: flex;
  gap: 0.75rem;
  justify-content: flex-end;
}

.close-btn {
  position: absolute;
  top: 1rem;
  right: 1rem;
  background: rgba(0, 0, 0, 0.04);
  border: none;
  font-size: 1.25rem;
  width: 32px;
  height: 32px;
  border-radius: 8px;
  cursor: pointer;
  color: var(--text-muted);
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all 0.2s;
}
.close-btn:hover {
  background: rgba(0, 0, 0, 0.08);
  color: var(--text-primary);
}

.range-wrapper {
  display: flex;
  align-items: center;
  gap: 1rem;
}

.range-wrapper input {
  flex: 1;
  accent-color: var(--primary);
}
.range-val {
  font-weight: 600;
  font-family: 'SF Mono', monospace;
  font-size: 0.875rem;
  color: var(--primary);
}

.plan-chapters {
  overflow-y: auto;
  flex: 1;
  border: 1px solid #e8e4da;
  border-radius: 12px;
  padding: 0.75rem;
  background: rgba(255, 255, 255, 0.5);
}

.plan-chapter-item {
  padding: 0.875rem;
  border-bottom: 1px solid #eee8dd;
  border-radius: 8px;
  transition: background 0.15s;
}
.plan-chapter-item:last-child { border-bottom: none; }
.plan-chapter-item:hover { background: rgba(139, 115, 85, 0.03); }

@keyframes modalPop {
  from { opacity: 0; transform: scale(0.96) translateY(8px); }
  to { opacity: 1; transform: scale(1) translateY(0); }
}

/* ─── Ending Modal Extras ─── */
.config-section {
  display: flex;
  flex-direction: column;
  gap: 1.25rem;
}

.ending-desc {
  color: #7c756b;
  font-size: 0.9375rem;
  line-height: 1.6;
}

.ending-form-group {
  margin-bottom: 0.5rem;
}

.ending-actions {
  margin-top: 1.5rem;
}

.plan-preview {
  display: flex;
  flex-direction: column;
  gap: 1rem;
  flex: 1;
  min-height: 0;
}

.plan-strategy {
  padding: 0.875rem 1rem;
  background: linear-gradient(135deg, rgba(139, 115, 85, 0.04), rgba(139, 115, 85, 0.06));
  border-radius: 10px;
  font-size: 0.9rem;
  line-height: 1.6;
  border: 1px solid rgba(139, 115, 85, 0.08);
}

.plan-ch-title {
  font-weight: 650;
  color: var(--text-primary);
  font-size: 0.9rem;
}

.plan-ch-summary {
  font-size: 0.8125rem;
  color: var(--text-secondary);
  margin-top: 0.375rem;
  line-height: 1.5;
}

.plan-ch-purpose {
  font-size: 0.75rem;
  color: var(--primary);
  margin-top: 0.25rem;
  font-weight: 500;
}

/* ─── Form Group ─── */
.form-group {
  margin-bottom: 1rem;
}

.form-group label {
  display: block;
  font-weight: 600;
  margin-bottom: 0.5rem;
  color: var(--text-primary);
  font-size: 0.8125rem;
  letter-spacing: 0.02em;
}

/* ─── Toast Transition ─── */
.toast-enter-active {
  transition: all 0.35s cubic-bezier(0.16, 1, 0.3, 1);
}
.toast-leave-active {
  transition: all 0.25s ease-in;
}

.toast-enter-from {
  opacity: 0;
  transform: translateX(-50%) translateY(-16px) scale(0.95);
}

.toast-leave-to {
  opacity: 0;
  transform: translateX(-50%) translateY(-12px);
}

/* ─── Responsive ─── */
@media (max-width: 768px) {
  .chapter-nav {
    position: absolute;
    height: 100%;
    z-index: 20;
    box-shadow: 4px 0 24px rgba(0, 0, 0, 0.08);
  }
  .chapter-nav.collapsed { width: 0; border: none; box-shadow: none; }
  .editor-wrapper { padding: 0; }
  .editor-toolbar { padding: 0.625rem 1rem 0.5rem; }
  .toolbar-actions { flex-wrap: wrap; }
  .title-input { font-size: 1.125rem; }
  .main-textarea { padding: 1.5rem 1.25rem; }

  .editor-area {
    flex-direction: column;
  }

  .review-panel {
    width: 100%;
    height: auto;
    max-height: 50vh;
    border-left: none;
    border-top: 1px solid #e8e4da;
    box-shadow: 0 -6px 20px rgba(0, 0, 0, 0.06);
  }

  .review-slide-enter-from,
  .review-slide-leave-to {
    transform: translateY(100%);
  }

  .editor-wrapper::before { display: none; }
}
</style>
