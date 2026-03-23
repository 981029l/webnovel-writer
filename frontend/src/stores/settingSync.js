// Copyright (c) 2026 左岚. All rights reserved.
// 章节设定同步后台任务管理

import { defineStore } from 'pinia'
import { ref } from 'vue'
import { chaptersApi } from '../api'
import { useAiTaskStore } from './aiTask'

let pollTimer = null

function clearPollTimer() {
    if (pollTimer) {
        clearTimeout(pollTimer)
        pollTimer = null
    }
}

function getErrorMessage(error) {
    return error?.response?.data?.detail || error?.message || '未知错误'
}

function isExtractionEmpty(extraction) {
    if (!extraction || typeof extraction !== 'object') return true

    const listKeys = [
        'new_characters',
        'new_treasures',
        'new_techniques',
        'new_organizations',
        'new_locations',
        'status_changes',
        'entity_events',
        'exits',
    ]

    const hasListChanges = listKeys.some(key => Array.isArray(extraction[key]) && extraction[key].length > 0)
    const statusFileUpdates = extraction.status_file_updates
    const hasStatusFileUpdates = !!(
        statusFileUpdates &&
        typeof statusFileUpdates === 'object' &&
        Object.keys(statusFileUpdates).length > 0
    )

    return !hasListChanges && !hasStatusFileUpdates
}

export const useSettingSyncStore = defineStore('settingSync', () => {
    const isRunning = ref(false)
    const chapterId = ref(null)
    const backendTaskId = ref('')
    const contentSnapshot = ref('')
    let activePromise = null
    let resolveActivePromise = null
    let rejectActivePromise = null

    function settleActivePromise(error = null, result = null) {
        if (error) {
            rejectActivePromise?.(error)
        } else {
            resolveActivePromise?.(result)
        }
        activePromise = null
        resolveActivePromise = null
        rejectActivePromise = null
    }

    function resetState() {
        clearPollTimer()
        isRunning.value = false
        chapterId.value = null
        backendTaskId.value = ''
        contentSnapshot.value = ''
    }

    async function finishWithError(message) {
        const aiTaskStore = useAiTaskStore()
        if (backendTaskId.value) {
            await chaptersApi.ackTask(backendTaskId.value).catch(() => {})
        }
        aiTaskStore.failTask(message)
        settleActivePromise(new Error(message))
        resetState()
    }

    async function pollStatus() {
        if (!backendTaskId.value || !chapterId.value) return

        const aiTaskStore = useAiTaskStore()

        try {
            const { data: status } = await chaptersApi.getTaskStatus(backendTaskId.value)

            if (status.status === 'running') {
                aiTaskStore.updateTaskDetail(status.message || `第 ${chapterId.value} 章：正在分析设定`)
                pollTimer = setTimeout(pollStatus, 1500)
                return
            }

            await chaptersApi.ackTask(backendTaskId.value).catch(() => {})

            if (status.status === 'completed') {
                const extraction = status.result?.extraction && typeof status.result.extraction === 'object'
                    ? status.result.extraction
                    : {}
                const emptyExtraction = isExtractionEmpty(extraction)

                aiTaskStore.updateTaskDetail(`第 ${chapterId.value} 章：正在写入设定`)
                const { data: applyResult } = await chaptersApi.extractApply(
                    chapterId.value,
                    extraction,
                    contentSnapshot.value
                )
                aiTaskStore.completeTask(
                    true,
                    emptyExtraction
                        ? `第 ${chapterId.value} 章无新设定，已标记为已同步`
                        : `第 ${chapterId.value} 章设定同步完成（新增 ${applyResult.created_files || 0} 文件，更新 ${applyResult.updated_entities || 0} 实体）`,
                    '/workspace/characters'
                )
                settleActivePromise(null, applyResult)
                resetState()
                return
            }

            if (status.status === 'error') {
                await finishWithError(`第 ${chapterId.value} 章设定同步失败：${status.message || '未知错误'}`)
                return
            }

            await finishWithError(`第 ${chapterId.value} 章设定同步状态异常`)
        } catch (error) {
            await finishWithError(`第 ${chapterId.value} 章设定同步失败：${getErrorMessage(error)}`)
        }
    }

    async function startSync(targetChapterId, content) {
        const aiTaskStore = useAiTaskStore()

        if (isRunning.value) {
            throw new Error('已有设定同步任务正在运行')
        }
        if (aiTaskStore.isRunning) {
            throw new Error('当前有其他后台任务进行中，请稍后再试')
        }
        if (!targetChapterId) {
            throw new Error('缺少章节号')
        }
        if (!(content || '').trim()) {
            throw new Error('章节内容为空，无法同步')
        }

        isRunning.value = true
        chapterId.value = targetChapterId
        contentSnapshot.value = content
        activePromise = new Promise((resolve, reject) => {
            resolveActivePromise = resolve
            rejectActivePromise = reject
        })

        aiTaskStore.startTask('设定同步', `第 ${targetChapterId} 章：正在分析设定`)

        try {
            const { data } = await chaptersApi.extractPreview(targetChapterId, content)
            if (!data?.success || !data?.task_id) {
                throw new Error(data?.message || '启动设定同步失败')
            }
            backendTaskId.value = data.task_id
            clearPollTimer()
            pollTimer = setTimeout(pollStatus, 1000)
        } catch (error) {
            await finishWithError(`第 ${targetChapterId} 章设定同步失败：${getErrorMessage(error)}`)
            throw error
        }
    }

    async function startSyncAndWait(targetChapterId, content) {
        await startSync(targetChapterId, content)
        return activePromise
    }

    return {
        isRunning,
        chapterId,
        startSync,
        startSyncAndWait,
    }
})
