<!-- Copyright (c) 2026 左岚. All rights reserved. -->
<script setup>
import { computed, onMounted, onBeforeUnmount, ref } from 'vue'
import { onBeforeRouteLeave } from 'vue-router'
import { projectsApi } from '../api'
import { useProjectStore } from '../stores/project'
import ConfirmDialog from '../components/ConfirmDialog.vue'
import { ChevronDown } from 'lucide-vue-next'

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

// 折叠状态:默认收起,点头部展开;有未保存改动的卡强制展开
const expandedIds = ref(new Set())

function toggleExpand(id) {
  if (isDirty(id)) return
  const next = new Set(expandedIds.value)
  if (next.has(id)) next.delete(id)
  else next.add(id)
  expandedIds.value = next
}

function isExpanded(id) {
  return expandedIds.value.has(id) || isDirty(id)
}

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

// 3d. 推送当前槽位内容到全局子风格包（影响新项目与「恢复默认」）
const showPushDialog = ref(false)
const pushing = ref(false)
const pushTarget = ref(null)

function requestPush(item) {
  if (isDirty(item.id)) {
    showMessage('该模板有未保存改动，请先保存再推送')
    return
  }
  pushTarget.value = item
  showPushDialog.value = true
}

async function confirmPush() {
  if (!pushTarget.value) return
  pushing.value = true
  try {
    const { data } = await projectsApi.pushPromptGlobal(pushTarget.value.id)
    if (data.config) applyPromptConfig(data.config)
    showMessage('✓ 已推送到全局子风格包（原文件已备份）')
  } catch (e) {
    const detail = e?.response?.data?.detail
    showMessage(detail ? `✗ 推送失败：${detail}` : '✗ 推送失败')
  } finally {
    pushing.value = false
    showPushDialog.value = false
    pushTarget.value = null
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
              :class="{ dirty: isDirty(item.id), expanded: isExpanded(item.id) }"
            >
              <div
                class="prompt-head"
                role="button"
                :aria-expanded="isExpanded(item.id)"
                @click="toggleExpand(item.id)"
              >
                <div>
                  <h3>{{ item.name }}</h3>
                  <p>{{ item.description }}</p>
                </div>
                <div class="prompt-head-right">
                  <div class="prompt-badges">
                    <span class="badge" :class="item.customized ? 'badge-custom' : 'badge-default'">
                      {{ item.customized ? '已自定义' : '默认快照' }}
                    </span>
                    <span v-if="isDirty(item.id)" class="badge badge-dirty">未保存</span>
                  </div>
                  <ChevronDown :size="15" :stroke-width="1.75" class="expand-chevron" :class="{ open: isExpanded(item.id) }" />
                </div>
              </div>

              <template v-if="isExpanded(item.id)">
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
                <div class="foot-actions">
                  <button
                    class="btn tiny"
                    @click="requestPush(item)"
                    :disabled="pushing || isDirty(item.id)"
                    :title="isDirty(item.id) ? '有未保存改动，请先保存' : '把当前内容设为该子风格的全局默认模板'"
                  >
                    保存到全局子风格包
                  </button>
                  <button class="btn tiny" @click="resetSlot(item.id)" :disabled="resetting">
                    恢复此模板
                  </button>
                </div>
              </div>
              </template>
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
          <span v-if="s.missing.length" style="color: var(--warning-strong); font-size: 0.88rem;">
            &nbsp;— 缺失变量：{{ s.missing.join('、') }}
          </span>
        </li>
      </ul>
      <p v-if="hasMissingVarsInDirty" style="margin: 0.75rem 0 0; color: var(--warning-strong); font-size: 0.88rem;">
        部分模板存在缺失变量，运行时对应位置将不会被替换，可能导致输出异常。
      </p>
    </ConfirmDialog>

    <!-- 推送到全局包确认弹窗 -->
    <ConfirmDialog
      :is-open="showPushDialog"
      title="推送到全局子风格包"
      confirm-text="确认推送"
      type="warning"
      :loading="pushing"
      @confirm="confirmPush"
      @cancel="showPushDialog = false"
    >
      <p style="margin: 0 0 0.5rem;">
        将把 <strong>{{ pushTarget?.name }}</strong> 的当前内容写入全局子风格包
        （{{ promptConfig.genre }} / {{ promptConfig.substyle || '默认' }}）：
      </p>
      <p style="margin: 0 0 0.75rem;">
        <code style="word-break: break-all; font-size: 0.8rem;">{{ pushTarget?.source_path || '按当前题材推导' }}</code>
      </p>
      <p style="margin: 0; font-size: 0.88rem; color: var(--ink-secondary);">
        只影响之后新建的项目与「恢复默认/题材切换」，不会改动其他现有项目的快照；原全局文件会自动备份为 .bak。
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
  overflow-y: auto;
  overflow-x: hidden;
}

.page-shell {
  max-width: 1180px;
  margin: 0 auto;
  min-height: 100%;
  box-sizing: border-box;
  padding: 1.5rem 2rem 4rem;
}

.page-hero {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 2rem;
  margin-bottom: 1.25rem;
  padding-bottom: 1.25rem;
  border-bottom: 1px solid var(--border);
}

.hero-kicker {
  margin: 0 0 0.375rem;
  font-size: 0.75rem;
  font-weight: 500;
  color: var(--ink-muted);
}

.page-hero h1 {
  margin: 0;
  font-size: 1.375rem;
  font-weight: 600;
  color: var(--ink-primary);
  letter-spacing: -0.01em;
}

.hero-copy {
  max-width: 720px;
  margin: 0.6rem 0 0;
  line-height: 1.7;
  color: var(--ink-secondary);
  font-size: 0.9375rem;
}

.hero-meta {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}

.meta-pill {
  padding: 0.5rem 0.8rem;
  border-radius: var(--radius-md);
  background: var(--surface);
  border: 1px solid var(--border);
  color: var(--ink-secondary);
  font-weight: 500;
  font-size: 0.8125rem;
  white-space: nowrap;
}

.control-bar {
  position: sticky;
  top: 0.75rem;
  z-index: var(--z-sticky);
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 1rem;
  margin-bottom: 1.25rem;
  padding: 0.875rem 1rem;
  border-radius: var(--radius-lg);
  background: var(--surface);
  border: 1px solid var(--border);
  box-shadow: var(--shadow-sm);
}

.control-copy {
  display: flex;
  align-items: baseline;
  gap: 0.5rem;
  color: var(--ink-secondary);
  font-size: 0.875rem;
}

.control-copy strong {
  font-size: 1.25rem;
  color: var(--ink-primary);
  font-family: var(--font-mono);
  font-feature-settings: "tnum";
}

.control-actions {
  display: flex;
  gap: 0.625rem;
}

.btn {
  border: 1px solid transparent;
  border-radius: var(--radius-md);
  padding: 0.5rem 1rem;
  font-weight: 500;
  font-size: 0.875rem;
  cursor: pointer;
  transition: background-color var(--dur-fast) var(--ease-standard), border-color var(--dur-fast) var(--ease-standard), color var(--dur-fast) var(--ease-standard);
}

.btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.btn.solid {
  color: var(--on-primary);
  background: var(--primary);
  border-color: var(--primary);
}

.btn.solid:hover:not(:disabled) {
  background: var(--primary-hover);
  border-color: var(--primary-hover);
}

.btn.ghost,
.btn.tiny {
  color: var(--ink-secondary);
  background: var(--card);
  border: 1px solid var(--border);
}

.btn.ghost:hover:not(:disabled),
.btn.tiny:hover:not(:disabled) {
  background: var(--surface);
  border-color: var(--border-strong);
  color: var(--ink-primary);
}

.btn.tiny {
  padding: 0.4rem 0.75rem;
  font-size: 0.8125rem;
}

.loading-card,
.group-panel {
  border-radius: var(--radius-lg);
  background: var(--card);
  border: 1px solid var(--border);
}

.loading-card {
  padding: 2rem;
  color: var(--ink-muted);
}

.group-panel {
  margin-bottom: 1rem;
  padding: 1.25rem;
}

.group-head {
  margin-bottom: 1rem;
}

.group-head h2 {
  margin: 0;
  font-size: 1.0625rem;
  font-weight: 600;
  color: var(--ink-primary);
}

.group-head p {
  margin: 0.4rem 0 0;
  color: var(--ink-secondary);
  font-size: 0.875rem;
}

.prompt-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 0.875rem;
}

