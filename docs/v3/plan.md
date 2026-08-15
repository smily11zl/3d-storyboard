# V3 Plan — 多会话历史实施计划

状态: 已完成 ✅
日期: 2026-08-14

> 四个阶段全部完成。阶段 2 的关键决策（session_id 获取方式）实测后改为：
> **统一走 `/api/sessions/{id}/chat/stream`**（先建会话拿可控 session_id，再续接生成），
> 而非 `/v1/responses`（其响应不返回 session_id）。

## 阶段划分

### 阶段 1 — 后端转发层（TDD）
1. backend/sessions.py: 转发 Hermes /api/sessions 系列端点
   - GET /api/sessions（附加 folder_name/preview/has_output）
   - GET /api/sessions/{id}/messages（转换层还原）
   - DELETE /api/sessions/{id}（幂等）
2. 消息转换层 convert_hermes_messages
3. POST /api/open-finder（macOS open 命令，校验文件夹存在）
4. backend/tests/test_sessions.py（mock Hermes 端点）

### 阶段 2 — 生成链路改造（TDD）
1. status.json 增加 session_id 字段（生成时写回）
2. 二次修改: POST /api/sessions/{id}/chat 续接生成（复用流式逻辑）
3. session_id 获取: 从 /v1/responses 响应回查 或 显式传 session_id
4. 测试: 映射逻辑 / 续接端点

### 阶段 3 — 前端历史 UI
1. HistoryDropdown 组件（历史下拉框，标题旁）
2. TopBar "+ 新的聊天"按钮
3. store 扩展: currentSessionId / sessionList
4. ChatPanel: 切换历史加载记录 / 二次修改 / 删除 / 打开 Finder
5. 构建 + 浏览器验证

### 阶段 4 — skill 修改模式 + 收尾
1. skill 增加"修改模式"约束（读回 script.py 修改）
2. 文档更新（ROADMAP / 主 PRD / CONTEXT）
3. 全量测试 + 手动集成验证（真实生成 → 历史 → 二次修改 → 删除）

## 关键风险

- Hermes session API 的实际响应格式需在阶段 1 实测确认（POST /api/sessions 建会话、
  /chat 续接的请求/响应结构）
- 二次修改的 skill 行为需验证（读回 script.py 修改是否稳定）
- session_id 获取方式需实测（/v1/responses 是否返回 session_id）
