# Enterprise RAG Web 前端

基于 **Vue 3 + Vite** 的企业知识库助手前端界面，对接本仓库 FastAPI 后端（`Enterprise-RAG-Agent`）。

## 功能

- 💬 **流式对话**：基于 `POST /rag/chat/stream` 逐字输出，支持「停止生成」「重新生成」「复制回答」
- 🗂️ **多会话管理**：会话自动保存在浏览器 localStorage，每个会话对应后端独立的 `session_id`（多轮上下文互不干扰）
- 📤 **知识库上传**：拖拽上传 `.txt / .pdf / .md`，实时显示上传进度，构建完成后一键提问
- 📎 **引用来源展示**：兼容后端返回的 `sources` 字段（折叠展示）
- 🌙 **暗色 / 亮色主题**：默认跟随系统，可手动切换并记忆
- ⚙️ **后端地址可配置**：连接状态实时检测，支持开发代理 `/api`

## 快速开始

### 1. 启动后端

```bash
cd ..   # 回到 Enterprise-RAG-Agent 根目录
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### 2. 启动前端（开发模式）

```bash
npm install
npm run dev
```

访问 http://localhost:5173 ，右上角「⚙️」确认后端地址为 `http://localhost:8000`。

> 后端已配置 CORS，前端可直接跨域调用；也可以把后端地址填成 `/api`，走 Vite 开发代理。

### 3. 生产构建

```bash
npm run build        # 独立部署：产物在 dist/，可用任意静态服务器或 vite preview 托管
npm run build:web    # 由 FastAPI 托管：产物引用 /web/ 前缀，配合后端 /web 路由
```

由 FastAPI 托管时（`build:web`），只需启动后端即可，访问 http://localhost:8000/web/ 打开界面。

## 目录结构

```
web/
├── index.html
├── vite.config.js          # 开发配置（端口 5173，/api 代理）
├── vite.web.config.js      # 由 FastAPI 托管时的构建配置（base=/web/）
└── src/
    ├── main.js
    ├── App.vue             # 主布局：侧边栏 + 对话区 + 顶栏
    ├── api.js              # 后端 API 客户端（流式/普通问答、上传、健康检查）
    ├── style.css           # 全局样式与主题变量（暗色/亮色）
    ├── composables/
    │   ├── useSessions.js  # 会话与消息状态管理（localStorage 持久化）
    │   └── useTheme.js     # 主题切换
    ├── components/
    │   ├── Sidebar.vue     # 会话列表
    │   ├── ChatMessage.vue # 消息气泡（Markdown 渲染、来源、复制/重试）
    │   ├── ChatInput.vue   # 输入框（自动增高、Enter 发送、停止生成）
    │   └── UploadPanel.vue # 知识库上传弹窗（拖拽 + 进度）
    └── utils/
        ├── markdown.js     # marked + DOMPurify 渲染
        └── time.js         # 相对时间格式化
```

## 对接的 API

| 接口 | 说明 |
| ---- | ---- |
| `POST /rag/chat/stream` | 流式问答（默认使用） |
| `POST /rag/chat` | 普通问答（返回 answer + sources） |
| `POST /upload` | 上传文档构建知识库 |
| `GET /` | 健康检查（连接状态指示） |
