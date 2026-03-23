<!-- Copyright (c) 2026 左岚. All rights reserved. -->
<script setup>
import { computed, onMounted, onBeforeUnmount, ref } from 'vue'
import { onBeforeRouteLeave } from 'vue-router'
import { projectsApi } from '../api'
import { useProjectStore } from '../stores/project'
import ConfirmDialog from '../components/ConfirmDialog.vue'

const projectStore = useProjectStore()

const loading = ref(false)
const saving = ref(false)
const resetting = ref(false)
const message = ref('')
const promptConfig = ref({ genre: '', substyle: '', prompts: [] })
const draftMap = ref({})
const showSaveDialog = ref(false)
const forceLeave = ref(false)
const showLeaveDialog = ref(false)
let pendingLeaveResolve = null

function showMessage(text, duration = 3000) {
  message.value = text
  setTimeout(() => {
    if (message.value === text) message.value = ''
  }, duration)
}

function applyPromptConfig(data) {
  promptConfig.value = {
    genre: data.genre || '',
    substyle: data.substyle || '',
    prompts: data.prompts || []
  }
  draftMap.value = Object.fromEntries(
    (data.prompts || []).map(item => [item.id, item.content || ''])
  )
}

async function loadPromptConfig() {
  loading.value = true
  try {
    const { data } = await projectsApi.getPromptConfig()
    applyPromptConfig(data)
  } catch (e) {
    showMessage('✗ 加载提示词配置失败')
  } finally {
    loading.value = false
  }
}

function getOriginalPrompt(id) {
  return promptConfig.value.prompts.find(item => item.id === id)?.content || ''
}

function isDirty(id) {
  return (draftMap.value[id] || '') !== getOriginalPrompt(id)
}

const dirtyPromptIds = computed(() => {
  return promptConfig.value.prompts
    .filter(item => isDirty(item.id))
    .map(item => item.id)
})

const promptGroups = computed(() => {
  const groups = new Map()
  for (const item of promptConfig.value.prompts || []) {
    const key = item.group || '其他'
    if (!groups.has(key)) groups.set(key, [])
    groups.get(key).push(item)
  }
  return Array.from(groups.entries()).map(([name, prompts]) => ({ name, prompts }))
})

// 3a. 变量缺失校验
function getMissingVariables(item) {
  const draft = draftMap.value[item.id] || ''
  if (!item.variables?.length || !draft) return []
  return item.variables.filter(v => !draft.includes(`{${v}}`))
}

// 保存确认弹窗需要的汇总信息
const saveDialogSummary = computed(() => {
  const dirtyItems = promptConfig.value.prompts.filter(item => isDirty(item.id))
  return dirtyItems.map(item => ({
    id: item.id,
    name: item.name,
    missing: getMissingVariables(item),
  }))
})

const hasMissingVarsInDirty = computed(() => {
  return saveDialogSummary.value.some(s => s.missing.length > 0)
})

// 3b. 保存确认弹窗
function requestSave() {
  if (!dirtyPromptIds.value.length) {
    showMessage('当前没有未保存的改动')
    return
  }
  showSaveDialog.value = true
}

async function confirmSave() {
  showSaveDialog.value = false
  saving.value = true
  try {
    await projectsApi.updatePromptConfig({
      prompts: dirtyPromptIds.value.map(id => ({
        id,
        content: draftMap.value[id] || ''
      }))
    })
    await loadPromptConfig()
    showMessage('✓ 提示词配置已保存')
  } catch (e) {
    showMessage('✗ 保存提示词配置失败')
  } finally {
    saving.value = false
  }
}

async function resetSlot(id) {
  resetting.value = true
  try {
    const { data } = await projectsApi.resetPromptConfig({ slot_ids: [id] })
    const resetItem = (data.prompts || []).find(item => item.id === id)
    if (resetItem) {
      promptConfig.value = {
        genre: data.genre || promptConfig.value.genre,
        substyle: data.substyle || promptConfig.value.substyle,
        prompts: promptConfig.value.prompts.map(item => item.id === id ? resetItem : item)
      }
      draftMap.value[id] = resetItem.content || ''
    }
    showMessage('✓ 已恢复默认模板')
  } catch (e) {
    showMessage('✗ 恢复默认失败')
  } finally {
    resetting.value = false
  }
}

async function resetAll() {
  resetting.value = true
  try {
    const { data } = await projectsApi.resetPromptConfig({})
    applyPromptConfig(data)
    showMessage('✓ 全部提示词已恢复默认')
  } catch (e) {
    showMessage('✗ 全部恢复失败')
  } finally {
    resetting.value = false
  }
}

// 3c. 离开页面警告
function onBeforeUnload(e) {
  if (dirtyPromptIds.value.length) {
    e.preventDefault()
    e.returnValue = ''
  }
}

