<!-- FanqiePublishView.vue - 番茄小说自动上传（多账号版） -->
<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { fanqieApi } from '../api'

// ─── 环境状态 ───
const envReady = ref(true)
const envError = ref('')
const envFixCommands = ref([])

// ─── 多账号 ───
const accounts = ref([])
const newAccountName = ref('')
const showAddAccount = ref(false)

// ─── 登录 ───
const loginLoading = ref(false)
const loginMessage = ref('')
const loginScreenshot = ref('')
const loginBrowserOpen = ref(false)
const loginAccountName = ref('')
let loginPollTimer = null

// ─── 配置 ───
const bookName = ref('')
const selectedAccount = ref('')
const configSaved = ref(false)
const books = ref([])
const booksLoading = ref(false)
const showManualInput = ref(false)

// ─── 章节 ───
const chapters = ref([])
const chaptersLoading = ref(false)
const selectedIds = ref(new Set())

// ─── 发布 ───
const publishing = ref(false)
const publishProgress = ref(null)
const publishResults = ref([])
const publishDone = ref(false)

// ─── 计算属性 ───
const hasAnyAccount = computed(() => accounts.value.length > 0)
const canPublish = computed(() => hasAnyAccount.value && bookName.value && selectedIds.value.size > 0 && !publishing.value)

// ─── 初始化 ───
let chapterRefreshTimer = null
onMounted(async () => {
  await fetchStatus()
  chapterRefreshTimer = setInterval(fetchChapters, 30000)
})
onUnmounted(() => {
  stopLoginPoll()
  if (publishPollTimer) clearInterval(publishPollTimer)
  if (chapterRefreshTimer) clearInterval(chapterRefreshTimer)
})

async function fetchStatus() {
  try {
    const { data } = await fanqieApi.getStatus()
    envReady.value = data.env_ready
    envError.value = data.env_error || ''
    envFixCommands.value = data.env_fix_commands || []
    accounts.value = data.accounts || []
    bookName.value = data.book_name || ''
    selectedAccount.value = data.account_name || (accounts.value[0]?.name || '')
    if (hasAnyAccount.value) {
      await fetchChapters()
      fetchBooks()
    }
  } catch (e) {
    console.error('获取状态失败:', e)
  }
}

async function fetchBooks() {
  if (!selectedAccount.value) return
  booksLoading.value = true
  try {
    const { data } = await fanqieApi.getBooks(selectedAccount.value)
    books.value = data.books || []
  } catch (e) {
    console.error('获取书籍列表失败:', e)
    books.value = []
  }
  booksLoading.value = false
}

// ─── 登录（轮询） ───
async function startLogin(accountName) {
  if (!accountName) return
  loginLoading.value = true
  loginMessage.value = '正在启动浏览器...'
  loginScreenshot.value = ''
  loginAccountName.value = accountName
  showAddAccount.value = false

  try {
    await fanqieApi.startLogin(accountName)
    loginPollTimer = setInterval(pollLoginStatus, 2000)
    await pollLoginStatus()
  } catch (e) {
    loginMessage.value = '启动失败: ' + (e.response?.data?.detail || e.message)
    loginLoading.value = false
    showAddAccount.value = true  // 恢复表单让用户能重试
  }
}

async function pollLoginStatus() {
  try {
    const { data } = await fanqieApi.pollLogin()
    loginMessage.value = data.message || loginMessage.value
    loginBrowserOpen.value = data.browser_open
    if (data.screenshot) loginScreenshot.value = data.screenshot

    if (data.status === 'success') {
      stopLoginPoll()
      loginLoading.value = false
      // 刷新账号列表
      await fetchStatus()
    } else if (data.status === 'timeout' || data.status === 'error') {
      stopLoginPoll()
      loginLoading.value = false
      if (data.error?.includes('playwright') || data.error?.includes('Chromium')) {
        envReady.value = false
        envError.value = data.error
      }
    }
  } catch (e) { /* 继续轮询 */ }
}

function stopLoginPoll() {
  if (loginPollTimer) { clearInterval(loginPollTimer); loginPollTimer = null }
}

async function closeLoginBrowser() {
  await fanqieApi.closeLoginBrowser()
  loginBrowserOpen.value = false
  loginScreenshot.value = ''
  loginMessage.value = ''
}

