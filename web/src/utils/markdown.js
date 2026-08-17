import { marked } from 'marked'
import DOMPurify from 'dompurify'

marked.use({
  gfm: true,
  breaks: true
})

/** 将 Markdown 渲染为经过 XSS 过滤的安全 HTML */
export function renderMarkdown(text) {
  const html = marked.parse(text ?? '')
  return DOMPurify.sanitize(html)
}
