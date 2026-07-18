// Copyright (c) 2026 左岚. All rights reserved.
// main.js - Vue 应用入口

// 自托管字体(unicode-range 子集化,按需下载)
// 晴窗编辑部:Inter(UI)/ IBM Plex Mono(读数)/ Noto Sans SC(中文)/ 霞鹜文楷(手稿)
import '@fontsource/inter/400.css'
import '@fontsource/inter/500.css'
import '@fontsource/inter/600.css'
import '@fontsource/ibm-plex-mono/400.css'
import '@fontsource/ibm-plex-mono/500.css'
import '@fontsource/noto-sans-sc/400.css'
import '@fontsource/noto-sans-sc/500.css'
import '@fontsource/noto-sans-sc/700.css'
import 'lxgw-wenkai-screen-webfont/style.css'

import { createApp } from 'vue'
import { createPinia } from 'pinia'
import App from './App.vue'
import router from './router'
import './assets/main.css'

const app = createApp(App)

app.use(createPinia())
app.use(router)

app.mount('#app')
