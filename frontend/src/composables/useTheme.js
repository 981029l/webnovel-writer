// Copyright (c) 2026 左岚. All rights reserved.
// useTheme.js - 明暗主题切换(书房日光 / 书房夜灯)
import { ref } from 'vue'

const STORAGE_KEY = 'wnw-theme'

// index.html 的内联脚本已在应用挂载前设置 data-theme,这里读取当前状态
const current = ref(document.documentElement.dataset.theme === 'dark' ? 'dark' : 'light')

function apply(theme) {
  current.value = theme
  document.documentElement.dataset.theme = theme
  localStorage.setItem(STORAGE_KEY, theme)
}

export function useTheme() {
  return {
    theme: current,
    toggle: () => apply(current.value === 'dark' ? 'light' : 'dark'),
    set: apply
  }
}
