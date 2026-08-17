import { computed, reactive, watch } from 'vue'

/**
 * 会话管理：会话列表与消息记录保存在 localStorage，
 * 每个会话的 id 即后端 Memory 的 session_id（服务端按会话保留多轮上下文）。
 */

const STORAGE_KEY = 'rag-web-sessions'

function load() {
  try {
    return JSON.parse(localStorage.getItem(STORAGE_KEY)) ?? []
  } catch {
    return []
  }
}

function now() {
  return Date.now()
}

const state = reactive({
  sessions: load(),
  activeId: load()[0]?.id ?? null,
  // 运行时状态（不持久化）
  streaming: false
})

function persist() {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(state.sessions))
}

/** 是否还有尚未结束的流式回复 */
const isStreaming = computed(() => state.streaming)

const activeSession = computed(() => state.sessions.find((s) => s.id === state.activeId) ?? null)

function ensureActive() {
  if (!activeSession.value) createSession()
  return activeSession.value
}

function createSession() {
  const s = {
    id: crypto.randomUUID(),
    title: '新对话',
    createdAt: now(),
    updatedAt: now(),
    messages: []
  }
  state.sessions.push(s)
  state.activeId = s.id
  persist()
  return s
}

function removeSession(id) {
  const idx = state.sessions.findIndex((s) => s.id === id)
  if (idx === -1) return
  state.sessions.splice(idx, 1)
  if (state.activeId === id) {
    state.activeId = state.sessions[0]?.id ?? null
  }
  persist()
}

function clearAll() {
  state.sessions = []
  state.activeId = null
  persist()
}

function touch(session) {
  session.updatedAt = now()
}

/** 以第一条提问作为会话标题 */
function maybeTitle(session, question) {
  if (session.title === '新对话') {
    session.title = question.trim().replace(/\s+/g, ' ').slice(0, 24)
  }
}

function pushUserMessage(session, question) {
  session.messages.push({ role: 'user', content: question, ts: now() })
  maybeTitle(session, question)
  touch(session)
}

/** 创建一条“正在生成”的助手消息占位，返回消息对象 */
function beginAssistantMessage(session) {
  const msg = { role: 'assistant', content: '', sources: [], streaming: true, waiting: true, ts: now() }
  session.messages.push(msg)
  state.streaming = true
  persist()
  return msg
}

function endAssistantMessage(session, msg, { error } = {}) {
  msg.streaming = false
  msg.waiting = false
  if (error) msg.error = error
  touch(session)
  state.streaming = false
  persist()
}

watch(
  () => state.sessions.map((s) => s.messages.length),
  () => persist(),
  { deep: false }
)

export function useSessions() {
  return {
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
    setActive(id) {
      state.activeId = id
    }
  }
}
