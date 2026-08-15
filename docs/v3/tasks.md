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

## 阶段 5 — 交付后修复与增强（用户验收 Q&A）

- [x] T5-1 修复「创建会话失败 201」：POST /api/sessions 返回 201 Created 而非 200，判断改为 `in (200, 201)`
- [x] T5-2 二次修改 folder_name 兜底：前端直接传 folder_name 定位输出文件夹（旧会话 status.json 无 session_id 时也可二次修改）
- [x] T5-3 流式文本合并：连续 text delta 合并为一条 agent 消息（修复"每段文字一行"的严重换行）
- [x] T5-4 session_created 即时更新下拉框：生成开始（会话创建瞬间）下拉框即从 "New chat" 变为文件夹名，无需等生成完成
- [x] T5-5 thinking 折叠块：历史 reasoning 字段 → Thinking 折叠块（转换层 + ReasoningBlock 组件，生成中展开/完成后折叠）
- [x] T5-6 键盘焦点守卫：BrowseControls/FreeView/SelectionControls 忽略输入框内按键（打字不再影响自由视角移动）
- [x] T5-7 确认 Hermes 推理流式能力边界：真正的 reasoning 字段不流式推送（仅存 messages 表），`tool.progress` 事件携带的是 content 而非 reasoning（已撤销误加的转发）
