<script setup>
import { ref, computed, watch, onMounted, onBeforeUnmount, nextTick } from 'vue'
import Sidebar from './components/Sidebar.vue'
import ChatMessage from './components/ChatMessage.vue'
import ChatInput from './components/ChatInput.vue'
import UploadPanel from './components/UploadPanel.vue'
import { useSessions } from './composables/useSessions'
import { useTheme } from './composables/useTheme'
import { chatStream, health, getBase, setBase, defaultBase } from './api'

const {
  state,
  isStreaming,
  activeSession,
  createSession,
  removeSession,
  clearAll,
  ensureActive,
  pushUserMessage,
  beginAssistantMessage,
  endAssistantMessage,
  setActive
} = useSessions()

const { theme, toggle } = useTheme()

/* ---------------- 会话切换 ---------------- */
function selectSession(id) {
  if (isStreaming.value) abortStream()
  setActive(id)
  scrollToBottom(false)
}

function remove(id) {
  if (state.activeId === id && isStreaming.value) abortStream()
  removeSession(id)
}

function clear() {
  if (isStreaming.value) abortStream()
  clearAll()
}

/* ---------------- 发送 / 停止 / 重试 ---------------- */
let abortCtrl = null

function abortStream() {
  abortCtrl?.abort()
}

function scrollToBottom(smooth = false) {
  nextTick(() => {
    const el = scrollRef.value
    if (el) el.scrollTo({ top: el.scrollHeight, behavior: smooth ? 'smooth' : 'auto' })
  })
}

async function send(question) {
  const session = ensureActive()
  pushUserMessage(session, question)
  const msg = beginAssistantMessage(session)
  scrollToBottom(true)

  abortCtrl = new AbortController()
  try {
    const full = await chatStream(
      { session_id: session.id, question },
      {
        signal: abortCtrl.signal,
        onChunk: (text) => {
          msg.content = text
          msg.waiting = false
          scrollToBottom(true)
        }
      }
    )
    msg.content = full
    endAssistantMessage(session, msg)
  } catch (e) {
    if (e.name === 'AbortError') {
      endAssistantMessage(session, msg) // 用户主动停止，保留已生成内容
    } else {
      endAssistantMessage(session, msg, { error: e.message || String(e) })
    }
  }
}

/** 重新生成：删除上一条助手回复，重发最近一次提问 */
async function regenerate() {
  if (isStreaming.value) return
  const session = activeSession.value
  if (!session) return
  const last = session.messages[session.messages.length - 1]
  if (last?.role === 'assistant') session.messages.pop()
  const userMsg = [...session.messages].reverse().find((m) => m.role === 'user')
  if (!userMsg) return
  await send(userMsg.content)
}

/* ---------------- 建议问题 ---------------- */
const suggestions = [
  '知识库里包含哪些内容？',
  '员工每年有多少天年假？',
  '考勤和请假制度是怎样的？',
  '帮我总结知识库文档的要点'
]

/* ---------------- 上传 ---------------- */
const showUpload = ref(false)
const toast = ref('')

let toastTimer = null
function showToast(msg) {
  toast.value = msg
  clearTimeout(toastTimer)
  toastTimer = setTimeout(() => (toast.value = ''), 3200)
}

function onUploaded(filename) {
  showToast(`📚 知识库已更新：${filename}，现在可以开始提问了`)
}

/* ---------------- 连接状态 & 设置 ---------------- */
const online = ref(null)
const showSettings = ref(false)
const baseInput = ref(getBase())
const testing = ref(false)
const testResult = ref('')

async function checkHealth() {
  online.value = await health()
}
const healthTimer = setInterval(checkHealth, 30_000)
onMounted(checkHealth)
onBeforeUnmount(() => clearInterval(healthTimer))

async function saveSettings() {
  setBase(baseInput.value)
  baseInput.value = getBase()
  showSettings.value = false
  showToast('⚙️ 后端地址已保存')
  await checkHealth()
}

