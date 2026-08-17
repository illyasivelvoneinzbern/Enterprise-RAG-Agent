import { ref, watch } from 'vue'

const STORAGE_KEY = 'rag-web-theme'

function loadTheme() {
  const saved = localStorage.getItem(STORAGE_KEY)
  if (saved === 'light' || saved === 'dark') return saved
  // 默认跟随系统
  return window.matchMedia?.('(prefers-color-scheme: light)').matches ? 'light' : 'dark'
}

const theme = ref(loadTheme())

watch(theme, (v) => {
  localStorage.setItem(STORAGE_KEY, v)
  document.documentElement.dataset.theme = v
})
document.documentElement.dataset.theme = theme.value

export function useTheme() {
  function toggle() {
    theme.value = theme.value === 'dark' ? 'light' : 'dark'
  }
  return { theme, toggle }
}
