<!-- Copyright (c) 2026 左岚. All rights reserved. -->
<!-- GoldenFingerChat.vue - AI 共创金手指对话弹窗（新建小说时使用） -->
<script setup>
import { ref, nextTick, onMounted } from 'vue'
import { marked } from 'marked'
import DOMPurify from 'dompurify'
import { aiApi } from '../api'

marked.setOptions({ breaks: true, gfm: true })

// 渲染 AI 返回的 Markdown（净化防 XSS）
function renderMarkdown(text) {
  return DOMPurify.sanitize(marked.parse(text || ''))
}

const props = defineProps({
  genre: { type: String, default: '玄幻' },
  substyle: { type: String, default: '' },
  seed: { type: String, default: '' },
  // 内嵌模式：作为父弹窗内的一块内容渲染，不再套自己的全屏遮罩
  embedded: { type: Boolean, default: false }
})

const emit = defineEmits(['close', 'apply'])

// 阶段：chat（对话中）/ result（已生成设定，可编辑）
const phase = ref('chat')

// 对话历史（不含 system），role: 'user' | 'assistant'
const messages = ref([])
const input = ref('')
const streaming = ref(false)      // 是否正在流式接收 AI 回复
const generating = ref(false)     // 是否正在生成最终设定
const errorMsg = ref('')
const messagesEl = ref(null)

// 生成结果
const titleCandidates = ref([])   // [{ title, reason }]
const selectedTitle = ref('')
const goldenFingerDesign = ref('') // 可编辑的金手指文档

function scrollToBottom() {
  nextTick(() => {
    if (messagesEl.value) messagesEl.value.scrollTop = messagesEl.value.scrollHeight
  })
}

// 通用 SSE 读取：逐块回调 onChunk
async function readStream(response, onChunk) {
  if (!response.ok) throw new Error(`请求失败: ${response.status}`)
  const reader = response.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''
  while (true) {
    const { done, value } = await reader.read()
    if (done) break
    buffer += decoder.decode(value, { stream: true })
    const lines = buffer.split('\n\n')
    buffer = lines.pop()
    for (const line of lines) {
      if (!line.startsWith('data: ')) continue
      let data
      try {
        data = JSON.parse(line.substring(6))
      } catch (e) {
        continue
      }
      if (data.type === 'content') {
        onChunk(data.chunk || '')
      } else if (data.type === 'error') {
        throw new Error(data.message || 'AI 流式返回错误')
      } else if (data.type === 'done') {
        return
      }
    }
  }
}

async function sendMessage() {
  const text = input.value.trim()
  if (!text || streaming.value) return
  errorMsg.value = ''
  messages.value.push({ role: 'user', content: text })
  input.value = ''
  scrollToBottom()

  // 追加一个空的 assistant 气泡用于流式填充
  const aiMsg = ref('')
  messages.value.push({ role: 'assistant', content: '' })
  const aiIndex = messages.value.length - 1
  streaming.value = true
  try {
    const response = await aiApi.goldenFingerChatStream({
      messages: messages.value.slice(0, aiIndex).map(m => ({ role: m.role, content: m.content })),
      genre: props.genre,
      substyle: props.substyle,
      seed: props.seed
    })
    await readStream(response, (chunk) => {
      aiMsg.value += chunk
      messages.value[aiIndex].content = aiMsg.value
      scrollToBottom()
    })
    if (!messages.value[aiIndex].content) {
      messages.value[aiIndex].content = '（AI 未返回内容，请重试）'
    }
  } catch (e) {
    messages.value[aiIndex].content = ''
    errorMsg.value = e.message || '对话失败'
  } finally {
    streaming.value = false
    scrollToBottom()
  }
}

