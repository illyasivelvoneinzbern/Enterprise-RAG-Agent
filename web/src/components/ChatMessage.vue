<script setup>
import { computed, ref } from 'vue'
import { renderMarkdown } from '../utils/markdown'

const props = defineProps({
  message: { type: Object, required: true },
  showActions: { type: Boolean, default: true }
})

const emit = defineEmits(['regenerate'])

const isUser = computed(() => props.message.role === 'user')
const isStreaming = computed(() => props.message.streaming === true)
const isWaiting = computed(() => props.message.waiting === true)

const html = computed(() => renderMarkdown(props.message.content))
const showSources = ref(true)

const copied = ref(false)
async function copy() {
  try {
    await navigator.clipboard.writeText(props.message.content)
    copied.value = true
    setTimeout(() => (copied.value = false), 1500)
  } catch {
    /* ignore */
  }
}
</script>

<template>
  <div class="msg-row" :class="isUser ? 'user' : 'assistant'">
    <div v-if="!isUser" class="avatar">🤖</div>

    <div class="msg-col">
      <div class="bubble" :class="{ 'is-streaming': isStreaming }">
        <!-- 等待首个 token（Agent 检索 / 调用工具阶段） -->
        <div v-if="isWaiting" class="thinking">
          <span class="dot"></span><span class="dot"></span><span class="dot"></span>
          <span class="thinking-text">正在检索知识库…</span>
        </div>

        <!-- 流式输出：原文 + 闪烁光标 -->
        <div v-else-if="isStreaming" class="stream-text">
          {{ message.content }}<span class="cursor">▍</span>
        </div>

        <!-- 错误提示 -->
        <div v-else-if="message.error" class="error-box">
          <div class="error-title">⚠️ 出错了</div>
          <div class="error-detail">{{ message.error }}</div>
          <button class="btn btn-ghost retry-btn" @click="emit('regenerate')">↻ 重试</button>
        </div>

        <!-- 完成渲染 -->
        <template v-else>
          <div class="md" v-html="html"></div>

          <!-- 引用来源 -->
          <div v-if="message.sources?.length" class="sources">
            <button class="sources-toggle" @click="showSources = !showSources">
              📎 引用来源（{{ message.sources.length }}）
              <span :class="{ open: showSources }">▾</span>
            </button>
            <ol v-show="showSources" class="sources-list">
              <li v-for="(src, i) in message.sources" :key="i" class="source-item">
                <span class="source-name">{{ src.title ?? src.source ?? `来源 ${i + 1}` }}</span>
                <span v-if="src.page != null" class="source-page">P{{ src.page }}</span>
                <p v-if="src.text" class="source-text">{{ src.text }}</p>
              </li>
            </ol>
          </div>
        </template>
      </div>

      <!-- 操作栏 -->
      <div v-if="showActions && !isUser && !isStreaming && message.content && !message.error" class="msg-actions">
        <button class="mini-btn" title="复制回答" @click="copy">
          {{ copied ? '✓ 已复制' : '复制' }}
        </button>
        <button class="mini-btn" title="重新生成" @click="emit('regenerate')">重新生成</button>
      </div>
    </div>
  </div>
</template>

<style scoped>
.msg-row {
  display: flex;
  gap: 12px;
  padding: 14px 0;
}
.msg-row.user {
  flex-direction: row-reverse;
}

.avatar {
  width: 34px;
  height: 34px;
  border-radius: 50%;
  flex-shrink: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 17px;
  background: linear-gradient(135deg, var(--accent), #7c5cff);
  box-shadow: 0 3px 10px var(--accent-soft);
}

.msg-col {
  max-width: min(78%, 860px);
  display: flex;
  flex-direction: column;
}
.user .msg-col {
  align-items: flex-end;
}

.bubble {
  padding: 12px 16px;
  border-radius: var(--radius-md);
  font-size: 14px;
  line-height: 1.7;
}

.assistant .bubble {
  background: var(--bg-elev);
  border: 1px solid var(--border);
  border-top-left-radius: 4px;
}

.user .bubble {
  background: var(--user-bubble);
  color: var(--user-bubble-text);
  border-top-right-radius: 4px;
  white-space: pre-wrap;
  word-break: break-word;
}

/* 流式光标 */
.stream-text {
  white-space: pre-wrap;
  word-break: break-word;
}
.cursor {
  color: var(--accent-strong);
  animation: blink 0.9s steps(1) infinite;
}
@keyframes blink {
  50% { opacity: 0; }
}

/* 思考指示器 */
.thinking {
  display: flex;
  align-items: center;
  gap: 6px;
  color: var(--text-2);
  font-size: 13px;
  padding: 4px 0;
}
.dot {
  width: 7px;
  height: 7px;
  border-radius: 50%;
  background: var(--accent);
  animation: bounce 1.2s infinite ease-in-out;
}
.dot:nth-child(2) { animation-delay: 0.15s; }
.dot:nth-child(3) { animation-delay: 0.3s; }
.thinking-text { margin-left: 4px; }
@keyframes bounce {
  0%, 60%, 100% { transform: translateY(0); opacity: 0.4; }
  30% { transform: translateY(-5px); opacity: 1; }
}

/* 错误 */
.error-box {
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.error-title {
  font-weight: 600;
  color: var(--danger);
}
.error-detail {
  font-size: 13px;
  color: var(--text-2);
  white-space: pre-wrap;
}
.retry-btn {
  align-self: flex-start;
  font-size: 12px;
  padding: 5px 12px;
}

/* 来源 */
.sources {
  margin-top: 12px;
  padding-top: 10px;
  border-top: 1px dashed var(--border);
}
.sources-toggle {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
  font-weight: 600;
  color: var(--accent-strong);
  padding: 2px 0;
}
.sources-toggle span {
  transition: transform 0.15s ease;
  display: inline-block;
}
.sources-toggle span.open {
  transform: rotate(180deg);
}
.sources-list {
  margin: 8px 0 0;
  padding-left: 20px;
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.source-item {
  font-size: 12.5px;
  color: var(--text-2);
}
.source-name {
  font-weight: 600;
  color: var(--text);
}
.source-page {
  margin-left: 6px;
  font-size: 11px;
  color: var(--text-3);
  border: 1px solid var(--border);
  border-radius: 4px;
  padding: 0 5px;
}
.source-text {
  margin-top: 2px;
  font-size: 12px;
  color: var(--text-3);
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

/* 操作栏 */
.msg-actions {
  display: flex;
  gap: 4px;
  margin-top: 6px;
  padding-left: 2px;
}
.mini-btn {
  font-size: 12px;
  color: var(--text-3);
  padding: 3px 8px;
  border-radius: 6px;
  transition: color var(--transition), background var(--transition);
}
.mini-btn:hover {
  color: var(--text);
  background: var(--bg-hover);
}
</style>
