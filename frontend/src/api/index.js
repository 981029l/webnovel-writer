// Copyright (c) 2026 左岚. All rights reserved.
// API 封装模块

import axios from 'axios'

const api = axios.create({
    baseURL: 'http://localhost:8080/api',
    timeout: 600000, // 10分钟超时，支持 AI 长时间请求
    headers: {
        'Content-Type': 'application/json'
    }
})

// 项目管理 API
export const projectsApi = {
    getStatus: () => api.get('/projects/status'),
    getConfig: () => api.get('/projects/config'),
    getSettings: () => api.get('/projects/settings'),
    updateConfig: (config) => api.put('/projects/config', config),
    init: (data) => api.post('/projects/init', data),
    getGenres: () => api.get('/projects/genres'),
    reset: () => api.delete('/projects/reset'),
    getActivities: () => api.get('/projects/activities'),
    // 多项目管理
    list: () => api.get('/projects/list'),
    create: (data) => api.post('/projects/create', data),
    switch: (path) => api.post('/projects/switch', { path }),
    import: (path) => api.post('/projects/import', { path }),
    delete: (projectId, deleteFiles = false) => api.delete(`/projects/${projectId}?delete_files=${deleteFiles}`)
}

// 大纲管理 API
export const outlinesApi = {
    getAll: () => api.get('/outlines'),
    getVolume: (volume) => api.get(`/outlines/${volume}`),
    updateVolume: (volume, content) => api.put(`/outlines/${volume}`, { content }),
    updateTotal: (content) => api.put('/outlines/total', { content }),
    deleteVolume: (volume, deleteRelatedCharacters = false) => api.delete(`/outlines/${volume}`, {
        params: { delete_related_characters: deleteRelatedCharacters }
    }),
    getTree: () => api.get('/outlines/tree')
}

// 章节管理 API
export const chaptersApi = {
    getAll: () => api.get('/chapters'),
    get: (id) => api.get(`/chapters/${id}`),
    update: (id, data) => api.put(`/chapters/${id}`, data),
    delete: (id) => api.delete(`/chapters/${id}`),
    write: (data) => api.post('/chapters/write', data),
    review: (chapters) => api.post('/chapters/review', { chapters }),
    getStats: () => api.get('/chapters/stats'),
    getTaskStatus: (taskId) => api.get(`/chapters/tasks/${taskId}`),
    ackTask: (taskId) => api.delete(`/chapters/tasks/${taskId}`),
    forceExtract: (id) => api.post(`/chapters/${id}/extract`),
    extractPreview: (id, content) => api.post(`/chapters/${id}/extract-preview`, { content }),
    extractApply: (id, extraction, content) => api.post(`/chapters/${id}/extract-apply`, { extraction, content }),
}

// 实体管理 API
export const entitiesApi = {
    getAll: (params) => api.get('/entities', { params }),
    get: (id) => api.get(`/entities/${id}`),
    getByType: (type) => api.get(`/entities/type/${type}`),
    search: (q) => api.get('/entities/search', { params: { q } }),
    getTypes: () => api.get('/entities/types'),
    getTiers: () => api.get('/entities/tiers'),
    getProtagonist: () => api.get('/entities/protagonist'),
    getCharacters: () => api.get('/entities/characters'),
    getForeshadowing: (status) => api.get('/entities/foreshadowing', { params: { status } })
}

// RAG 检索 API
export const ragApi = {
    search: (query, mode = 'hybrid', topK = 10) => api.post('/rag/search', { query, mode, top_k: topK }),
    getStats: () => api.get('/rag/stats'),
    test: (query) => api.get('/rag/test', { params: { query } }),
    rebuildIndex: () => api.post('/rag/index/all')
}

// Helper for stream requests
function getAuthHeaders() {
    const headers = { 'Content-Type': 'application/json' }
    if (api.defaults.headers.common['X-Project-Root']) {
        headers['X-Project-Root'] = api.defaults.headers.common['X-Project-Root']
    }
    return headers
}

// AI 写作 API
export const aiApi = {
    getConfig: () => api.get('/ai/config'),
    updateConfig: (config) => api.put('/ai/config', config),
    testConnection: () => api.get('/ai/test'),
    getModels: () => api.get('/ai/models'),
    getGenres: () => api.get('/ai/genres'),
    initProject: (data) => api.post('/ai/init', data),
    initProjectStream: (data) => fetch(`${api.defaults.baseURL}/ai/init-stream`, {
        method: 'POST',
        headers: getAuthHeaders(),
        body: JSON.stringify(data)
    }),
    buildContext: (chapter) => api.post('/ai/context', null, { params: { chapter } }),
    writeChapter: (chapter, wordCount = 3500) => api.post('/ai/write', { chapter, word_count: wordCount }),
    writeChapterStream: (chapter, wordCount = 3500) => fetch(`${api.defaults.baseURL}/ai/write-stream`, {
        method: 'POST',
        headers: getAuthHeaders(),
        body: JSON.stringify({ chapter, word_count: wordCount })
    }),
    reviewChapter: (chapter) => api.post('/ai/review', null, { params: { chapter } }),
    planVolume: (volume, chaptersCount = 30, guidance = "") => api.post('/ai/plan', { volume, chapters_count: chaptersCount, guidance }),
    planVolumeStream: (volume, chaptersCount = 30, guidance = "") => fetch(`${api.defaults.baseURL}/ai/plan-stream`, {
        method: 'POST',
        headers: getAuthHeaders(),
        body: JSON.stringify({ volume, chapters_count: chaptersCount, guidance })
    }),
    polishOutlineStream: (volume, content, requirements) => fetch(`${api.defaults.baseURL}/ai/polish-outline-stream`, {
        method: 'POST',
        headers: getAuthHeaders(),
        body: JSON.stringify({ volume, content, requirements })
    }),

    polishChapterStream: (chapterId, content, suggestions) => fetch(`${api.defaults.baseURL}/ai/polish-stream`, {
        method: 'POST',
        headers: getAuthHeaders(),
        body: JSON.stringify({ chapter_id: chapterId, content, suggestions })
    }),
    polishChapter: (chapterId, content, suggestions) => api.post('/ai/polish', { chapter_id: chapterId, content, suggestions }),
    generateSynopsis: () => api.post('/ai/generate-synopsis'),
    generateTitles: () => api.post('/ai/generate-titles'),
    updateProjectInfo: (data) => api.put('/projects/info', data),
    generateEndingPlan: (remainingChapters) => api.post('/ai/ending-plan', { remaining_chapters: remainingChapters })
}

// 角色管理 API
export const charactersApi = {
    list: () => api.get('/characters'),
    getFile: (path) => api.get('/characters/file', { params: { path } }),
    updateFile: (path, content) => api.put('/characters/file', { content }, { params: { path } }),
    create: (name, category) => api.post('/characters/create', null, { params: { name, category } }),
    delete: (path) => api.delete('/characters/file', { params: { path } }),
    getRelationships: () => api.get('/characters/relationships'),
    getProfile: (name) => api.get('/characters/profile', { params: { name } })
}

export default api