async function doLogout(accountName) {
  stopLoginPoll()
  await fanqieApi.logout(accountName)
  accounts.value = accounts.value.filter(a => a.name !== accountName)
  if (selectedAccount.value === accountName) {
    selectedAccount.value = accounts.value[0]?.name || ''
  }
}

function startAddAccount() {
  showAddAccount.value = true
  newAccountName.value = ''
}

function confirmAddAccount() {
  const name = newAccountName.value.trim()
  if (!name) return
  startLogin(name)
}

// ─── 账号切换 ───
async function enterAccount(accountName) {
  selectedAccount.value = accountName
  await fanqieApi.updateConfig({ book_name: bookName.value || '', account_name: accountName })
  await fetchChapters()
  fetchBooks()
}

async function enterBook() {
  if (!bookName.value.trim()) return
  await fanqieApi.updateConfig({ book_name: bookName.value.trim(), account_name: selectedAccount.value })
  configSaved.value = true
  showManualInput.value = false
  setTimeout(() => configSaved.value = false, 2000)
  await fetchChapters()
}

async function selectBook(name) {
  bookName.value = name
  await enterBook()
}

// ─── 章节 ───
async function fetchChapters() {
  chaptersLoading.value = true
  try {
    const { data } = await fanqieApi.getChapters()
    chapters.value = data.chapters || []
  } catch (e) { console.error(e) }
  chaptersLoading.value = false
}

function toggleSelect(id) {
  const s = new Set(selectedIds.value)
  s.has(id) ? s.delete(id) : s.add(id)
  selectedIds.value = s
}
function selectAllUnpublished() {
  selectedIds.value = new Set(chapters.value.filter(c => !c.published).map(c => c.id))
}
function clearSelection() { selectedIds.value = new Set() }

// ─── 发布（轮询） ───
let publishPollTimer = null

async function startPublish() {
  if (!canPublish.value) return
  publishing.value = true
  publishDone.value = false
  publishResults.value = []
  publishProgress.value = { current: 0, total: selectedIds.value.size }

  try {
    const ids = Array.from(selectedIds.value).sort((a, b) => a - b)
    await fanqieApi.startPublish(ids)
    publishPollTimer = setInterval(pollPublishStatus, 2000)
    await pollPublishStatus()
  } catch (e) {
    publishResults.value.push({ type: 'error', message: '启动失败: ' + (e.response?.data?.detail || e.message) })
    publishing.value = false
    publishDone.value = true
  }
}

async function pollPublishStatus() {
  try {
    const { data } = await fanqieApi.pollPublish()
    publishProgress.value = {
      current: data.current, total: data.total,
      chapter_title: data.chapter_title,
      success_count: data.success_count, fail_count: data.fail_count,
      finished: data.status === 'done' || data.status === 'error'
    }
    publishResults.value = data.results || []

    if (!data.active) {
      clearInterval(publishPollTimer)
      publishPollTimer = null
      publishing.value = false
      publishDone.value = true
      await fetchChapters()
    }
  } catch (e) { /* 继续轮询 */ }
}

function formatWordCount(c) { return c >= 10000 ? (c / 10000).toFixed(1) + '万' : String(c) }
</script>