// 解析生成结果：===书名=== 段 + ===金手指=== 段
function parseResult(raw) {
  const gfMarker = raw.indexOf('===金手指===')
  const titleMarker = raw.indexOf('===书名===')

  let titleBlock = ''
  let gfBlock = ''
  if (gfMarker >= 0) {
    const titleStart = titleMarker >= 0 ? titleMarker + '===书名==='.length : 0
    titleBlock = raw.substring(titleStart, gfMarker)
    gfBlock = raw.substring(gfMarker + '===金手指==='.length)
  } else {
    // 没有金手指标记：整体当作金手指文档
    gfBlock = titleMarker >= 0 ? raw.substring(titleMarker + '===书名==='.length) : raw
  }

  const titles = []
  for (let line of titleBlock.split('\n')) {
    line = line.replace(/^\s*\d+[.、\s]+/, '').trim()
    line = line.replace(/^[-*]\s*/, '')
    if (!line) continue
    if (line.includes('|')) {
      const [t, ...rest] = line.split('|')
      const title = t.replace(/《|》/g, '').trim()
      if (title) titles.push({ title, reason: rest.join('|').trim() })
    } else {
      const title = line.replace(/《|》/g, '').trim()
      if (title) titles.push({ title, reason: '' })
    }
  }
  return { titles, gf: gfBlock.trim() }
}

async function generateDesign() {
  if (generating.value || streaming.value) return
  if (!messages.value.some(m => m.role === 'user') && !props.seed) {
    errorMsg.value = '请先和 AI 聊几句，把金手指想法说清楚再生成'
    return
  }
  errorMsg.value = ''
  generating.value = true
  let raw = ''
  try {
    const response = await aiApi.goldenFingerGenerateStream({
      messages: messages.value.map(m => ({ role: m.role, content: m.content })),
      genre: props.genre,
      substyle: props.substyle,
      seed: props.seed
    })
    await readStream(response, (chunk) => {
      raw += chunk
      // 实时预览金手指部分
      const { gf } = parseResult(raw)
      if (gf) goldenFingerDesign.value = gf
    })
    const { titles, gf } = parseResult(raw)
    titleCandidates.value = titles
    selectedTitle.value = titles.length ? titles[0].title : ''
    goldenFingerDesign.value = gf || raw.trim()
    phase.value = 'result'
  } catch (e) {
    errorMsg.value = e.message || '生成失败'
  } finally {
    generating.value = false
  }
}

function applyResult() {
  const title = (selectedTitle.value || '').trim()
  if (!title) {
    errorMsg.value = '请先选择或填写一个书名'
    return
  }
  if (!goldenFingerDesign.value.trim()) {
    errorMsg.value = '金手指设定不能为空'
    return
  }
  emit('apply', {
    title,
    goldenFingerDesign: goldenFingerDesign.value.trim()
  })
}

function backToChat() {
  phase.value = 'chat'
}

function onInputKeydown(e) {
  if (e.key === 'Enter' && !e.shiftKey) {
    e.preventDefault()
    sendMessage()
  }
}

// 输入框随内容自动增高（上限 8rem，超出滚动）
function autoResize(e) {
  const el = e.target
  el.style.height = 'auto'
  el.style.height = Math.min(el.scrollHeight, 128) + 'px'
}

function handleOverlayClick() {
  if (!props.embedded) {
    emit('close')
  }
}

onMounted(() => {
  // AI 主动开场
  sendOpening()
})

async function sendOpening() {
  streaming.value = true
  const aiMsg = ref('')
  messages.value.push({ role: 'assistant', content: '' })
  const aiIndex = messages.value.length - 1
  try {
    const response = await aiApi.goldenFingerChatStream({
      messages: [],
      genre: props.genre,
      substyle: props.substyle,
      seed: props.seed
    })
    await readStream(response, (chunk) => {
      aiMsg.value += chunk
      messages.value[aiIndex].content = aiMsg.value
      scrollToBottom()
    })
    if (!messages.value[aiIndex].content) {
      messages.value[aiIndex].content = '想要什么样的核心金手指？说说你的初步想法，我帮你把它设计完整。'
    }
  } catch (e) {
    messages.value[aiIndex].content = '想要什么样的核心金手指？说说你的初步想法，我帮你把它设计完整。'
  } finally {
    streaming.value = false
    scrollToBottom()
  }
}
</script>

