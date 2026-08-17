<script setup>
import { ref, nextTick } from 'vue'

const props = defineProps({
  streaming: { type: Boolean, default: false },
  disabled: { type: Boolean, default: false }
})

const emit = defineEmits(['send', 'stop'])

const text = ref('')
const ta = ref(null)

function autoGrow() {
  const el = ta.value
  if (!el) return
  el.style.height = 'auto'
  el.style.height = Math.min(el.scrollHeight, 180) + 'px'
}

async function submit() {
  const q = text.value.trim()
  if (!q || props.disabled || props.streaming) return
  emit('send', q)
  text.value = ''
  await nextTick()
  autoGrow()
  ta.value?.focus()
}

function onKeydown(e) {
  if (e.key === 'Enter' && !e.shiftKey && !e.isComposing) {
    e.preventDefault()
    submit()
  }
}
</script>

<template>
  <div class="input-wrap">
    <div class="input-box">
      <textarea
        ref="ta"
        v-model="text"
        class="input-ta"
        rows="1"
        placeholder="输入你的问题，Enter 发送，Shift+Enter 换行…"
        :disabled="disabled"
        @input="autoGrow"
        @keydown="onKeydown"
      ></textarea>

      <button
        v-if="streaming"
        class="send-btn stop"
        title="停止生成"
        @click="emit('stop')"
      >
        <svg width="14" height="14" viewBox="0 0 24 24"><rect x="5" y="5" width="14" height="14" rx="2.5" fill="currentColor" /></svg>
        停止
      </button>

      <button
        v-else
        class="send-btn"
        :disabled="disabled || !text.trim()"
        title="发送"
        @click="submit"
      >
        <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round">
          <path d="M22 2 11 13M22 2l-7 20-4-9-9-4 20-7z" />
        </svg>
      </button>
    </div>
    <div class="input-hint">回答由 AI 基于企业知识库生成，仅供参考</div>
  </div>
</template>

<style scoped>
.input-wrap {
  padding: 12px 0 14px;
}

.input-box {
  display: flex;
  align-items: flex-end;
  gap: 10px;
  background: var(--bg-elev);
  border: 1px solid var(--border-strong);
  border-radius: var(--radius-lg);
  padding: 10px 12px;
  transition: border-color var(--transition), box-shadow var(--transition);
}
.input-box:focus-within {
  border-color: var(--accent);
  box-shadow: 0 0 0 3px var(--accent-soft);
}

.input-ta {
  flex: 1;
  background: transparent;
  border: none;
  outline: none;
  resize: none;
  font-size: 14px;
  line-height: 1.6;
  max-height: 180px;
  padding: 4px 0;
}
.input-ta::placeholder {
  color: var(--text-3);
}
.input-ta:disabled {
  opacity: 0.6;
}

.send-btn {
  flex-shrink: 0;
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 9px 16px;
  border-radius: 10px;
  background: var(--accent);
  color: #fff;
  font-size: 13px;
  font-weight: 600;
  transition: background var(--transition), opacity var(--transition);
}
.send-btn:hover:not(:disabled) {
  background: var(--accent-strong);
}
.send-btn:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}
.send-btn.stop {
  background: var(--bg-elev-2);
  color: var(--danger);
  border: 1px solid rgba(229, 72, 77, 0.35);
}
.send-btn.stop:hover {
  background: rgba(229, 72, 77, 0.1);
}

.input-hint {
  text-align: center;
  font-size: 11px;
  color: var(--text-3);
  margin-top: 8px;
}
</style>