<template>
  <div class="fanqie-layout">
    <div class="fanqie-container">
      <header class="page-header">
        <h1 class="page-title">番茄自动上传</h1>
        <p class="page-subtitle">一键将章节发布到番茄小说平台</p>
      </header>

      <!-- 环境警告 -->
      <section v-if="!envReady" class="card env-warning">
        <div class="env-warning-content">
          <h3 class="env-warning-title">运行环境未就绪</h3>
          <p class="env-warning-msg">{{ envError }}</p>
          <div class="env-commands">
            <code v-for="cmd in envFixCommands" :key="cmd" class="env-cmd">{{ cmd }}</code>
          </div>
          <button class="btn btn-outline btn-sm" @click="fetchStatus">重新检测</button>
        </div>
      </section>

      <!-- 账号管理 -->
      <section v-if="envReady" class="card">
        <div class="card-header">
          <h2 class="card-title">番茄账号</h2>
          <button class="btn btn-primary btn-sm" @click="startAddAccount" :disabled="loginLoading || loginBrowserOpen">
            添加账号
          </button>
        </div>

        <!-- 已有账号列表 -->
        <div v-if="accounts.length > 0" class="account-list">
          <div v-for="acc in accounts" :key="acc.name" class="account-item" :class="{ 'account-active': selectedAccount === acc.name }">
            <div class="account-info">
              <span class="account-name">{{ acc.name }}</span>
              <span v-if="selectedAccount === acc.name" class="status-badge status-current">当前</span>
              <span class="status-badge status-online">已登录</span>
            </div>
            <div class="account-actions">
              <button v-if="selectedAccount !== acc.name" class="btn btn-primary btn-sm" @click="enterAccount(acc.name)">进入</button>
              <a class="btn btn-outline btn-sm" href="https://fanqienovel.com/main/writer/book-manage" target="_blank" rel="noopener">后台</a>
              <button class="btn btn-outline btn-sm btn-danger" @click="doLogout(acc.name)">删除</button>
            </div>
          </div>
        </div>
        <div v-else-if="!showAddAccount && !loginLoading && !loginBrowserOpen" class="empty-hint">
          暂无账号，请点击"添加账号"登录番茄小说
        </div>

        <!-- 添加账号输入 -->
        <div v-if="showAddAccount && !loginLoading && !loginBrowserOpen" class="add-account-form">
          <input v-model="newAccountName" class="config-input" placeholder="输入账号名称（如：主号、小号）" @keyup.enter="confirmAddAccount" />
          <button class="btn btn-primary btn-sm" @click="confirmAddAccount" :disabled="!newAccountName.trim()">开始登录</button>
          <button class="btn btn-outline btn-sm" @click="showAddAccount = false">取消</button>
        </div>

        <!-- 错误提示 -->
        <div v-if="loginMessage && !loginLoading && !loginBrowserOpen" class="login-error">{{ loginMessage }}</div>

        <!-- 登录中 / QR码 -->
        <div v-if="loginLoading || loginBrowserOpen" class="login-area">
          <div v-if="loginScreenshot" class="qr-area">
            <img :src="'data:image/png;base64,' + loginScreenshot" class="qr-screenshot" alt="二维码" />
            <p class="qr-hint">{{ loginMessage }}</p>
          </div>
          <div v-else-if="loginLoading" class="login-loading">
            <div class="spinner"></div>
            <p>{{ loginMessage }}</p>
          </div>

          <!-- 登录成功后的关闭按钮 -->
          <div v-if="loginBrowserOpen && !loginLoading" class="browser-control">
            <p class="success-text">{{ loginMessage }}</p>
            <button class="btn btn-primary" @click="closeLoginBrowser">关闭浏览器</button>
          </div>
        </div>
      </section>

      <!-- 配置区 -->
      <section v-if="envReady && hasAnyAccount" class="card">
        <div class="card-header">
          <h2 class="card-title">发布配置</h2>
          <button class="btn btn-outline btn-sm" @click="fetchBooks" :disabled="booksLoading">刷新书单</button>
        </div>
        <div class="config-body">
          <div class="config-row">
            <label class="config-label">番茄书名</label>

            <!-- 当前已选 -->
            <div v-if="bookName && !showManualInput" class="current-book">
              <span class="current-book-name">{{ bookName }}</span>
              <span class="status-badge status-online">已选</span>
            </div>

            <!-- 书籍列表 -->
            <div v-if="booksLoading" class="books-loading"><div class="spinner spinner-sm"></div><span>正在从番茄后台加载书单...</span></div>
            <div v-else-if="books.length > 0" class="book-chips">
              <span v-for="book in books" :key="book.name"
                class="book-chip" :class="{ active: bookName === book.name }"
                @click="selectBook(book.name)">
                {{ book.name }}
              </span>
            </div>
            <div v-else-if="!booksLoading && hasAnyAccount" class="empty-hint" style="padding: 0.75rem 0; text-align: left;">
              未找到书籍，请先在番茄后台创建
            </div>

            <!-- 手动输入（折叠） -->
            <div class="manual-input-toggle">
              <button v-if="!showManualInput" class="btn btn-outline btn-sm" @click="showManualInput = true">手动输入书名</button>
              <div v-else class="config-input-group">
                <input v-model="bookName" class="config-input" placeholder="输入番茄后台的小说名称" @keyup.enter="enterBook" />
                <button class="btn btn-primary btn-sm" @click="enterBook" :disabled="!bookName.trim()">确认</button>
                <button class="btn btn-outline btn-sm" @click="showManualInput = false">取消</button>
              </div>
            </div>
          </div>
          <div v-if="configSaved" class="save-toast">配置已保存</div>
        </div>
      </section>

      <!-- 章节发布 -->
      <section v-if="envReady && hasAnyAccount" class="card">
        <div class="card-header">
          <h2 class="card-title">章节管理</h2>
          <div class="header-actions">
            <button class="btn btn-outline btn-sm" @click="fetchChapters" :disabled="chaptersLoading">刷新</button>
            <button class="btn btn-outline btn-sm" @click="selectAllUnpublished">全选未发布</button>
            <button v-if="selectedIds.size > 0" class="btn btn-outline btn-sm" @click="clearSelection">取消选择</button>
          </div>
        </div>

        <div class="chapter-table-wrap">
          <div v-if="chaptersLoading" class="loading-state"><div class="spinner"></div><p>加载中...</p></div>
          <div v-else-if="!chapters.length" class="loading-state"><p>暂无章节</p></div>
          <table v-else class="chapter-table">
            <thead><tr><th class="col-check"></th><th class="col-id">章节</th><th class="col-title">标题</th><th class="col-words">字数</th><th class="col-status">状态</th></tr></thead>
            <tbody>
              <tr v-for="ch in chapters" :key="ch.id" :class="{ 'row-published': ch.published, 'row-selected': selectedIds.has(ch.id) }" @click="toggleSelect(ch.id)">
                <td class="col-check"><input type="checkbox" :checked="selectedIds.has(ch.id)" @click.stop="toggleSelect(ch.id)" /></td>
                <td class="col-id">第{{ ch.id }}章</td>
                <td class="col-title">{{ ch.title || '(无标题)' }}</td>
                <td class="col-words">{{ formatWordCount(ch.word_count) }}</td>
                <td class="col-status">
                  <span v-if="ch.published" class="tag tag-success">已发布</span>
                  <span v-else class="tag tag-default">未发布</span>
                </td>
              </tr>
            </tbody>
          </table>
        </div>

        <div class="publish-controls">
          <span v-if="selectedIds.size > 0">已选择 {{ selectedIds.size }} 个章节</span>
          <span v-else class="text-muted">请选择要上传的章节</span>
          <button class="btn btn-primary" :disabled="!canPublish" @click="startPublish">开始上传</button>
        </div>

        <div v-if="publishing || publishDone" class="publish-progress">
          <div v-if="publishProgress" class="progress-header">
            <div class="progress-text">
              <span v-if="publishProgress.finished">上传完成：成功 {{ publishProgress.success_count }} 章，失败 {{ publishProgress.fail_count }} 章</span>
              <span v-else>正在上传 ({{ publishProgress.current }}/{{ publishProgress.total }}) <span class="text-muted">{{ publishProgress.chapter_title }}</span></span>
            </div>
            <div class="progress-bar-wrap"><div class="progress-bar" :style="{ width: ((publishProgress.current||0)/(publishProgress.total||1)*100)+'%' }" :class="{ 'bar-done': publishProgress.finished }"></div></div>
          </div>
          <div v-if="publishResults.length" class="results-log">
            <div v-for="(r,i) in publishResults" :key="i" class="result-item" :class="{ 'result-ok': r.success, 'result-fail': !r.success || r.type==='error' }">
              <span class="result-icon">{{ r.success ? 'OK' : 'ERR' }}</span>
              <span class="result-msg">{{ r.message }}</span>
            </div>
          </div>
        </div>
      </section>
    </div>
  </div>
