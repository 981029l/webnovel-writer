<!-- Copyright (c) 2026 左岚. All rights reserved. -->
<!-- App.vue - 主应用组件（简化版） -->
<script setup>
import AiStatusBar from './components/AiStatusBar.vue'
import ToastHost from './components/ToastHost.vue'
</script>

<template>
  <AiStatusBar />
  <RouterView />
  <ToastHost />
</template>
