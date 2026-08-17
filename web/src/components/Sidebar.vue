<script setup>
import { computed } from 'vue'
import { relativeTime } from '../utils/time'

const props = defineProps({
  sessions: { type: Array, required: true },
  activeId: { type: String, default: null }
})

const emit = defineEmits(['select', 'create', 'remove', 'clear-all'])

const sorted = computed(() =>
  [...props.sessions].sort((a, b) => b.updatedAt - a.updatedAt)
)
</script>

<template>
  <aside class="sidebar">
    <div class="brand">
      <div class="brand-logo">📚</div>
      <div class="brand-text">
        <div class="brand-name">企业知识库助手</div>
        <div class="brand-sub">RAG Agent · DeepSeek</div>
      </div>
    </div>

    <button class="btn btn-primary new-chat" @click="emit('create')">
      <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round">
        <path d="M12 5v14M5 12h14" />
      </svg>
      新建对话
    </button>

    <div class="session-list">
      <button
        v-for="s in sorted"
        :key="s.id"
        class="session-item"
        :class="{ active: s.id === activeId }"
        @click="emit('select', s.id)"
      >
        <span class="session-msg-count">{{ s.messages.length ? '💬' : '✏️' }}</span>
        <span class="session-body">
          <span class="session-title">{{ s.title || '新对话' }}</span>
          <span class="session-time">{{ relativeTime(s.updatedAt) }}</span>
        </span>
        <span
          class="session-del"
          title="删除会话"
          @click.stop="emit('remove', s.id)"
        >✕</span>
      </button>

      <div v-if="sorted.length === 0" class="session-empty">
        暂无会话，点击上方「新建对话」开始提问
      </div>
    </div>

    <div class="sidebar-footer">
      <button v-if="sessions.length" class="btn btn-danger-ghost clear-all" @click="emit('clear-all')">
        清空全部会话
      </button>
    </div>
  </aside>
</template>

<style scoped>
.sidebar {
  width: var(--sidebar-w);
  flex-shrink: 0;
  display: flex;
  flex-direction: column;
  background: var(--bg-elev);
  border-right: 1px solid var(--border);
  padding: 16px 12px;
  height: 100%;
}

.brand {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 4px 6px 14px;
}
.brand-logo {
  width: 38px;
  height: 38px;
  border-radius: 10px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 20px;
  background: linear-gradient(135deg, var(--accent), #7c5cff);
  box-shadow: 0 4px 14px var(--accent-soft);
}
.brand-name {
  font-size: 14.5px;
  font-weight: 700;
  line-height: 1.3;
}
.brand-sub {
  font-size: 11px;
  color: var(--text-3);
}

.new-chat {
  width: 100%;
  justify-content: center;
  margin-bottom: 14px;
}

.session-list {
  flex: 1;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: 2px;
  padding-right: 2px;
}

.session-item {
  display: flex;
  align-items: center;
  gap: 8px;
  width: 100%;
  padding: 9px 10px;
  border-radius: var(--radius-sm);
  text-align: left;
  transition: background var(--transition);
}
.session-item:hover {
  background: var(--bg-hover);
}
.session-item.active {
  background: var(--accent-soft);
  box-shadow: inset 2px 0 0 var(--accent);
}

.session-msg-count {
  font-size: 14px;
  flex-shrink: 0;
}

.session-body {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
}
.session-title {
  font-size: 13px;
  color: var(--text);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  line-height: 1.35;
}
.session-item.active .session-title {
  color: var(--accent-strong);
  font-weight: 600;
}
.session-time {
  font-size: 11px;
  color: var(--text-3);
}

.session-del {
  opacity: 0;
  color: var(--text-3);
  font-size: 12px;
  padding: 2px 5px;
  border-radius: 4px;
  flex-shrink: 0;
  transition: opacity var(--transition), background var(--transition);
}
.session-item:hover .session-del {
  opacity: 1;
}
.session-del:hover {
  color: var(--danger);
  background: rgba(229, 72, 77, 0.12);
}

.session-empty {
  padding: 24px 12px;
  text-align: center;
  font-size: 12px;
  color: var(--text-3);
  line-height: 1.7;
}

.sidebar-footer {
  padding-top: 10px;
  border-top: 1px solid var(--border);
}
.clear-all {
  width: 100%;
  justify-content: center;
  font-size: 12px;
}
</style>