</template>

<style scoped>
.fanqie-layout { height: 100%; width: 100%; overflow-y: auto; background: var(--bg-background); padding-bottom: 4rem; }
.fanqie-container { max-width: 900px; margin: 0 auto; padding: 0 1.5rem; }
.page-header { padding: 2.5rem 0 1.5rem; }
.page-title { font-size: 1.75rem; font-weight: 800; color: var(--text-primary); margin-bottom: 0.25rem; }
.page-subtitle { color: var(--text-secondary); font-size: 0.9375rem; }

.card { background: var(--bg-card); border: 1px solid var(--border); border-radius: var(--radius-lg); padding: 1.5rem; margin-bottom: 1.25rem; }
.card-header { display: flex; align-items: center; justify-content: space-between; margin-bottom: 1rem; }
.card-title { font-size: 1.0625rem; font-weight: 700; color: var(--text-primary); }

/* Env warning */
.env-warning { border-color: rgba(245,158,11,0.4); background: rgba(245,158,11,0.04); }
.env-warning-title { font-weight: 700; margin-bottom: 0.375rem; }
.env-warning-msg { color: var(--text-secondary); font-size: 0.875rem; margin-bottom: 0.75rem; }
.env-commands { display: flex; flex-direction: column; gap: 0.375rem; margin-bottom: 0.75rem; }
.env-cmd { font-family: monospace; font-size: 0.8125rem; background: var(--bg-background); border: 1px solid var(--border); border-radius: 4px; padding: 0.5rem 0.75rem; user-select: all; }

