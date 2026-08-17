import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

// 供 FastAPI 在 /web 路径下托管构建产物的配置：
//   npm run build:web
// 构建产物引用 /web/assets/...，配合 app/main.py 中的静态路由使用
export default defineConfig({
  plugins: [vue()],
  base: '/web/',
  build: {
    outDir: 'dist',
    chunkSizeWarningLimit: 1024
  }
})