onBeforeRouteLeave(() => {
  if (forceLeave.value || !dirtyPromptIds.value.length) return true
  showLeaveDialog.value = true
  return new Promise(resolve => { pendingLeaveResolve = resolve })
})

function confirmLeave() {
  showLeaveDialog.value = false
  forceLeave.value = true
  if (pendingLeaveResolve) {
    pendingLeaveResolve(true)
    pendingLeaveResolve = null
  }
}

function cancelLeave() {
  showLeaveDialog.value = false
  if (pendingLeaveResolve) {
    pendingLeaveResolve(false)
    pendingLeaveResolve = null
  }
}

onMounted(async () => {
  window.addEventListener('beforeunload', onBeforeUnload)
  if (!projectStore.title) {
    await projectStore.fetchStatus()
  }
  await loadPromptConfig()
})

onBeforeUnmount(() => {
  window.removeEventListener('beforeunload', onBeforeUnload)
})
</script>

<template>
  <div class="prompt-config-page">
    <div class="page-shell">
      <header class="page-hero">
        <div>
          <p class="hero-kicker">Project Prompt Registry</p>
          <h1>提示词配置</h1>
          <p class="hero-copy">
            当前项目的写作、审查、收容模板都固定在这里。创建项目后会快照一份到项目目录，后续执行直接读取项目模板，不再按章节临时匹配。
          </p>
        </div>
        <div class="hero-meta">
          <div class="meta-pill">题材：{{ promptConfig.genre || projectStore.genre || '未设定' }}</div>
          <div class="meta-pill">子风格：{{ promptConfig.substyle || projectStore.substyle || '默认' }}</div>
        </div>
      </header>

      <section class="control-bar">
        <div class="control-copy">
          <strong>{{ dirtyPromptIds.length }}</strong>
          <span>个模板有未保存改动</span>
        </div>
        <div class="control-actions">
          <button class="btn ghost" @click="resetAll" :disabled="resetting || loading">
            {{ resetting ? '恢复中...' : '全部恢复默认' }}
          </button>
          <button class="btn solid" @click="requestSave" :disabled="saving || !dirtyPromptIds.length">
            {{ saving ? '保存中...' : '保存全部改动' }}
          </button>
        </div>
      </section>

      <div v-if="loading" class="loading-card">
        正在加载项目提示词配置...
      </div>

      <template v-else>
        <section
          v-for="group in promptGroups"
          :key="group.name"
          class="group-panel"
        >
          <div class="group-head">
            <div>
              <h2>{{ group.name }}</h2>
              <p>这些模板会在当前项目后续流程中直接生效。</p>
            </div>
          </div>

          <div class="prompt-grid">
            <article
              v-for="item in group.prompts"
              :key="item.id"
              class="prompt-card"
              :class="{ dirty: isDirty(item.id) }"
            >
              <div class="prompt-head">
                <div>
                  <h3>{{ item.name }}</h3>
                  <p>{{ item.description }}</p>
                </div>
                <div class="prompt-badges">
                  <span class="badge" :class="item.customized ? 'badge-custom' : 'badge-default'">
                    {{ item.customized ? '已自定义' : '默认快照' }}
                  </span>
                  <span v-if="isDirty(item.id)" class="badge badge-dirty">未保存</span>
                </div>
              </div>

              <div class="slot-meta">
                <div class="slot-meta-row">
                  <span class="slot-label">文件</span>
                  <code>{{ item.filename }}</code>
                </div>
                <div class="slot-meta-row">
                  <span class="slot-label">来源</span>
                  <code>{{ item.source_path || '项目模板' }}</code>
                </div>
                <div v-if="item.variables?.length" class="slot-meta-row">
                  <span class="slot-label">变量</span>
                  <div class="chip-row">
                    <span v-for="variable in item.variables" :key="variable" class="chip" :class="{ 'chip-missing': !(draftMap[item.id] || '').includes(`{${variable}}`) }">{{ variable }}</span>
                  </div>
                </div>
                <div v-if="getMissingVariables(item).length" class="var-warning">
                  缺失变量：{{ getMissingVariables(item).join('、') }}
                </div>
              </div>

              <textarea
                v-model="draftMap[item.id]"
                class="prompt-editor"
                spellcheck="false"
              />

              <div class="prompt-foot">
                <span class="char-count">{{ (draftMap[item.id] || '').length }} 字符</span>
                <button class="btn tiny" @click="resetSlot(item.id)" :disabled="resetting">
                  恢复此模板
                </button>
              </div>
            </article>
          </div>
        </section>
      </template>
    </div>

    <!-- 保存确认弹窗 -->
    <ConfirmDialog
      :is-open="showSaveDialog"
      title="确认保存"
      :confirm-text="hasMissingVarsInDirty ? '仍然保存' : '确认保存'"
      :type="hasMissingVarsInDirty ? 'warning' : 'primary'"
      :loading="saving"
      @confirm="confirmSave"
      @cancel="showSaveDialog = false"
    >
      <p style="margin: 0 0 0.75rem;">即将保存以下模板的改动：</p>
      <ul style="margin: 0; padding-left: 1.2rem; line-height: 1.8;">
        <li v-for="s in saveDialogSummary" :key="s.id">
          <strong>{{ s.name }}</strong>
          <span v-if="s.missing.length" style="color: #b45309; font-size: 0.88rem;">
            &nbsp;— 缺失变量：{{ s.missing.join('、') }}
          </span>
        </li>
      </ul>
      <p v-if="hasMissingVarsInDirty" style="margin: 0.75rem 0 0; color: #b45309; font-size: 0.88rem;">
        部分模板存在缺失变量，运行时对应位置将不会被替换，可能导致输出异常。
      </p>
    </ConfirmDialog>

    <!-- 离开页面确认弹窗 -->
    <ConfirmDialog
      :is-open="showLeaveDialog"
      title="未保存的改动"
      message="当前有未保存的提示词改动，离开后将丢失这些更改。确定要离开吗？"
      confirm-text="离开"
      type="warning"
      @confirm="confirmLeave"
      @cancel="cancelLeave"
    />

    <div v-if="message" class="toast-message">{{ message }}</div>
  </div>