/* Accounts */
.account-list { display: flex; flex-direction: column; gap: 0.5rem; }
.account-item { display: flex; align-items: center; justify-content: space-between; padding: 0.625rem 0.875rem; background: var(--bg-secondary); border-radius: var(--radius-md); border: 1px solid transparent; transition: border-color 0.2s; }
.account-active { border-color: var(--primary); background: rgba(99,102,241,0.04); }
.account-info { display: flex; align-items: center; gap: 0.75rem; }
.account-actions { display: flex; gap: 0.5rem; }
.account-name { font-weight: 600; font-size: 0.9375rem; color: var(--text-primary); }
.empty-hint { text-align: center; padding: 1.5rem; color: var(--text-muted); font-size: 0.875rem; }

.add-account-form { display: flex; gap: 0.5rem; margin-top: 0.75rem; align-items: center; }
.login-error { margin-top: 0.75rem; padding: 0.625rem 1rem; background: rgba(239,68,68,0.08); border-radius: var(--radius-md); color: var(--error, #ef4444); font-size: 0.875rem; }

/* Login / QR */
.login-area { margin-top: 1rem; text-align: center; }
.qr-area { display: flex; flex-direction: column; align-items: center; gap: 0.75rem; padding: 1rem 0; }
.qr-screenshot { max-width: 280px; max-height: 280px; border-radius: var(--radius-md); border: 2px solid var(--border); image-rendering: pixelated; }
.qr-hint { color: var(--text-secondary); font-size: 0.875rem; }
.login-loading { display: flex; flex-direction: column; align-items: center; gap: 0.75rem; padding: 2rem 0; color: var(--text-muted); }
.browser-control { display: flex; flex-direction: column; align-items: center; gap: 0.75rem; padding: 1rem 0; }
.success-text { color: var(--success, #22c55e); font-weight: 600; }

/* Config */
.config-body { display: flex; flex-direction: column; gap: 1rem; }
.config-row { display: flex; flex-direction: column; gap: 0.5rem; }
.config-label { font-size: 0.8125rem; font-weight: 600; color: var(--text-secondary); }
.config-input-group { display: flex; gap: 0.5rem; }
.config-input { flex: 1; padding: 0.625rem 0.875rem; background: var(--bg-background); border: 1px solid var(--border); border-radius: var(--radius-md); color: var(--text-primary); font-size: 0.875rem; outline: none; }
.config-input:focus { border-color: var(--primary); }
.config-select { padding: 0.625rem 0.875rem; background: var(--bg-background); border: 1px solid var(--border); border-radius: var(--radius-md); color: var(--text-primary); font-size: 0.875rem; }
.book-chips { display: flex; flex-wrap: wrap; gap: 0.5rem; }
.book-chip { padding: 0.375rem 0.875rem; background: var(--bg-secondary); border: 1px solid var(--border); border-radius: 999px; color: var(--text-secondary); font-size: 0.8125rem; cursor: pointer; }
.book-chip:hover { border-color: var(--primary); color: var(--primary); }
.book-chip.active { background: rgba(99,102,241,0.1); border-color: var(--primary); color: var(--primary); font-weight: 600; }
.save-toast { color: var(--success, #22c55e); font-size: 0.8125rem; }

/* Current book */
.current-book { display: flex; align-items: center; gap: 0.5rem; margin-bottom: 0.5rem; }
.current-book-name { font-weight: 600; font-size: 0.9375rem; color: var(--text-primary); }

/* Books loading */
.books-loading { display: flex; align-items: center; gap: 0.5rem; padding: 0.75rem 0; color: var(--text-muted); font-size: 0.875rem; }
.spinner-sm { width: 18px; height: 18px; border-width: 2px; }

/* Manual input toggle */
.manual-input-toggle { margin-top: 0.5rem; }

/* Buttons */
.btn { display: inline-flex; align-items: center; gap: 0.375rem; padding: 0.625rem 1.25rem; border-radius: var(--radius-md); font-size: 0.875rem; font-weight: 600; cursor: pointer; transition: all 0.2s; border: none; white-space: nowrap; }
.btn:disabled { opacity: 0.5; cursor: not-allowed; }
.btn-primary { background: var(--primary); color: white; }
.btn-primary:hover:not(:disabled) { filter: brightness(1.1); }
.btn-outline { background: transparent; border: 1px solid var(--border); color: var(--text-secondary); }
.btn-outline:hover:not(:disabled) { border-color: var(--primary); color: var(--primary); }
.btn-sm { padding: 0.375rem 0.75rem; font-size: 0.8125rem; }
.btn-danger:hover:not(:disabled) { border-color: var(--error, #ef4444); color: var(--error, #ef4444); }
.header-actions { display: flex; gap: 0.5rem; }
.status-badge { font-size: 0.75rem; font-weight: 600; padding: 0.25rem 0.75rem; border-radius: 999px; }
.status-online { background: rgba(34,197,94,0.1); color: var(--success, #22c55e); }
.status-current { background: rgba(99,102,241,0.1); color: var(--primary); }

/* Chapter table */
.chapter-table-wrap { margin-bottom: 1rem; max-height: 450px; overflow-y: auto; border: 1px solid var(--border); border-radius: var(--radius-md); }
.chapter-table { width: 100%; border-collapse: collapse; font-size: 0.875rem; }
.chapter-table thead { position: sticky; top: 0; background: var(--bg-secondary); z-index: 1; }
.chapter-table th { padding: 0.625rem 0.75rem; text-align: left; font-weight: 600; color: var(--text-secondary); font-size: 0.75rem; border-bottom: 1px solid var(--border); }
.chapter-table td { padding: 0.625rem 0.75rem; border-bottom: 1px solid var(--border); }
.chapter-table tbody tr { cursor: pointer; transition: background 0.15s; }
.chapter-table tbody tr:hover { background: var(--bg-hover); }
.row-selected { background: rgba(99,102,241,0.06) !important; }
.row-published { opacity: 0.65; }
.col-check { width: 40px; text-align: center; }
.col-id { width: 80px; font-weight: 600; }
.col-words { width: 80px; color: var(--text-muted); }
.col-status { width: 80px; }
.tag { display: inline-block; font-size: 0.6875rem; font-weight: 600; padding: 0.125rem 0.5rem; border-radius: 999px; }
.tag-success { background: rgba(34,197,94,0.1); color: var(--success, #22c55e); }
.tag-default { background: rgba(156,163,175,0.1); color: var(--text-muted); }

/* Publish */
.publish-controls { display: flex; align-items: center; justify-content: space-between; padding: 1rem 0; border-top: 1px solid var(--border); font-size: 0.875rem; font-weight: 500; }
.text-muted { color: var(--text-muted); }
.publish-progress { margin-top: 1rem; padding: 1.25rem; background: var(--bg-secondary); border-radius: var(--radius-md); }
.progress-text { font-size: 0.875rem; font-weight: 500; margin-bottom: 0.5rem; }
.progress-bar-wrap { height: 6px; background: var(--border); border-radius: 3px; overflow: hidden; }
.progress-bar { height: 100%; background: var(--primary); border-radius: 3px; transition: width 0.3s; }
.bar-done { background: var(--success, #22c55e); }
.results-log { display: flex; flex-direction: column; gap: 0.375rem; max-height: 250px; overflow-y: auto; margin-top: 0.75rem; }
.result-item { display: flex; align-items: center; gap: 0.5rem; font-size: 0.8125rem; padding: 0.375rem 0.5rem; border-radius: 4px; }
.result-ok { color: var(--success, #22c55e); background: rgba(34,197,94,0.06); }
.result-fail { color: var(--error, #ef4444); background: rgba(239,68,68,0.06); }
.result-icon { font-weight: 700; font-size: 0.6875rem; padding: 0.125rem 0.375rem; border-radius: 4px; flex-shrink: 0; }

.spinner { width: 28px; height: 28px; border: 3px solid var(--border); border-top-color: var(--primary); border-radius: 50%; animation: spin 0.8s linear infinite; }
@keyframes spin { to { transform: rotate(360deg); } }
.loading-state { text-align: center; padding: 2.5rem 1rem; color: var(--text-muted); display: flex; flex-direction: column; align-items: center; gap: 0.75rem; }
</style>
