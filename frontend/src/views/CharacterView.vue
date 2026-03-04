<script setup>
// Copyright (c) 2026 左岚. All rights reserved.
import { ref, onMounted, computed } from 'vue'
import { charactersApi } from '../api'

const categories = ref({})
const loading = ref(true)
const activeTab = ref('实时状态')
const selectedChar = ref(null)
const editContent = ref('')
const saving = ref(false)
const showCreateModal = ref(false)
const newCharName = ref('')
const newCharCategory = ref('次要角色')

const tabs = ['实时状态', '主角卡', '主要角色', '次要角色', '反派角色', '活跃角色表', '宝物库', '功法库', '势力库', '地点库']

const currentList = computed(() => {
    if (activeTab.value === '活跃角色表') {
        return categories.value['活跃角色表'] ? [categories.value['活跃角色表']] : []
    }
    if (activeTab.value === '实时状态') {
        return categories.value['实时状态'] ? [categories.value['实时状态']] : []
    }
    if (activeTab.value === '主角卡') {
        return categories.value['主角卡'] ? [categories.value['主角卡']] : []
    }
    return categories.value[activeTab.value] || []
})

async function loadCharacters() {
    loading.value = true
    try {
        const { data } = await charactersApi.list()
        categories.value = data.categories || {}
    } catch (e) {
        console.error('加载角色列表失败:', e)
    } finally {
        loading.value = false
    }
}

async function selectCharacter(char) {
    try {
        const { data } = await charactersApi.getFile(char.path)
        selectedChar.value = char
        editContent.value = data.content
    } catch (e) {
        console.error('加载角色文件失败:', e)
    }
}

async function saveCharacter() {
    if (!selectedChar.value) return
    saving.value = true
    try {
        await charactersApi.updateFile(selectedChar.value.path, editContent.value)
        alert('保存成功')
    } catch (e) {
        console.error('保存失败:', e)
        alert('保存失败: ' + e.message)
    } finally {
        saving.value = false
    }
}

async function createCharacter() {
    if (!newCharName.value.trim()) {
        alert('请输入角色名')
        return
    }
    try {
        await charactersApi.create(newCharName.value.trim(), newCharCategory.value)
        showCreateModal.value = false
        newCharName.value = ''
        await loadCharacters()
    } catch (e) {
        alert('创建失败: ' + (e.response?.data?.detail || e.message))
    }
}

async function deleteCharacter(char) {
    if (!confirm(`确定删除角色 "${char.name}" 吗？`)) return
    try {
        await charactersApi.delete(char.path)
        if (selectedChar.value?.path === char.path) {
            selectedChar.value = null
            editContent.value = ''
        }
        await loadCharacters()
    } catch (e) {
        alert('删除失败: ' + (e.response?.data?.detail || e.message))
    }
}

onMounted(loadCharacters)
</script>

<template>
    <div class="character-view">
        <header class="page-header">
            <div class="header-left">
                <h1>🌍 世界观管理</h1>
                <p class="subtitle">管理角色、宝物、功法、势力、地点等设定档案</p>
            </div>
            <button class="btn-create" @click="showCreateModal = true">+ 新建角色</button>
        </header>

        <div class="tabs">
            <button 
                v-for="tab in tabs" 
                :key="tab"
                :class="{ active: activeTab === tab }"
                @click="activeTab = tab"
            >
                {{ tab }}
                <span v-if="tab !== '活跃角色表' && tab !== '实时状态' && tab !== '主角卡'" class="count">
                    {{ (categories[tab] || []).length }}
                </span>
            </button>
        </div>

        <div class="content-area">
            <div class="char-list" v-if="!loading">
                <div v-if="currentList.length === 0" class="empty">
                    暂无档案
                </div>
                <div 
                    v-for="char in currentList" 
                    :key="char.path"
                    :class="['char-item', { active: selectedChar?.path === char.path }]"
                    @click="selectCharacter(char)"
                >
                    <span class="char-name">{{ char.name }}</span>
                    <button 
                        v-if="activeTab !== '活跃角色表' && activeTab !== '实时状态' && activeTab !== '主角卡'"
                        class="btn-delete" 
                        @click.stop="deleteCharacter(char)"
                    >×</button>
                </div>
            </div>

            <div class="char-editor" v-if="selectedChar">
                <div class="editor-header">
                    <h3>{{ selectedChar.name }}</h3>
                    <button class="btn-save" @click="saveCharacter" :disabled="saving">
                        {{ saving ? '保存中...' : '💾 保存' }}
                    </button>
                </div>
                <textarea 
                    v-model="editContent"
                    class="editor-content"
                    placeholder="编辑角色档案..."
                ></textarea>
            </div>
            <div v-else class="no-selection">
                <p>👈 请从左侧选择一个档案查看和编辑</p>
            </div>
        </div>

        <!-- 新建角色弹窗 -->
        <div v-if="showCreateModal" class="modal-overlay" @click.self="showCreateModal = false">
            <div class="modal">
                <h3>新建角色</h3>
                <div class="form-group">
                    <label>角色名</label>
                    <input v-model="newCharName" placeholder="输入角色名" />
                </div>
                <div class="form-group">
                    <label>分类</label>
                    <select v-model="newCharCategory">
                        <option value="主要角色">主要角色</option>
                        <option value="次要角色">次要角色</option>
                        <option value="反派角色">反派角色</option>
                    </select>
                </div>
                <div class="modal-actions">
                    <button @click="showCreateModal = false">取消</button>
                    <button class="btn-primary" @click="createCharacter">创建</button>
                </div>
            </div>
        </div>
    </div>
