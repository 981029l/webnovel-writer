<!-- Copyright (c) 2026 左岚. All rights reserved. -->
<!-- AiConfigModal.vue - 全局 AI 服务配置弹窗（首页/项目页共用） -->
<script setup>
import { ref, onMounted } from 'vue'
import { aiApi } from '../api'
import SearchSelect from './SearchSelect.vue'

const emit = defineEmits(['close'])

const aiConfig = ref({ base_url: '', api_key: '', model: '' })
const agentMode = ref(true)
const aiModels = ref([])
const aiModelsLoading = ref(false)
const saving = ref(false)
const message = ref('')

const apiBaseUrls = [
  'https://api.openai.com', 'https://api.deepseek.com', 'https://api.moonshot.cn', 'https://api-inference.modelscope.cn/compatible-mode/v1',
  'https://api.x.ai/v1', 'https://generativelanguage.googleapis.com/v1beta/openai', 'http://localhost:8000', 'http://127.0.0.1:8317', 'http://localhost:8317'
]

function showMessage(text, duration = 3000) {
  message.value = text
  setTimeout(() => { if (message.value === text) message.value = '' }, duration)
}

async function loadAiConfig() {
  try {
    const { data } = await aiApi.getConfig()
    aiConfig.value = {
      base_url: data.base_url,
      model: data.model,
      api_key: data.has_api_key ? '******' : ''
    }
    agentMode.value = data.agent_mode !== false
  } catch (e) { console.error(e) }
}

async function toggleAgentMode() {
  const next = !agentMode.value
  try {
    await aiApi.setAgentMode(next)
    agentMode.value = next
    showMessage(next ? '✓ 写手 Agent 模式已开启' : '已切换为标准模式')
  } catch (e) {
    showMessage('✗ 切换失败：' + e.message)
  }
}

async function loadModels() {
  if (!aiConfig.value.base_url) return
  aiModelsLoading.value = true
  try {
    const configToUpdate = { ...aiConfig.value }
    if (configToUpdate.api_key === '******') delete configToUpdate.api_key
    await aiApi.updateConfig(configToUpdate)
    const { data } = await aiApi.getModels()
    if (data.success) aiModels.value = data.models
  } catch (e) { console.error('Failed to load models:', e) }
  finally { aiModelsLoading.value = false }
}

async function saveAiConfig() {
  saving.value = true
  try {
    const configToUpdate = { ...aiConfig.value }
    if (configToUpdate.api_key === '******') delete configToUpdate.api_key
    await aiApi.updateConfig(configToUpdate)
    showMessage('✓ AI 配置已保存')
    setTimeout(() => emit('close'), 600)
  } catch (e) { showMessage('✗ 保存失败：' + e.message) }
  finally { saving.value = false }
}

onMounted(loadAiConfig)
</script>

