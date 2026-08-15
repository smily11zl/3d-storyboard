# V3 Tasks — 多会话历史任务切片

## 阶段 1 — 后端转发层

- [x] T1-1 后端 sessions.py 骨架 + GET /api/sessions（转发 + 附加 folder_name/preview/has_output）
- [x] T1-2 消息转换层 convert_hermes_messages（user/assistant/tool → UI 格式）
- [x] T1-3 GET /api/sessions/{id}/messages（转发 + 转换）
- [x] T1-4 DELETE /api/sessions/{id}（转发，幂等）
- [x] T1-5 POST /api/open-finder（open 命令 + 文件夹校验）
- [x] T1-6 test_sessions.py（mock Hermes 端点，覆盖以上）

## 阶段 2 — 生成链路改造

- [x] T2-1 实测 Hermes session API（POST /api/sessions 建会话 / /chat/stream 续接格式）
- [x] T2-2 status.json 增加 session_id（生成时写回映射）
- [x] T2-3 二次修改端点 POST /api/sessions/{id}/chat（SSE 流式续接）
- [x] T2-4 测试（映射 + 续接）

## 阶段 3 — 前端历史 UI

- [x] T3-1 HistoryDropdown 组件（标题旁历史下拉框）
- [x] T3-2 TopBar "+ 新的聊天"按钮
- [x] T3-3 store 扩展（currentSessionId / sessionList）
- [x] T3-4 ChatPanel 切换历史加载 + 二次修改 + 删除 + 打开 Finder
- [x] T3-5 构建 + 浏览器验证

## 阶段 4 — skill 修改模式 + 收尾

- [x] T4-1 skill 增加"修改模式"约束
- [x] T4-2 文档更新（ROADMAP / 主 PRD / CONTEXT）
- [x] T4-3 全量测试 + 手动集成验证