async function testConnection() {
  testing.value = true
  testResult.value = ''
  const ok = await health()
  testResult.value = ok ? '✓ 连接成功' : '✕ 无法连接，请检查服务是否启动'
  testing.value = false
  online.value = ok
}

/* ---------------- 自动滚动 ---------------- */
const scrollRef = ref(null)
watch(
  () => activeSession.value?.messages.length,
  () => scrollToBottom(false)
)

const messages = computed(() => activeSession.value?.messages ?? [])
</script>

<template>
  <div class="app-shell">
    <Sidebar
      :sessions="state.sessions"
      :active-id="state.activeId"
      @select="selectSession"
      @create="createSession"
      @remove="remove"
      @clear-all="clear"
    />

    <main class="chat-area">
      <!-- 顶栏 -->
      <header class="chat-header">
        <div class="header-left">
          <h2 class="header-title">{{ activeSession?.title || '企业知识库助手' }}</h2>
          <span v-if="messages.length" class="header-count">{{ messages.length }} 条消息</span>
        </div>

        <div class="header-right">
          <span
            class="conn"
            :class="online === true ? 'ok' : online === false ? 'bad' : 'unknown'"
            :title="online === true ? '后端服务正常' : online === false ? '后端服务不可用' : '检测中…'"
          >
            <span class="conn-dot"></span>
            {{ online === true ? '服务正常' : online === false ? '服务离线' : '检测中' }}
          </span>

          <button class="btn btn-ghost" title="上传知识库文档" @click="showUpload = true">
            📤 上传知识库
          </button>

          <div class="settings-wrap">
            <button class="icon-btn" title="设置" @click="showSettings = !showSettings">⚙️</button>
            <div v-if="showSettings" class="popover settings-pop">
              <div class="field-label">后端 API 地址</div>
              <div class="settings-row">
                <input
                  v-model="baseInput"
                  class="text-input"
                  placeholder="http://localhost:8000"
                  @keydown.enter="saveSettings"
                />
              </div>
              <div class="settings-hint">
                默认 <code>{{ defaultBase() || '（同源）' }}</code>；开发环境也可填
                <code>/api</code> 走 Vite 代理。
              </div>
              <div class="settings-actions">
                <button class="btn btn-ghost" :disabled="testing" @click="testConnection">
                  {{ testing ? '测试中…' : '测试连接' }}
                </button>
                <button class="btn btn-primary" @click="saveSettings">保存</button>
              </div>
              <div v-if="testResult" class="test-result">{{ testResult }}</div>
            </div>
          </div>

          <button class="icon-btn" :title="theme === 'dark' ? '切换亮色主题' : '切换暗色主题'" @click="toggle">
            {{ theme === 'dark' ? '🌙' : '☀️' }}
          </button>
        </div>
      </header>

      <!-- 消息区 -->
      <div ref="scrollRef" class="messages">
        <div v-if="messages.length === 0" class="welcome">
          <div class="welcome-logo">📚</div>
          <h1>企业知识库助手</h1>
          <p>基于 RAG 检索增强生成，回答均来自你上传的企业文档。<br />先上传知识库文档，再开始提问。</p>
          <div class="suggestions">
            <button v-for="s in suggestions" :key="s" class="suggestion-chip" @click="send(s)">
              {{ s }}
            </button>
          </div>
        </div>

        <template v-else>
          <ChatMessage
            v-for="(m, i) in messages"
            :key="i"
            :message="m"
            :show-actions="i === messages.length - 1"
            @regenerate="regenerate"
          />
        </template>
      </div>

      <!-- 输入区 -->
      <div class="input-area">
        <ChatInput :streaming="isStreaming" @send="send" @stop="abortStream" />
      </div>
    </main>

    <!-- 上传弹窗 -->
    <UploadPanel v-if="showUpload" @close="showUpload = false" @uploaded="onUploaded" />

    <!-- Toast -->
    <transition name="toast">
      <div v-if="toast" class="toast">{{ toast }}</div>
    </transition>
  </div>
</template>

<style scoped>
.app-shell {
  display: flex;
  height: 100%;
  overflow: hidden;
}

