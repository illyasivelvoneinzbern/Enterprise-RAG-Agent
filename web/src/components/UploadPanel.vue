<script setup>
import { ref, computed } from 'vue'
import { uploadFile, isAcceptedFile, getBase } from '../api'

const emit = defineEmits(['close', 'uploaded'])

const dragOver = ref(false)
const uploading = ref(false)
const progress = ref(0)
const error = ref('')
const done = ref(null)

const base = getBase() || '（同源）'

const statusText = computed(() => {
  if (uploading.value) return `正在上传并构建知识库… ${progress.value}%`
  if (done.value) return '✓ 知识库构建完成'
  return '拖拽文件到此处，或点击选择文件'
})

function pickFile(file) {
  if (!file || uploading.value) return
  error.value = ''
  done.value = null
  if (!isAcceptedFile(file.name)) {
    error.value = `不支持的文件类型 ${file.name}：仅支持 .txt / .pdf / .md`
    return
  }
  start(file)
}

function onDrop(e) {
  dragOver.value = false
  pickFile(e.dataTransfer?.files?.[0])
}

async function start(file) {
  uploading.value = true
  progress.value = 0
  try {
    const res = await uploadFile(file, { onProgress: (p) => (progress.value = p) })
    done.value = {
      filename: res.filename ?? file.name,
      size: file.size
    }
  } catch (e) {
    error.value = e.message ?? String(e)
  } finally {
    uploading.value = false
  }
}

function finish() {
  emit('uploaded', done.value?.filename ?? null)
  emit('close')
}
</script>

<template>
  <div class="modal-mask" @click.self="emit('close')">
    <div class="modal">
      <div class="modal-head">
        <h3>📤 上传知识库文档</h3>
        <button class="modal-x" @click="emit('close')">✕</button>
      </div>

      <p class="modal-desc">
        上传文档后将自动完成「加载 → 切分 → Embedding → 建立 FAISS 索引」，
        后端会用新知识库替换当前检索器。支持
        <code>.txt</code> <code>.pdf</code> <code>.md</code>
      </p>

      <div
        class="drop-zone"
        :class="{ 'drag-over': dragOver, uploading }"
        @dragover.prevent="dragOver = true"
        @dragleave.prevent="dragOver = false"
        @drop.prevent="onDrop"
        @click="!uploading && $refs.fileInput?.click()"
      >
        <input
          ref="fileInput"
          type="file"
          accept=".txt,.pdf,.md,.markdown"
          style="display: none"
          @change="pickFile($event.target.files[0])"
        />
        <div class="dz-icon">{{ uploading ? '⏳' : done ? '✅' : '📄' }}</div>
        <div class="dz-text">{{ statusText }}</div>
        <div v-if="uploading" class="progress-track">
          <div class="progress-bar" :style="{ width: progress + '%' }"></div>
        </div>
        <div v-if="done" class="dz-file">
          {{ done.filename }}（{{ (done.size / 1024).toFixed(1) }} KB）
        </div>
      </div>

      <div v-if="error" class="upload-error">⚠️ {{ error }}</div>

      <div class="modal-foot">
        <span class="api-hint">后端地址：{{ base }}</span>
        <div class="foot-btns">
          <button class="btn btn-ghost" @click="emit('close')">关闭</button>
          <button v-if="done" class="btn btn-primary" @click="finish">
            {{ done ? '完成，开始提问' : '上传' }}
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.modal-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 10px;
}
.modal-head h3 {
  font-size: 16px;
}
.modal-x {
  color: var(--text-3);
  font-size: 14px;
  padding: 4px 8px;
  border-radius: 6px;
}
.modal-x:hover {
  background: var(--bg-hover);
  color: var(--text);
}

.modal-desc {
  font-size: 12.5px;
  color: var(--text-2);
  margin-bottom: 16px;
  line-height: 1.7;
}
.modal-desc code {
  font-family: var(--font-mono);
  background: var(--bg-elev-2);
  border: 1px solid var(--border);
  border-radius: 4px;
  padding: 0 5px;
  font-size: 11.5px;
}

.drop-zone {
  border: 2px dashed var(--border-strong);
  border-radius: var(--radius-md);
  padding: 34px 20px;
  text-align: center;
  cursor: pointer;
  transition: border-color var(--transition), background var(--transition);
}
.drop-zone:hover,
.drop-zone.drag-over {
  border-color: var(--accent);
  background: var(--accent-soft);
}
.drop-zone.uploading {
  cursor: wait;
}

.dz-icon {
  font-size: 34px;
  margin-bottom: 10px;
}
.dz-text {
  font-size: 13.5px;
  color: var(--text-2);
}

.progress-track {
  margin: 14px auto 0;
  width: 80%;
  height: 7px;
  background: var(--bg-elev-2);
  border-radius: var(--radius-full);
  overflow: hidden;
}
.progress-bar {
  height: 100%;
  background: linear-gradient(90deg, var(--accent), #7c5cff);
  border-radius: var(--radius-full);
  transition: width 0.2s ease;
}

.dz-file {
  margin-top: 10px;
  font-size: 12.5px;
  color: var(--success);
  font-weight: 600;
}

.upload-error {
  margin-top: 12px;
  padding: 10px 14px;
  background: rgba(229, 72, 77, 0.1);
  border: 1px solid rgba(229, 72, 77, 0.3);
  border-radius: var(--radius-sm);
  color: var(--danger);
  font-size: 12.5px;
}

.modal-foot {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-top: 18px;
}
.api-hint {
  font-size: 11.5px;
  color: var(--text-3);
}
.foot-btns {
  display: flex;
  gap: 8px;
}
</style>