<template>
  <div :class="embedded ? 'gf-embedded-wrap' : 'modal-overlay'" @click.self="handleOverlayClick">
    <div class="gf-modal">
      <div class="modal-header">
        <h3>
          <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor" class="size-5">
            <path stroke-linecap="round" stroke-linejoin="round" d="M9.813 15.904 9 18.75l-.813-2.846a4.5 4.5 0 0 0-3.09-3.09L2.25 12l2.846-.813a4.5 4.5 0 0 0 3.09-3.09L9 5.25l.813 2.846a4.5 4.5 0 0 0 3.09 3.09L15.75 12l-2.846.813a4.5 4.5 0 0 0-3.09 3.09Z" />
          </svg>
          AI 共创金手指
        </h3>
        <button class="close-btn" @click="emit('close')">
          <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor" class="size-5">
            <path stroke-linecap="round" stroke-linejoin="round" d="M6 18 18 6M6 6l12 12" />
          </svg>
        </button>
      </div>

      <!-- 对话阶段 -->
      <template v-if="phase === 'chat'">
        <div class="chat-messages" ref="messagesEl">
          <div
            v-for="(m, i) in messages"
            :key="i"
            class="chat-msg"
            :class="m.role"
          >
            <!-- AI 消息：渲染 Markdown，保留大模型返回的原始格式 -->
            <div v-if="m.role === 'assistant'" class="msg-role-label">AI</div>
            <div
              v-if="m.role === 'assistant' && m.content"
              class="msg-body md-body"
              v-html="renderMarkdown(m.content)"
            ></div>
            <div v-else-if="m.role === 'assistant'" class="msg-body typing">
              <span></span><span></span><span></span>
            </div>
            <!-- 用户消息：纯文本气泡 -->
            <div v-else class="msg-body user-bubble">{{ m.content }}</div>
          </div>
        </div>

        <div v-if="errorMsg" class="error-bar">{{ errorMsg }}</div>

        <div class="composer" :class="{ disabled: streaming }">
          <textarea
            v-model="input"
            class="composer-input"
            rows="1"
            :placeholder="streaming ? 'AI 正在回复...' : '说说你的金手指想法，回车发送'"
            :disabled="streaming"
            @keydown="onInputKeydown"
            @input="autoResize"
          ></textarea>
          <button
            class="composer-send"
            @click="sendMessage"
            :disabled="streaming || !input.trim()"
            title="发送（Shift+回车换行）"
          >
            <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="currentColor" class="size-5">
              <path d="M3.478 2.404a.75.75 0 0 0-.926.941l2.432 7.905H13.5a.75.75 0 0 1 0 1.5H4.984l-2.432 7.905a.75.75 0 0 0 .926.94 60.519 60.519 0 0 0 18.445-8.986.75.75 0 0 0 0-1.218A60.517 60.517 0 0 0 3.478 2.404Z" />
            </svg>
          </button>
        </div>

        <div class="chat-footer">
          <span class="footer-hint">聊清楚金手指的能力、代价和成长线后，点右侧生成</span>
          <button class="btn btn-primary" @click="generateDesign" :disabled="generating || streaming">
            {{ generating ? '生成中...' : '生成金手指设定' }}
          </button>
        </div>
      </template>

      <!-- 结果阶段 -->
      <template v-else>
        <div class="result-body">
          <div class="result-section">
            <label class="result-label">选择书名</label>
            <div class="title-candidates">
              <button
                v-for="(t, i) in titleCandidates"
                :key="i"
                class="title-chip"
                :class="{ active: selectedTitle === t.title }"
                @click="selectedTitle = t.title"
                :title="t.reason"
              >
                {{ t.title }}
              </button>
            </div>
            <input v-model="selectedTitle" class="input title-input" placeholder="书名（可手动修改）" />
          </div>

          <div class="result-section grow">
            <label class="result-label">金手指设定（可自由编辑）</label>
            <textarea v-model="goldenFingerDesign" class="gf-textarea" placeholder="金手指设定文档..."></textarea>
          </div>
        </div>

        <div v-if="errorMsg" class="error-bar">{{ errorMsg }}</div>

        <div class="modal-actions">
          <button class="btn btn-secondary" @click="backToChat">← 继续对话</button>
          <button class="btn btn-primary" @click="applyResult">用这个创建小说</button>
        </div>
      </template>
    </div>
  </div>