</template>

<style scoped>
.prompt-config-page {
  height: 100%;
  min-height: 0;
  background:
    radial-gradient(circle at top left, rgba(198, 118, 53, 0.12), transparent 28%),
    radial-gradient(circle at 85% 20%, rgba(115, 74, 36, 0.10), transparent 24%),
    linear-gradient(180deg, #f7f1e7 0%, #f9f7f2 42%, #fcfbf8 100%);
  overflow-y: auto;
  overflow-x: hidden;
}

.page-shell {
  max-width: 1180px;
  margin: 0 auto;
  min-height: 100%;
  box-sizing: border-box;
  padding: 2.25rem 2rem 4rem;
}

.page-hero {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 2rem;
  margin-bottom: 1.5rem;
  padding: 1.75rem 1.85rem;
  border-radius: 24px;
  background: linear-gradient(135deg, rgba(255, 250, 242, 0.96), rgba(249, 239, 223, 0.92));
  border: 1px solid rgba(125, 86, 42, 0.14);
  box-shadow: 0 18px 40px rgba(102, 72, 42, 0.08);
}

.hero-kicker {
  margin: 0 0 0.5rem;
  font-size: 0.78rem;
  letter-spacing: 0.16em;
  text-transform: uppercase;
  color: #9b6b3f;
}

.page-hero h1 {
  margin: 0;
  font-size: 2rem;
  font-weight: 800;
  color: #2f2417;
}

.hero-copy {
  max-width: 720px;
  margin: 0.8rem 0 0;
  line-height: 1.75;
  color: #6f5b46;
}

.hero-meta {
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
}

.meta-pill {
  padding: 0.7rem 0.95rem;
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.82);
  border: 1px solid rgba(125, 86, 42, 0.12);
  color: #5c452c;
  font-weight: 600;
  white-space: nowrap;
}

.control-bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 1rem;
  margin-bottom: 1.5rem;
  padding: 1rem 1.1rem;
  border-radius: 18px;
  background: rgba(255, 255, 255, 0.74);
  border: 1px solid rgba(125, 86, 42, 0.12);
  backdrop-filter: blur(8px);
}

.control-copy {
  display: flex;
  align-items: baseline;
  gap: 0.5rem;
  color: #4f3b27;
}

.control-copy strong {
  font-size: 1.4rem;
}

.control-actions {
  display: flex;
  gap: 0.75rem;
}

.btn {
  border: none;
  border-radius: 999px;
  padding: 0.72rem 1.1rem;
  font-weight: 600;
  cursor: pointer;
  transition: transform 0.18s ease, box-shadow 0.18s ease, opacity 0.18s ease;
}

.btn:hover:not(:disabled) {
  transform: translateY(-1px);
}

.btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.btn.solid {
  color: #fff;
  background: linear-gradient(135deg, #9f6430, #7d4a21);
  box-shadow: 0 12px 24px rgba(125, 74, 33, 0.22);
}

.btn.ghost,
.btn.tiny {
  color: #6c5136;
  background: #fff;
  border: 1px solid rgba(125, 86, 42, 0.15);
}

.btn.tiny {
  padding: 0.45rem 0.8rem;
  font-size: 0.82rem;
}

.loading-card,
.group-panel {
  border-radius: 22px;
  background: rgba(255, 255, 255, 0.86);
  border: 1px solid rgba(125, 86, 42, 0.1);
  box-shadow: 0 12px 28px rgba(79, 52, 21, 0.06);
}

.loading-card {
  padding: 2rem;
  color: #6b5b4c;
}

.group-panel {
  margin-bottom: 1.4rem;
  padding: 1.35rem;
}

.group-head {
  margin-bottom: 1rem;
}

.group-head h2 {
  margin: 0;
  font-size: 1.12rem;
  color: #342618;
}

.group-head p {
  margin: 0.4rem 0 0;
  color: #77614b;
}

.prompt-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 1rem;
}

.prompt-card {
  display: flex;
  flex-direction: column;
  min-height: 520px;
  border-radius: 18px;
  padding: 1rem;
  background: linear-gradient(180deg, rgba(255, 251, 246, 0.94), rgba(255, 255, 255, 0.96));
  border: 1px solid rgba(125, 86, 42, 0.1);
}

.prompt-card.dirty {
  border-color: rgba(175, 104, 35, 0.45);
  box-shadow: inset 0 0 0 1px rgba(175, 104, 35, 0.16);
}

.prompt-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 1rem;
  margin-bottom: 0.9rem;
}

.prompt-head h3 {
  margin: 0;
  font-size: 1rem;
  color: #2d2317;
}

.prompt-head p {
  margin: 0.35rem 0 0;
  font-size: 0.9rem;
  line-height: 1.6;
  color: #7c6650;
}

.prompt-badges {
  display: flex;
  flex-direction: column;
  gap: 0.45rem;
}

.badge {
  padding: 0.28rem 0.55rem;
  border-radius: 999px;
  font-size: 0.74rem;
  font-weight: 700;
  text-align: center;
}

.badge-default {
  color: #5d503c;
  background: #f2e8d9;
}

.badge-custom {
  color: #185a55;
  background: #dbf5f1;
}

.badge-dirty {
  color: #8a4d15;
  background: #ffe7cc;
}

.slot-meta {
  display: grid;
  gap: 0.5rem;
  margin-bottom: 0.9rem;
}

.slot-meta-row {
  display: flex;
  align-items: flex-start;
  gap: 0.7rem;
  font-size: 0.84rem;
  color: #6f5943;
}

.slot-label {
  min-width: 2.4rem;
  color: #a08368;
}

.slot-meta code {
  word-break: break-all;
  color: #5f4527;
  background: rgba(124, 90, 52, 0.08);
  padding: 0.15rem 0.35rem;
  border-radius: 6px;
}

.chip-row {
  display: flex;
  flex-wrap: wrap;
  gap: 0.35rem;
}

.chip {
  padding: 0.2rem 0.45rem;
  border-radius: 999px;
  background: #f6efe5;
  color: #7a5f43;
}

.chip-missing {
  background: #fef3c7;
  color: #92400e;
  text-decoration: line-through;
}

.var-warning {
  margin-top: 0.35rem;
  padding: 0.45rem 0.65rem;
  border-radius: 10px;
  background: #fffbeb;
  border: 1px solid #fcd34d;
  color: #92400e;
  font-size: 0.82rem;
  line-height: 1.5;
}

.prompt-editor {
  flex: 1;
  width: 100%;
  min-height: 300px;
  resize: vertical;
  border: 1px solid rgba(125, 86, 42, 0.12);
  border-radius: 14px;
  padding: 1rem;
  background: #fffdf9;
  color: #382919;
  line-height: 1.7;
  font-size: 0.93rem;
  font-family: "SFMono-Regular", Consolas, "Liberation Mono", Menlo, monospace;
  outline: none;
}

.prompt-editor:focus {
  border-color: rgba(159, 100, 48, 0.45);
  box-shadow: 0 0 0 4px rgba(159, 100, 48, 0.09);
}

.prompt-foot {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 1rem;
  margin-top: 0.85rem;
}

.char-count {
  color: #8c7359;
  font-size: 0.82rem;
}

.toast-message {
  position: fixed;
  right: 1.5rem;
  bottom: 1.5rem;
  padding: 0.85rem 1.05rem;
  border-radius: 14px;
  background: rgba(48, 34, 19, 0.94);
  color: #fff;
  box-shadow: 0 16px 32px rgba(0, 0, 0, 0.22);
}

@media (max-width: 980px) {
  .page-shell {
    padding: 1.25rem 1rem 3rem;
  }

  .page-hero,
  .control-bar {
    flex-direction: column;
    align-items: stretch;
  }

  .prompt-grid {
    grid-template-columns: 1fr;
  }
}
</style>
