// Copyright (c) 2026 左岚. All rights reserved.
// useToast.js - 全局 toast 通知(替代原生 alert)
import { reactive } from 'vue'

let uid = 0

export const toasts = reactive([])

function push(type, message, duration = 4000) {
  const id = ++uid
  toasts.push({ id, type, message })
  if (duration > 0) {
    setTimeout(() => dismiss(id), duration)
  }
  return id
}

export function dismiss(id) {
  const i = toasts.findIndex(t => t.id === id)
  if (i !== -1) toasts.splice(i, 1)
}

export function useToast() {
  return {
    success: (msg, duration) => push('success', msg, duration),
    error: (msg, duration) => push('error', msg, duration ?? 6000),
    info: (msg, duration) => push('info', msg, duration),
    dismiss
  }
}
