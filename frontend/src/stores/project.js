// Copyright (c) 2026 左岚. All rights reserved.
// Pinia 状态管理 - 项目状态

import { defineStore } from 'pinia'
import api, { projectsApi, chaptersApi } from '../api'

const setAuthHeader = (path) => {
    if (path) {
        // ENCODE path to avoid Latin1/Chinese header errors
        api.defaults.headers.common['X-Project-Root'] = encodeURIComponent(path)
    } else {
        delete api.defaults.headers.common['X-Project-Root']
    }
}

export const useProjectStore = defineStore('project', {
    state: () => {
        const root = sessionStorage.getItem('webnovel_project_root') || ''
        if (root) setAuthHeader(root)
        return {
            initialized: false,
            projectRoot: root,
            currentChapter: 0,
            totalChapters: 0,
            totalWords: 0,
            targetWords: null,
            protagonist: null,
            genre: null,
            title: null,
            description: null,
            status: '连载中',
            activities: [],
            loading: false,
            error: null
        }
    },

    actions: {
        async setCurrentProject(path) {
            this.projectRoot = path
            sessionStorage.setItem('webnovel_project_root', path)
            setAuthHeader(path)

            // Still notify backend for global history/recent list, but frontend context is now local
            try {
                await projectsApi.switch(path)
            } catch (e) {
                console.warn('Switch project backend notification failed', e)
            }

            // Reactively fetch project status after switching — no more window.location.reload()
            await this.fetchStatus()
        },

        clearProject() {
            this.projectRoot = ''
            this.initialized = false
            this.currentChapter = 0
            this.totalChapters = 0
            this.totalWords = 0
            this.targetWords = null
            this.protagonist = null
            this.genre = null
            this.title = null
            this.description = null
            this.status = '连载中'
            this.activities = []
            this.loading = false
            this.error = null
            sessionStorage.removeItem('webnovel_project_root')
            delete api.defaults.headers.common['X-Project-Root']
        },

        async fetchStatus() {
            this.loading = true
            this.error = null
            try {
                const { data } = await projectsApi.getStatus()
                this.initialized = data.initialized

                // Sync normalized path from backend if needed
                if (data.project_root && data.project_root !== this.projectRoot) {
                    this.projectRoot = data.project_root
                    sessionStorage.setItem('webnovel_project_root', this.projectRoot)
                    setAuthHeader(this.projectRoot)
                }

                this.currentChapter = data.current_chapter
                this.totalChapters = data.total_chapters
                this.totalWords = data.total_words
                this.targetWords = data.target_words // 从 API 读取目标字数
                this.protagonist = data.protagonist
                this.genre = data.genre
                this.title = data.title // 从 API 读取标题
                this.description = data.description
                this.status = data.status || '连载中' // 从 API 读取状态

                // 同时获取活动记录
                await this.fetchActivities()
            } catch (e) {
                this.error = e.message
            } finally {
                this.loading = false
            }
        },

        async fetchActivities() {
            try {
                const { data } = await projectsApi.getActivities()
                this.activities = data.activities || []
            } catch (e) {
                console.error('Failed to fetch activities:', e)
            }
        },

        async initProject(genre, mode = 'standard') {
            this.loading = true
            try {
                await projectsApi.init({ genre, mode })
                await this.fetchStatus()
                return true
            } catch (e) {
                this.error = e.message
                return false
            } finally {
                this.loading = false
            }
        },

        async refreshStats() {
            try {
                const { data } = await chaptersApi.getStats()
                this.totalChapters = data.total_chapters
                this.totalWords = data.total_words
            } catch (e) {
                console.error('Failed to refresh stats:', e)
            }
        }
    }
})