.prompt-card {
  display: flex;
  flex-direction: column;
  border-radius: var(--radius-lg);
  padding: 1rem;
  background: var(--surface);
  border: 1px solid transparent;
  transition: border-color var(--dur-fast) var(--ease-standard);
}

.prompt-card.expanded {
  min-height: 520px;
}

.prompt-card:not(.expanded):hover {
  border-color: var(--border-strong);
}

.prompt-card.dirty {
  border-color: var(--warning);
}

.prompt-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 1rem;
  cursor: pointer;
  user-select: none;
}

.prompt-card.expanded .prompt-head {
  margin-bottom: 0.875rem;
}

.prompt-card.dirty .prompt-head {
  cursor: default;
}

.prompt-head-right {
  display: flex;
  align-items: flex-start;
  gap: 0.55rem;
  flex-shrink: 0;
}

.expand-chevron {
  color: var(--ink-muted);
  margin-top: 0.2rem;
  transition: transform var(--dur-fast) var(--ease-standard);
  flex-shrink: 0;
}

.expand-chevron.open {
  transform: rotate(180deg);
}

.prompt-card.dirty .expand-chevron {
  opacity: 0.35;
}

.prompt-head h3 {
  margin: 0;
  font-size: 0.9375rem;
  font-weight: 600;
  color: var(--ink-primary);
}