</template>

<style scoped>
.character-view { max-width: 1400px; margin: 0 auto; padding: 2rem; height: calc(100vh - 4rem); display: flex; flex-direction: column; }
.page-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 1.5rem; }
.header-left h1 { font-size: 1.8rem; margin-bottom: 0.3rem; }
.subtitle { color: var(--text-secondary); font-size: 0.9rem; }
.btn-create { background: var(--primary); color: white; border: none; padding: 0.6rem 1.2rem; border-radius: 6px; cursor: pointer; font-size: 0.9rem; }
.btn-create:hover { opacity: 0.9; }

.tabs { display: flex; gap: 0.5rem; border-bottom: 1px solid var(--border-color); padding-bottom: 1rem; margin-bottom: 1rem; }
.tabs button { background: none; border: none; padding: 0.6rem 1rem; cursor: pointer; border-radius: 6px 6px 0 0; color: var(--text-secondary); display: flex; align-items: center; gap: 0.5rem; }
.tabs button.active { background: var(--primary-light); color: var(--primary); font-weight: 600; }
.tabs button:hover { background: var(--bg-secondary); }
.count { background: var(--bg-secondary); padding: 0.1rem 0.5rem; border-radius: 10px; font-size: 0.75rem; }

.content-area { display: flex; gap: 1.5rem; flex: 1; min-height: 0; }
.char-list { width: 250px; background: var(--bg-secondary); border-radius: 8px; padding: 0.5rem; overflow-y: auto; }
.char-item { padding: 0.8rem 1rem; cursor: pointer; border-radius: 6px; display: flex; justify-content: space-between; align-items: center; }
.char-item:hover { background: var(--bg-primary); }
.char-item.active { background: var(--primary-light); color: var(--primary); }
.char-name { font-weight: 500; }
.btn-delete { background: none; border: none; color: var(--text-secondary); cursor: pointer; font-size: 1.2rem; opacity: 0; }
.char-item:hover .btn-delete { opacity: 1; }
.btn-delete:hover { color: #e74c3c; }
.empty { text-align: center; padding: 2rem; color: var(--text-secondary); }

.char-editor { flex: 1; display: flex; flex-direction: column; background: var(--bg-secondary); border-radius: 8px; padding: 1rem; }
.editor-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 1rem; padding-bottom: 1rem; border-bottom: 1px solid var(--border-color); }
.editor-header h3 { margin: 0; }
.btn-save { background: var(--primary); color: white; border: none; padding: 0.5rem 1rem; border-radius: 6px; cursor: pointer; }
.btn-save:disabled { opacity: 0.6; cursor: not-allowed; }
.editor-content { flex: 1; resize: none; padding: 1rem; border: 1px solid var(--border-color); border-radius: 6px; font-family: 'Fira Code', monospace; font-size: 0.9rem; line-height: 1.6; background: var(--bg-primary); }
.no-selection { flex: 1; display: flex; align-items: center; justify-content: center; color: var(--text-secondary); background: var(--bg-secondary); border-radius: 8px; }

.modal-overlay { position: fixed; inset: 0; background: rgba(0,0,0,0.5); display: flex; align-items: center; justify-content: center; z-index: 1000; }
.modal { background: var(--bg-primary); padding: 1.5rem; border-radius: 12px; width: 400px; }
.modal h3 { margin: 0 0 1.5rem; }
.form-group { margin-bottom: 1rem; }
.form-group label { display: block; margin-bottom: 0.5rem; font-weight: 500; }
.form-group input, .form-group select { width: 100%; padding: 0.6rem; border: 1px solid var(--border-color); border-radius: 6px; background: var(--bg-secondary); }
.modal-actions { display: flex; justify-content: flex-end; gap: 0.5rem; margin-top: 1.5rem; }
.modal-actions button { padding: 0.6rem 1.2rem; border-radius: 6px; cursor: pointer; border: 1px solid var(--border-color); background: var(--bg-secondary); }
.btn-primary { background: var(--primary) !important; color: white !important; border: none !important; }
</style>