<template>
  <div class="modal-overlay" @click.self="emit('close')">
    <div class="modal">
      <button class="close-btn" @click="emit('close')" aria-label="关闭">
        <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor" class="size-5">
          <path stroke-linecap="round" stroke-linejoin="round" d="M6 18 18 6M6 6l12 12" />
        </svg>
      </button>

      <div class="modal-header">
        <div class="header-icon">
          <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor" class="size-6">
            <path stroke-linecap="round" stroke-linejoin="round" d="M9.594 3.94c.09-.542.56-.94 1.11-.94h2.593c.55 0 1.02.398 1.11.94l.213 1.281c.063.374.313.686.645.87.074.04.147.083.22.127.324.196.72.257 1.075.124l1.217-.456a1.125 1.125 0 0 1 1.37.49l1.296 2.247a1.125 1.125 0 0 1-.26 1.431l-1.003.827c-.293.241-.438.613-.43.992a7.723 7.723 0 0 1 0 .255c-.008.378.137.75.43.991l1.004.827c.424.35.534.955.26 1.43l-1.298 2.247a1.125 1.125 0 0 1-1.369.491l-1.217-.456c-.355-.133-.75-.072-1.076.124a6.47 6.47 0 0 1-.22.128c-.331.183-.581.495-.644.869l-.213 1.281c-.09.543-.56.94-1.11.94h-2.594c-.55 0-1.019-.398-1.11-.94l-.213-1.281c-.062-.374-.312-.686-.644-.87a6.52 6.52 0 0 1-.22-.127c-.325-.196-.72-.257-1.076-.124l-1.217.456a1.125 1.125 0 0 1-1.369-.49l-1.297-2.247a1.125 1.125 0 0 1 .26-1.431l1.004-.827c.292-.241.437-.613.43-.992a7.723 7.723 0 0 1 0-.255c.007-.378-.138-.75-.43-.991l-1.004-.827a1.125 1.125 0 0 1-.26-1.43l1.297-2.247a1.125 1.125 0 0 1 1.37-.491l1.216.456c.356.133.751.072 1.076-.124.072-.044.146-.086.22-.128.332-.183.582-.495.644-.869l.214-1.28Z" />
            <path stroke-linecap="round" stroke-linejoin="round" d="M15 12a3 3 0 1 1-6 0 3 3 0 0 1 6 0Z" />
          </svg>
        </div>
        <div class="header-text">
          <h3>AI 服务配置</h3>
          <p class="modal-desc">配置一次即可对所有小说生效，用于 AI 初始化、大纲规划、正文创作等。</p>
        </div>
      </div>

      <div class="form-group">
        <label>API Base URL</label>
        <SearchSelect
          v-model="aiConfig.base_url"
          :options="apiBaseUrls"
          placeholder="输入或选择 API 地址..."
        />
      </div>
      <div class="form-group">
        <label>API Key</label>
        <input v-model="aiConfig.api_key" type="password" class="input" placeholder="sk-..." />
      </div>
      <div class="form-group">
        <label>Model Name</label>
        <div class="model-row">
          <SearchSelect
            v-model="aiConfig.model"
            :options="aiModels"
            class="flex-1"
            placeholder="选择或输入模型..."
            :loading="aiModelsLoading"
            @refresh="loadModels"
          />
          <button class="btn btn-secondary" @click="loadModels" :disabled="!aiConfig.base_url">
            刷新模型
          </button>
        </div>
      </div>

      <div class="form-group">
        <div class="agent-mode-row">
          <div class="agent-mode-text">
            <label>写手 Agent 模式</label>
            <p class="agent-mode-desc">开启后，AI 写作前会自主查阅设定集、前文伏笔与角色档案，长篇连贯性更好（每章耗时和 token 略增；模型需支持工具调用，不支持时自动回落标准模式）</p>
          </div>
          <button
            class="toggle"
            :class="{ on: agentMode }"
            role="switch"
            :aria-checked="agentMode"
            @click="toggleAgentMode"
          >
            <span class="toggle-knob"></span>
          </button>
        </div>
      </div>

      <div class="modal-actions">
        <button class="btn btn-secondary" @click="emit('close')">取消</button>
        <button class="btn btn-primary" @click="saveAiConfig" :disabled="saving">
          {{ saving ? '保存中...' : '保存配置' }}
        </button>
      </div>

      <div v-if="message" class="modal-toast">{{ message }}</div>
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
  padding: 1.5rem;
  animation: fadeIn var(--dur-fast) ease-out;
}

@keyframes fadeIn {
  from { opacity: 0; }
  to { opacity: 1; }
}

.modal {
  background: var(--card);
  border-radius: var(--radius-lg);
  padding: 1.5rem;
  width: 100%;
  max-width: 520px;
  box-shadow: var(--shadow-xl);
  border: 1px solid var(--border);
  animation: scaleIn var(--dur-base) var(--ease-emerge);
  position: relative;
  overflow: hidden;
}

@keyframes scaleIn {
  from { opacity: 0; transform: scale(0.98); }
  to { opacity: 1; transform: scale(1); }
}

.modal-header {
  display: flex;
  align-items: flex-start;
  gap: 1rem;
  margin-bottom: 1.5rem;
}

.header-icon {
  flex-shrink: 0;
  width: 2.5rem;
  height: 2.5rem;
  border-radius: var(--radius-md);
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--primary-on-tint);
  background: var(--primary-tint);
}