/* ---------- 主区域 ---------- */
.chat-area {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
}

.chat-header {
  height: var(--header-h);
  flex-shrink: 0;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 0 24px;
  border-bottom: 1px solid var(--border);
  background: var(--bg);
}

.header-left {
  display: flex;
  align-items: baseline;
  gap: 10px;
  min-width: 0;
}
.header-title {
  font-size: 15px;
  font-weight: 600;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  max-width: 40vw;
}
.header-count {
  font-size: 11.5px;
  color: var(--text-3);
  flex-shrink: 0;
}

.header-right {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-shrink: 0;
}

.icon-btn {
  width: 34px;
  height: 34px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border-radius: var(--radius-sm);
  font-size: 15px;
  border: 1px solid var(--border);
  background: var(--bg-elev);
  transition: background var(--transition);
}
.icon-btn:hover {
  background: var(--bg-hover);
}

.conn {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
  color: var(--text-2);
  padding: 6px 10px;
  border-radius: var(--radius-full);
  background: var(--bg-elev);
  border: 1px solid var(--border);
}
.conn-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: var(--text-3);
}
.conn.ok .conn-dot {
  background: var(--success);
  box-shadow: 0 0 6px var(--success);
}
.conn.bad .conn-dot {
  background: var(--danger);
  box-shadow: 0 0 6px var(--danger);
}
.conn.ok { color: var(--success); }
.conn.bad { color: var(--danger); }

.settings-wrap {
  position: relative;
}
.settings-pop {
  min-width: 340px;
}
.settings-row {
  display: flex;
  gap: 8px;
}
.settings-hint {
  margin-top: 8px;
  font-size: 11.5px;
  color: var(--text-3);
  line-height: 1.7;
}
.settings-hint code {
  font-family: var(--font-mono);
  background: var(--bg-elev-2);
  border: 1px solid var(--border);
  border-radius: 4px;
  padding: 0 4px;
  font-size: 11px;
}
.settings-actions {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
  margin-top: 14px;
}
.test-result {
  margin-top: 10px;
  font-size: 12.5px;
  font-weight: 600;
}

/* ---------- 消息区 ---------- */
.messages {
  flex: 1;
  overflow-y: auto;
  padding: 8px 24px 0;
}

.welcome {
  height: 100%;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  text-align: center;
  padding-bottom: 40px;
}
.welcome-logo {
  width: 72px;
  height: 72px;
  border-radius: 20px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 36px;
  background: linear-gradient(135deg, var(--accent), #7c5cff);
  box-shadow: 0 12px 36px var(--accent-soft);
  margin-bottom: 20px;
}
.welcome h1 {
  font-size: 22px;
  margin-bottom: 10px;
}
.welcome p {
  color: var(--text-2);
  font-size: 13.5px;
  line-height: 1.8;
  margin-bottom: 28px;
}

.suggestions {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  justify-content: center;
  max-width: 560px;
}
.suggestion-chip {
  padding: 9px 16px;
  border-radius: var(--radius-full);
  background: var(--bg-elev);
  border: 1px solid var(--border);
  color: var(--text-2);
  font-size: 13px;
  transition: all var(--transition);
}
.suggestion-chip:hover {
  border-color: var(--accent);
  color: var(--accent-strong);
  background: var(--accent-soft);
  transform: translateY(-1px);
}

/* ---------- 输入区 ---------- */
.input-area {
  flex-shrink: 0;
  padding: 0 24px;
}

/* ---------- Toast ---------- */
.toast {
  position: fixed;
  top: 20px;
  right: 24px;
  z-index: 200;
  background: var(--bg-elev);
  border: 1px solid var(--border);
  border-left: 3px solid var(--success);
  color: var(--text);
  padding: 12px 18px;
  border-radius: var(--radius-md);
  box-shadow: var(--shadow);
  font-size: 13px;
  max-width: 380px;
}
.toast-enter-active,
.toast-leave-active {
  transition: all 0.25s ease;
}
.toast-enter-from,
.toast-leave-to {
  opacity: 0;
  transform: translateY(-8px);
}
</style>