</template>

<style scoped>
.modal-overlay {
  position: fixed;
  top: 0; left: 0; right: 0; bottom: 0;
  background: rgb(15 17 21 / 0.45);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: var(--z-modal-backdrop);
  animation: fadeIn var(--dur-fast) ease-out;
}

@keyframes fadeIn { from { opacity: 0; } to { opacity: 1; } }

/* 嵌入父容器时：撑满父级高度，让内部消息区正常滚动 */
.gf-embedded-wrap {
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
}

.gf-modal {
  background: var(--card);
  border-radius: var(--radius-lg);
  padding: 1.5rem;
  width: 100%;
  max-width: 640px;
  height: 80vh;
  max-height: 720px;
  display: flex;
  flex-direction: column;
  box-shadow: var(--shadow-xl);
  border: 1px solid var(--border);
  animation: scaleIn var(--dur-base) var(--ease-emerge);
}

/* 嵌入模式：去掉独立弹窗的边框/阴影/固定高度，撑满父容器 */
.gf-embedded-wrap .gf-modal {
  border: none;
  box-shadow: none;
  border-radius: 0;
  padding: 0;
  max-width: none;
  height: auto;
  max-height: none;
  animation: none;
  background: transparent;
  flex: 1;
  min-height: 0;
}

/* 嵌入模式下隐藏 header */
.gf-embedded-wrap .modal-header {
  display: none;
}

@keyframes scaleIn {
  from { opacity: 0; transform: scale(0.98); }
  to { opacity: 1; transform: scale(1); }
}

.modal-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 1rem;
  flex-shrink: 0;
}

.modal-header h3 {
  margin: 0;
  font-size: 1.125rem;
  font-weight: 600;
  color: var(--ink-primary);
  display: flex;
  align-items: center;
  gap: 0.5rem;
}

.modal-header h3 svg { color: var(--primary-text); }

.close-btn {
  background: none; border: none; color: var(--ink-muted);
  cursor: pointer; padding: 0.375rem; border-radius: var(--radius-sm);
  display: flex; align-items: center; justify-content: center;
  transition: background-color var(--dur-fast) var(--ease-standard), color var(--dur-fast) var(--ease-standard);
}
.close-btn:hover { background: var(--hover); color: var(--ink-primary); }

/* 对话区：assistant 通栏 Markdown、user 右侧气泡 */
.chat-messages {
  flex: 1;
  overflow-y: auto;
  padding: 0.5rem 0.25rem;
  display: flex;
  flex-direction: column;
  gap: 1.25rem;
  margin-bottom: 1rem;
  scroll-behavior: smooth;
}

.chat-msg {
  display: flex;
  flex-direction: column;
  animation: slideIn 0.25s ease-out;
}

@keyframes slideIn {
  from { opacity: 0; transform: translateY(8px); }
  to { opacity: 1; transform: translateY(0); }
}

@media (prefers-reduced-motion: reduce) {
  .chat-msg { animation: none; }
}

.chat-msg.user {
  align-items: flex-end;
}

.msg-role-label {
  font-size: 0.6875rem;
  font-weight: 600;
  color: var(--primary-text);
  margin-bottom: 0.375rem;
}

/* AI 消息：不加气泡壳，全宽渲染 Markdown */
.chat-msg.assistant .msg-body {
  max-width: 100%;
  font-size: 0.9375rem;
  line-height: 1.7;
  color: var(--ink-primary);
}

/* 用户消息：紧凑气泡 */
.user-bubble {
  max-width: 80%;
  padding: 0.625rem 1rem;
  border-radius: var(--radius-lg);
  border-bottom-right-radius: 4px;
  background: var(--primary-tint);
  color: var(--ink-primary);
  font-size: 0.9375rem;
  line-height: 1.65;
  white-space: pre-wrap;
  word-break: break-word;
}

