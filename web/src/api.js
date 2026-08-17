/**
 * 后端 API 客户端
 * 对接 Enterprise-RAG-Agent (FastAPI)：
 *   POST /rag/chat        普通问答（返回 { answer: { answer, sources } }）
 *   POST /rag/chat/stream 流式问答（text/plain 逐块返回）
 *   POST /upload          上传文档构建知识库（multipart/form-data）
 *   GET  /                健康检查
 */

const STORAGE_KEY = 'rag-web-api-base'

// 默认后端地址：若前端由 FastAPI 托管（端口 8000），则走同源；否则指向本地后端
export function defaultBase() {
  return location.port === '8000' ? '' : 'http://localhost:8000'
}

export function getBase() {
  const saved = localStorage.getItem(STORAGE_KEY)
  return saved !== null && saved !== '' ? saved : defaultBase()
}

export function setBase(url) {
  const v = (url || '').trim().replace(/\/+$/, '')
  if (v) localStorage.setItem(STORAGE_KEY, v)
  else localStorage.removeItem(STORAGE_KEY)
}

function join(base, path) {
  return `${base}/${path}`.replace(/([^:])\/{2,}/g, '$1/')
}

async function handleError(res) {
  if (res.ok) return res
  let detail = `HTTP ${res.status}`
  try {
    const body = await res.json()
    if (body?.detail) detail = typeof body.detail === 'string' ? body.detail : JSON.stringify(body.detail)
  } catch {
    /* ignore */
  }
  throw new Error(detail)
}

/** 健康检查：GET / */
export async function health() {
  try {
    const res = await fetch(join(getBase(), ''), { signal: AbortSignal.timeout(3000) })
    return res.ok
  } catch {
    return false
  }
}

/**
 * 流式问答：POST /rag/chat/stream
 * @returns {Promise<string>} 完整回答文本
 */
export async function chatStream({ session_id, question }, { onChunk, signal } = {}) {
  const res = await fetch(join(getBase(), 'rag/chat/stream'), {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ session_id, question }),
    signal
  })
  await handleError(res)

  const reader = res.body.getReader()
  const decoder = new TextDecoder('utf-8')
  let full = ''
  for (;;) {
    const { done, value } = await reader.read()
    if (done) break
    full += decoder.decode(value, { stream: true })
    onChunk?.(full)
  }
  full += decoder.decode()
  return full
}

/**
 * 非流式问答：POST /rag/chat
 * @returns {Promise<{answer: string, sources: Array}>}
 */
export async function chat({ session_id, question }, { signal } = {}) {
  const res = await fetch(join(getBase(), 'rag/chat'), {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ session_id, question }),
    signal
  })
  await handleError(res)
  const data = await res.json()
  const answer = data?.answer ?? {}
  return {
    answer: typeof answer === 'string' ? answer : answer.answer ?? '',
    sources: Array.isArray(answer.sources) ? answer.sources : []
  }
}

/**
 * 上传文档构建知识库：POST /upload（使用 XHR 以获得上传进度）
 */
export function uploadFile(file, { onProgress, signal } = {}) {
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest()
    xhr.open('POST', join(getBase(), 'upload'))
    xhr.responseType = 'json'

    xhr.upload.onprogress = (e) => {
      if (e.lengthComputable) onProgress?.(Math.round((e.loaded / e.total) * 100))
    }
    xhr.onload = () => {
      if (xhr.status >= 200 && xhr.status < 300) {
        resolve(xhr.response ?? {})
      } else {
        reject(new Error(`上传失败：HTTP ${xhr.status} ${xhr.response?.detail ?? ''}`.trim()))
      }
    }
    xhr.onerror = () => reject(new Error('网络错误：无法连接后端服务'))
    xhr.onabort = () => reject(new DOMException('aborted', 'AbortError'))

    signal?.addEventListener('abort', () => xhr.abort())

    const fd = new FormData()
    fd.append('file', file)
    xhr.send(fd)
  })
}

/** 允许上传的文件类型 */
export const ACCEPTED_EXT = ['txt', 'pdf', 'md', 'markdown']
export function isAcceptedFile(name) {
  const ext = name.split('.').pop()?.toLowerCase()
  return ACCEPTED_EXT.includes(ext)
}