.header-text {
  flex: 1;
  min-width: 0;
  padding-top: 0.125rem;
}

.modal h3 {
  margin: 0;
  font-size: 1.125rem;
  font-weight: 600;
  color: var(--ink-primary);
}

.modal-desc {
  font-size: 0.8125rem;
  color: var(--ink-muted);
  margin: 0.375rem 0 0;
  line-height: 1.5;
}

.close-btn {
  position: absolute;
  top: 1.25rem;
  right: 1.25rem;
  background: none;
  border: none;
  color: var(--ink-muted);
  cursor: pointer;
  padding: 0.375rem;
  border-radius: var(--radius-sm);
  display: flex;
  align-items: center;
  justify-content: center;
  transition: background-color var(--dur-fast) var(--ease-standard), color var(--dur-fast) var(--ease-standard);
  z-index: 1;
}

.close-btn:hover {
  background: var(--hover);
  color: var(--ink-primary);
}

.form-group {
  margin-bottom: 1.25rem;
}

.form-group label {
  display: block;
  margin-bottom: 0.5rem;
  font-weight: 500;
  font-size: 0.875rem;
  color: var(--ink-secondary);
}

.input {
  width: 100%;
  padding: 0.6rem 0.85rem;
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  font-size: 0.875rem;
  color: var(--ink-primary);
  background: var(--surface);
  transition: border-color var(--dur-fast) var(--ease-standard), box-shadow var(--dur-fast) var(--ease-standard), background-color var(--dur-fast) var(--ease-standard);
  box-sizing: border-box;
}

.input::placeholder {
  color: var(--ink-muted);
}

.input:hover {
  border-color: var(--border-strong);
}

.input:focus {
  outline: none;
  border-color: var(--primary);
  background: var(--card);
  box-shadow: 0 0 0 3px var(--primary-tint);
}

.model-row {
  display: flex;
  gap: 0.75rem;
  align-items: center;
}

.model-row .flex-1 { flex: 1; }

.model-row .btn {
  white-space: nowrap;
  flex-shrink: 0;
}

.modal-actions {
  display: flex;
  justify-content: flex-end;
  gap: 0.625rem;
  margin-top: 1.75rem;
  padding-top: 1.25rem;
  border-top: 1px solid var(--border);
}

.modal-actions .btn {
  padding: 0.55rem 1.2rem;
}

.modal-toast {
  position: absolute;
  bottom: 5.75rem;
  left: 50%;
  transform: translateX(-50%);
  background: var(--ink-primary);
  color: var(--bg);
  padding: 0.5rem 1.25rem;
  border-radius: var(--radius-md);
  font-size: 0.8125rem;
  font-weight: 500;
  white-space: nowrap;
  box-shadow: var(--shadow-lg);
  animation: toastIn 0.3s var(--ease-emerge);
}

@keyframes toastIn {
  from { opacity: 0; transform: translateX(-50%) translateY(8px); }
  to { opacity: 1; transform: translateX(-50%) translateY(0); }
}

/* 写手 Agent 模式开关 */
.agent-mode-row {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 1rem;
  padding: 0.875rem 1rem;
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
}

.agent-mode-text label {
  margin-bottom: 0.25rem;
}

.agent-mode-desc {
  margin: 0;
  font-size: 0.75rem;
  line-height: 1.5;
  color: var(--ink-muted);
}

.toggle {
  flex-shrink: 0;
  width: 2.75rem;
  height: 1.5rem;
  border-radius: var(--radius-pill);
  border: none;
  background: var(--border-strong);
  cursor: pointer;
  position: relative;
  transition: background-color var(--dur-fast) var(--ease-standard);
  margin-top: 0.125rem;
}

.toggle.on {
  background: var(--primary);
}

.toggle-knob {
  position: absolute;
  top: 0.1875rem;
  left: 0.1875rem;
  width: 1.125rem;
  height: 1.125rem;
  border-radius: 50%;
  background: #fff;
  transition: transform var(--dur-fast) var(--ease-standard);
  box-shadow: 0 1px 3px rgb(15 17 21 / 0.2);
}

.toggle.on .toggle-knob {
  transform: translateX(1.25rem);
}
</style>
