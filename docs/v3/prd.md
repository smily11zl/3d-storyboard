# V3 PRD — 多会话历史

状态: 已实现 ✅
日期: 2026-08-14

## 1. 背景与目标

V2 每次生成都是"一次性"的：生成完场景替换当前视图，聊天记录只存在内存里，
刷新页面即丢失；也无法回到之前生成的某个场景继续修改。

V3 引入多会话历史：每个生成任务成为一个可持久化的会话，用户可以在历史列表里
切换、查看、删除、继续修改（二次修改）任何一个之前生成的场景。

**核心架构决策：复用 Hermes 的 session 存储**，不自建历史存储。Hermes 每次生成
已在 `state.db` 里自动记录 session + messages + token 用量 + 成本估算，并通过
`/api/sessions` 系列端点暴露。项目后端做一层转发 + 一个"session_id ↔ 文件夹名"
的映射。

## 2. 用户故事

- 作为分镜创作者，我昨天生成的场景今天还能在历史列表里找到并继续修改
- 我在一个历史会话里说"把人物换成女人"，系统基于之前的场景做增量修改
- 我删除某个历史聊天，但它的输出文件（.blend / glTF）还在磁盘上
- 我在历史里点"打开 Finder"直接定位到该场景的输出文件夹

## 3. 功能规格

### F1 历史列表（下拉框）

- 位置: 聊天框标题（"AI Generate"）旁边
- 数据源: Hermes `GET /api/sessions`（source=api_server 的会话）
- 每条显示: 文件夹名 + 描述预览（`20260814_075856 — 两个男人在空地上对峙打斗…`）
  - 描述预览截断（约 30 字符）
  - 文件夹名 = session.started_at 转时间戳，或从映射读取
- 排序: 按时间倒序（最新在前）
- 空历史: 下拉框显示"新聊天"（无历史）

### F2 新建聊天

- 顶部栏一直存在的"+ 新的聊天"按钮
- 点击: 清空当前聊天框 → 进入全新空会话（仅前端内存态，不落盘）
- **新聊天没有提交生成时不产生历史**（不调 Hermes 建 session）

### F3 切换 / 查看历史

- 下拉框选择某个历史 → 加载该 session 的聊天记录到聊天框
- 数据源: Hermes `GET /api/sessions/{id}/messages`
- 消息经转换层还原成前端 UI 格式（见 §6 技术决策）
- 加载后同时恢复该会话对应的场景视图（若存在输出 → 加载 glTF）

### F4 二次修改（增量修改）

- 在历史会话里继续发消息（如"把人物换成女人""机位改成侧面"）
- 前端提交 `POST /api/generate {description, session_id, folder_name}`（复用生成入口）
- 后端用 `session_id` 续接 Hermes 会话（`/chat/stream`，保留上下文），用 `folder_name` 定位输出文件夹
- agent 行为: **读回之前的 `script.py` → 修改代码 → 重新运行生成 scene.blend 覆盖**
  - 不新建代码文件（skill 需支持"修改模式"）
- 覆盖同一文件夹（文件夹名不变）；exports/ 因 hash 变化自动生成新缓存目录
- 结果: 前端刷新场景视图 + 追加新消息到聊天记录

### F5 删除历史

- 每个历史会话提供删除入口
- 删除: `DELETE /api/sessions/{id}`（删 Hermes session 记录 + 聊天消息）
- **输出文件夹保留不动**（generate/output/<时间戳>/ 与 exports/ 均不受影响）
- 删除后从历史列表消失

### F6 打开 Finder

- 历史会话若存在输出文件夹，提供"打开 Finder"入口
- 后端端点调 macOS `open` 命令打开 `generate/output/<时间戳>/`
- 文件夹不存在（如生成失败/取消无产物）时不显示该入口

### F7 session_id ↔ 文件夹名映射

- 生成任务创建时，将 Hermes session_id 写入该任务 `status.json` 的 `session_id` 字段
- 历史列表通过 status.json 反查文件夹名（session.started_at 时间戳作为兜底匹配）
- 二次修改定位输出文件夹：前端直接传 `folder_name`（兼容无 session_id 的旧数据）
- 映射不另建存储，复用 status.json

### F8 思考过程展示（Thinking 折叠块）

- 历史会话中，模型的推理/思考内容（Hermes messages 表的 `reasoning` 字段）以可折叠块展示
- 折叠块样式：一行 `▸ Thinking`，点击展开/收起推理全文
- 推理内容由 deepseek 按需产生（规划/设计步骤有，纯工具调用步骤无），故非每条消息都有
- 能力边界：真正的 reasoning 不流式推送（仅存 messages 表），故思考过程仅在历史回放可见，生成过程中不实时显示

## 4. 非功能需求

- 历史列表/消息读取只读 Hermes 数据，不写 Hermes 内部结构
- 后端转发层做鉴权（内部 API key）与错误兜底（Hermes 不可用时优雅降级）
- 删除操作幂等（重复删除不报错）
- 前端切换会话时，未完成的当前会话提示（生成中不可切换）

## 5. 测试策略

- 自动化: mock Hermes `/api/sessions` 系列端点，覆盖
  历史列表/消息读取/删除转发/映射逻辑/转换层（pytest + httpx，沿用 V2 结构）
- 前端: 构建验证 + 手动交互验证（新建/切换/删除/打开 Finder）
- 手动集成: 真实生成一次 → 历史列表出现 → 二次修改 → 覆盖验证

## 6. 关键技术决策（实现约定）

### 6.1 复用 Hermes session API

| 需求 | Hermes 端点 |
|------|------------|
| 历史列表 | `GET /api/sessions` |
| 聊天记录 | `GET /api/sessions/{id}/messages` |
| 删除 | `DELETE /api/sessions/{id}` |
| 二次修改（续接） | `POST /api/sessions/{id}/chat` |

### 6.2 消息转换层

Hermes 消息（底层 LLM 格式）→ 前端 UI 格式：

| Hermes 存 | 前端显示 | 转换 |
|-----------|---------|------|
| user (content) | user | 直接 |
| assistant (reasoning 非空) | ▸ Thinking 折叠块 | 直接（在 agent 文本前） |
| assistant (content 非空) | agent 文本 | 直接 |
| assistant (tool_calls) | 🔧 tool_start | 拆 tool_calls JSON 数组 |
| tool (content + tool_name) | 📄 tool_output | 直接（截断） |
| （无） | ✓ tool_end 耗时 | 历史回放省略耗时 |
| （无） | status 成功/失败/token | 根据 session 元数据重新生成 |

### 6.3 生成链路（统一走 /chat/stream）

- 生成统一走 Hermes `/api/sessions/{id}/chat/stream`（SSE 流式）
- 首轮：先 `POST /api/sessions` 建会话拿可控 session_id（返回 201 Created），再 `/chat/stream` 续接
- 二次修改：直接续接已有 session_id，不新建会话
- `/v1/responses` 响应不返回 session_id，已弃用为生成入口
- Hermes SSE 事件：`assistant.delta`（文本）/ `tool.started` / `tool.completed`（带 preview）/ `tool.failed` / `run.completed`（带 usage）/ `error` / `done`；`instructions` 字段传 system prompt（ephemeral）

## 7. 范围外（后续迭代）

- 会话重命名（自定义名称）
- 会话内多场景（一个会话多个文件夹版本）
- 历史搜索/过滤
- 会话导出/导入
- 生成目录自动清理