.prompt-head p {
  margin: 0.35rem 0 0;
  font-size: 0.8125rem;
  line-height: 1.6;
  color: var(--ink-secondary);
}

.prompt-badges {
  display: flex;
  flex-direction: column;
  gap: 0.4rem;
}

.badge {
  padding: 0.25rem 0.55rem;
  border-radius: var(--radius-sm);
  font-size: 0.75rem;
  font-weight: 500;
  text-align: center;
}

.badge-default {
  color: var(--ink-secondary);
  background: var(--card);
  border: 1px solid var(--border);
}

.badge-custom {
  color: var(--success);
  background: var(--success-tint);
}

.badge-dirty {
  color: var(--warning-strong);
  background: var(--warning-tint);
}

.slot-meta {
  display: grid;
  gap: 0.5rem;
  margin-bottom: 0.875rem;
}

.slot-meta-row {
  display: flex;
  align-items: flex-start;
  gap: 0.7rem;
  font-size: 0.8125rem;
  color: var(--ink-secondary);
}

.slot-label {
  min-width: 2.4rem;
  color: var(--ink-muted);
}

.slot-meta code {
  word-break: break-all;
  color: var(--ink-primary);
  background: var(--hover);
  padding: 0.15rem 0.35rem;
  border-radius: var(--radius-sm);
  font-family: var(--font-mono);
  font-size: 0.75rem;
}

.chip-row {
  display: flex;
  flex-wrap: wrap;
  gap: 0.35rem;
}

.chip {
  padding: 0.2rem 0.45rem;
  border-radius: var(--radius-sm);
  background: var(--card);
  border: 1px solid var(--border);
  color: var(--ink-secondary);
  font-family: var(--font-mono);
  font-size: 0.75rem;
}

.chip-missing {
  background: var(--warning-tint);
  border-color: transparent;
  color: var(--warning-strong);
  text-decoration: line-through;
}

.var-warning {
  margin-top: 0.35rem;
  padding: 0.45rem 0.65rem;
  border-radius: var(--radius-md);
  background: var(--warning-tint);
  border: 1px solid transparent;
  color: var(--warning-strong);
  font-size: 0.8125rem;
  line-height: 1.5;
}

.prompt-editor {
  flex: 1;
  width: 100%;
  min-height: 300px;
  resize: vertical;
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  padding: 1rem;
  background: var(--card);
  color: var(--ink-primary);
  line-height: 1.7;
  font-size: 0.875rem;
  font-family: var(--font-mono);
  outline: none;
  transition: border-color var(--dur-fast) var(--ease-standard), box-shadow var(--dur-fast) var(--ease-standard);
}

.prompt-editor:focus {
  border-color: var(--primary);
  box-shadow: 0 0 0 3px var(--primary-tint);
}

.prompt-foot {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 1rem;
  margin-top: 0.85rem;
}

.foot-actions {
  display: flex;
  gap: 0.5rem;
}

.char-count {
  color: var(--ink-muted);
  font-size: 0.8125rem;
  font-family: var(--font-mono);
  font-feature-settings: "tnum";
}

.toast-message {
  position: fixed;
  right: 1.5rem;
  bottom: 1.5rem;
  padding: 0.75rem 1.1rem;
  border-radius: var(--radius-md);
  background: var(--ink-primary);
  color: var(--bg);
  box-shadow: var(--shadow-lg);
  z-index: var(--z-toast);
  font-size: 0.875rem;
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
