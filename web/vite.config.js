import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

// 若由 FastAPI 在 /web 路径下托管构建产物，请将 base 设为 '/web/'
const BASE = process.env.VITE_BASE || '/'

export default defineConfig({
  plugins: [vue()],
  base: BASE,
  server: {
    port: 5173,
    host: true,
    // 开发环境下代理后端，避免跨域问题（也可直接关闭代理，在前端设置面板里填写后端地址）
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/api/, '')
      }
    }
  },
  build: {
    outDir: 'dist',
    chunkSizeWarningLimit: 1024
  }
})