/* Markdown 渲染样式（v-html 内容需 :deep） */
.md-body :deep(p) { margin: 0 0 0.625rem; }
.md-body :deep(p:last-child) { margin-bottom: 0; }
.md-body :deep(h1),
.md-body :deep(h2),
.md-body :deep(h3),
.md-body :deep(h4) {
  font-size: 1rem;
  font-weight: 600;
  color: var(--ink-primary);
  margin: 1rem 0 0.5rem;
}
.md-body :deep(ul),
.md-body :deep(ol) { margin: 0.25rem 0 0.625rem; padding-left: 1.375rem; }
.md-body :deep(li) { margin-bottom: 0.25rem; }
.md-body :deep(strong) { font-weight: 600; color: var(--ink-primary); }
.md-body :deep(code) {
  font-size: 0.85em;
  font-family: var(--font-mono);
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  padding: 0.1em 0.35em;
}
.md-body :deep(pre) {
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  padding: 0.75rem 1rem;
  overflow-x: auto;
  margin: 0.5rem 0 0.75rem;
}
.md-body :deep(pre code) { background: none; border: none; padding: 0; }
.md-body :deep(blockquote) {
  margin: 0.5rem 0;
  padding-left: 0.875rem;
  border-left: 3px solid var(--border-strong);
  color: var(--ink-secondary);
}
.md-body :deep(hr) {
  border: none;
  border-top: 1px solid var(--border);
  margin: 0.875rem 0;
}
.md-body :deep(a) { color: var(--primary-text); }
.md-body :deep(table) { border-collapse: collapse; margin: 0.5rem 0; }
.md-body :deep(th),
.md-body :deep(td) {
  border: 1px solid var(--border);
  padding: 0.375rem 0.625rem;
  font-size: 0.875rem;
}

/* 流式等待的打字指示 */
.typing {
  display: inline-flex;
  gap: 4px;
  padding: 0.5rem 0;
}
.typing span {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: var(--ink-muted);
  animation: typingBlink 1.2s infinite ease-in-out;
}
.typing span:nth-child(2) { animation-delay: 0.15s; }
.typing span:nth-child(3) { animation-delay: 0.3s; }
@keyframes typingBlink {
  0%, 60%, 100% { opacity: 0.3; transform: translateY(0); }
  30% { opacity: 1; transform: translateY(-3px); }
}
@media (prefers-reduced-motion: reduce) {
  .typing span { animation: none; opacity: 0.5; }
}

/* 一体化输入区：文本框 + 发送按钮 */
.composer {
  display: flex;
  align-items: flex-end;
  gap: 0.5rem;
  padding: 0.5rem 0.5rem 0.5rem 1rem;
  border: 1px solid var(--border);
  border-radius: var(--radius-lg);
  background: var(--card);
  transition: border-color var(--dur-fast) var(--ease-standard), box-shadow var(--dur-fast) var(--ease-standard);
  flex-shrink: 0;
}

.composer:focus-within {
  border-color: var(--primary);
  box-shadow: 0 0 0 3px var(--primary-tint);
}

.composer.disabled {
  background: var(--surface);
}

.composer-input {
  flex: 1;
  border: none;
  outline: none;
  resize: none;
  background: transparent;
  font-size: 0.9375rem;
  font-family: inherit;
  line-height: 1.6;
  padding: 0.5rem 0;
  max-height: 8rem;
  color: var(--ink-primary);
}

.composer-input::placeholder { color: var(--ink-muted); }
.composer-input:disabled { color: var(--ink-muted); }

.composer-send {
  flex-shrink: 0;
  width: 2.5rem;
  height: 2.5rem;
  border-radius: 50%;
  border: none;
  background: var(--primary);
  color: var(--on-primary);
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: background-color var(--dur-fast) var(--ease-standard), transform var(--dur-fast) var(--ease-standard);
}

.composer-send svg {
  width: 1.125rem;
  height: 1.125rem;
}

.composer-send:hover:not(:disabled) {
  background: var(--primary-hover);
}

.composer-send:active:not(:disabled) {
  transform: scale(0.94);
}

.composer-send:disabled {
  background: var(--border);
  color: var(--ink-muted);
  cursor: not-allowed;
}

