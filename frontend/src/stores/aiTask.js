// Copyright (c) 2026 左岚. All rights reserved.
// AI 任务全局状态管理

import { defineStore } from 'pinia'
import { ref, computed } from 'vue'

export const useAiTaskStore = defineStore('aiTask', () => {
    // 状态
    const isRunning = ref(false)
    const taskName = ref('')
    const taskDetail = ref('')
    const startTime = ref(null)
    const result = ref(null) // { success: bool, message: string, path?: string }

    // 初始化专用状态
    const streamContent = ref('')
    const streamTarget = ref('') // 'total_outline', 'chapter_content' 等
    const initSteps = ref([])

    // 计算属性
    const elapsedSeconds = computed(() => {
        if (!startTime.value) return 0
        return Math.floor((Date.now() - startTime.value) / 1000)
    })

    const statusText = computed(() => {
        if (isRunning.value) {
            return taskDetail.value
                ? `⏳ ${taskName.value} · ${taskDetail.value}`
                : `⏳ ${taskName.value}...`
        }
        if (result.value) {
            return result.value.message || (
                result.value.success
                    ? `✓ ${taskName.value} 完成`
                    : `✗ ${taskName.value} 失败`
            )
        }
        return ''
    })

    // 方法
    function startTask(name, detail = '') {
        isRunning.value = true
        taskName.value = name
        taskDetail.value = detail
        startTime.value = Date.now()
        result.value = null
        streamContent.value = ''
        streamTarget.value = ''
        initSteps.value = []
    }

    function completeTask(success, message = '', path = '') {
        isRunning.value = false
        result.value = { success, message, path }
    }

    function failTask(message) {
        isRunning.value = false
        result.value = { success: false, message }
    }

    function updateTaskDetail(detail = '') {
        taskDetail.value = detail
    }

    function clearTask() {
        isRunning.value = false
        taskName.value = ''
        taskDetail.value = ''
        startTime.value = null
        result.value = null
        streamContent.value = ''
        streamTarget.value = ''
        initSteps.value = []
    }

    // 更新单个步骤状态
    function updateStep(data) {
        const existing = initSteps.value.find(s => s.step === data.step)
        if (existing) {
            Object.assign(existing, data)
        } else {
            initSteps.value.push(data)
        }
    }

    // 统一的初始化 Action
    async function initProjectAction(params, aiApi) {
        clearTask()
        startTask('项目初始化', '正在构建世界...')
        initSteps.value = []

        try {
            const response = await aiApi.initProjectStream(params)
            if (!response.ok) throw new Error(`请求失败: ${response.status}`)

            const reader = response.body.getReader()
            const decoder = new TextDecoder()
            let buffer = ''

            // 真正的流式处理
            while (true) {
                const { done, value } = await reader.read()
                if (done) break

                buffer += decoder.decode(value, { stream: true })
                const lines = buffer.split('\n\n')
                buffer = lines.pop()

                for (const line of lines) {
                    if (line.startsWith('data: ')) {
                        let data
                        try {
                            data = JSON.parse(line.substring(6))
                        } catch (e) {
                            console.error('Stream parse error:', e)
                            continue
                        }
                        // Business logic outside parse try-catch
                        if (data.type === 'step') {
                            updateStep(data)
                            if (data.status === 'failed') throw new Error(data.error || '步骤失败')
                        } else if (data.type === 'content') {
                            streamContent.value += data.chunk
                            streamTarget.value = data.target
                        } else if (data.type === 'done') {
                            completeTask(data.success !== false, data.message)
                            return
                        } else if (data.type === 'error') {
                            throw new Error(data.message)
                        }
                    }
                }
            }
            // Stream ended without done/error event — mark as failed
            if (isRunning.value) {
                failTask('初始化流异常终止')
            }
        } catch (e) {
            console.error('Init Action Failed:', e)
            failTask(e.message)
            initSteps.value.push({ name: '系统错误', status: 'failed', error: e.message })
        }
    }

    return {
        isRunning,
        taskName,
        taskDetail,
        startTime,
        result,
        elapsedSeconds,
        statusText,
        streamContent,
        streamTarget,
        initSteps,
        startTask,
        completeTask,
        failTask,
        updateTaskDetail,
        clearTask,
        updateStep,
        initProjectAction
    }
})