.chat-footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 1.25rem;
  margin-top: 1.25rem;
  padding-top: 1.25rem;
  border-top: 1px solid var(--border);
  flex-shrink: 0;
}

.footer-hint {
  font-size: 0.8125rem;
  color: var(--ink-muted);
  line-height: 1.5;
}

.chat-footer .btn-primary {
  background: var(--primary);
  border: 1px solid var(--primary);
  color: var(--on-primary);
  font-weight: 500;
  padding: 0.65rem 1.4rem;
}

.chat-footer .btn-primary:hover:not(:disabled) {
  background: var(--primary-hover);
  border-color: var(--primary-hover);
}

/* 结果区 */
.result-body {
  flex: 1;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: 1.25rem;
  min-height: 0;
}
.result-section { display: flex; flex-direction: column; }
.result-section.grow { flex: 1; min-height: 0; }
.result-label {
  font-size: 0.8125rem;
  font-weight: 500;
  color: var(--ink-secondary);
  margin-bottom: 0.5rem;
}
.title-candidates {
  display: flex;
  flex-wrap: wrap;
  gap: 0.5rem;
  margin-bottom: 0.6rem;
}
.title-chip {
  padding: 0.45rem 0.9rem;
  border-radius: var(--radius-md);
  border: 1px solid var(--border);
  background: var(--card);
  font-size: 0.875rem;
  cursor: pointer;
  transition: border-color var(--dur-fast) var(--ease-standard), background-color var(--dur-fast) var(--ease-standard), color var(--dur-fast) var(--ease-standard);
  color: var(--ink-secondary);
  font-weight: 500;
}

.title-chip:hover {
  border-color: var(--border-strong);
  color: var(--ink-primary);
  background: var(--surface);
}

.title-chip.active {
  background: var(--primary-tint);
  border-color: transparent;
  color: var(--primary-on-tint);
  font-weight: 500;
}
.input, .title-input {
  width: 100%;
  padding: 0.65rem 0.9rem;
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  font-size: 0.9375rem;
  outline: none;
  box-sizing: border-box;
  transition: border-color var(--dur-fast) var(--ease-standard), box-shadow var(--dur-fast) var(--ease-standard), background-color var(--dur-fast) var(--ease-standard);
  background: var(--surface);
  color: var(--ink-primary);
}

.title-input:focus {
  border-color: var(--primary);
  background: var(--card);
  box-shadow: 0 0 0 3px var(--primary-tint);
}

.gf-textarea {
  flex: 1;
  width: 100%;
  min-height: 280px;
  padding: 1rem;
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  font-size: 0.9375rem;
  line-height: 1.7;
  font-family: inherit;
  resize: vertical;
  outline: none;
  box-sizing: border-box;
  transition: border-color var(--dur-fast) var(--ease-standard), box-shadow var(--dur-fast) var(--ease-standard), background-color var(--dur-fast) var(--ease-standard);
  background: var(--surface);
  color: var(--ink-primary);
}

.gf-textarea:focus {
  border-color: var(--primary);
  background: var(--card);
  box-shadow: 0 0 0 3px var(--primary-tint);
}

.modal-actions {
  display: flex;
  justify-content: space-between;
  gap: 1rem;
  margin-top: 1.5rem;
  padding-top: 1.25rem;
  border-top: 1px solid var(--border);
  flex-shrink: 0;
}

.modal-actions .btn-secondary {
  padding: 0.65rem 1.2rem;
}

.modal-actions .btn-primary {
  background: var(--primary);
  border: 1px solid var(--primary);
  color: var(--on-primary);
  font-weight: 500;
  padding: 0.65rem 1.6rem;
}

.modal-actions .btn-primary:hover:not(:disabled) {
  background: var(--primary-hover);
  border-color: var(--primary-hover);
}

.error-bar {
  margin-top: 0.75rem;
  padding: 0.6rem 0.9rem;
  background: var(--danger-tint);
  border: 1px solid transparent;
  border-radius: var(--radius-md);
  color: var(--danger);
  font-size: 0.8125rem;
  flex-shrink: 0;
}
</style>
