# V3 Design — 多会话历史架构

日期: 2026-08-14

## 1. 总体架构

```
前端 (React + TS)
  ├─ TopBar: [+ 新的聊天] [历史下拉框] [Upload .blend] [⚙]
  ├─ ChatPanel: 聊天框（标题旁历史下拉框）
  └─ 查看器: 不变

后端 (FastAPI, 8000)
  ├─ /api/sessions/*          —— 转发到 Hermes /api/sessions/*
  │     GET    /api/sessions            （历史列表，附加文件夹名+预览）
  │     GET    /api/sessions/{id}/messages （聊天记录，转换层还原）
  │     DELETE /api/sessions/{id}       （删除会话）
  ├─ /api/generate             —— 生成入口（首轮 + 二次修改共用，带 session_id/folder_name）
  ├─ /api/generate/{id}/status —— 现有
  └─ /api/open-finder          —— macOS open 命令

Hermes API Server (8643, 内嵌)
  └─ /api/sessions 系列 + /api/sessions/{id}/chat/stream（底层生成/续接）
```

> 注：二次修改不设独立端点，复用 `POST /api/generate`，payload 携带 `session_id`（续接会话）+ `folder_name`（定位输出文件夹）。

## 2. 数据流

### 2.1 新建聊天 + 生成（首轮）

```
前端 [+ 新的聊天] → 空会话（内存态，不落盘）
前端提交描述 → POST /api/generate {description}
  后端创建任务（时间戳文件夹 + status.json）
  后端 POST /api/sessions 建会话（拿可控 session_id；返回 201 Created）
  后端发 session_created 事件 → 写 session_id 到 status.json + 通知前端（下拉框即时变为文件夹名）
  后端续接 POST /api/sessions/{id}/chat/stream（SSE 流式生成）
  生成完成（run.completed 带 usage）→ 前端加载场景 + token 统计
```

### 2.2 历史列表加载

```
前端 GET /api/sessions
  后端转发 GET Hermes /api/sessions
  对每条 session:
    - 通过 status.json 反查文件夹名（started_at 时间戳兜底）
    - 取 preview 作描述预览
  返回 [{id, folder_name, preview, tokens, cost, has_output}]
前端渲染下拉框
```

### 2.3 切换历史

```
前端选择历史 → GET /api/sessions/{id}/messages
  后端转发 Hermes messages → 转换层还原前端格式
  前端恢复聊天记录 + 若 has_output 加载对应 glTF
```

### 2.4 二次修改

```
前端在历史会话发消息 → POST /api/generate {description, session_id, folder_name}
  后端用 session_id 续接 Hermes session（/chat/stream，不新建会话）
  后端用 folder_name 定位输出文件夹（覆盖同文件夹，不新建）
  agent 读回 script.py → 修改 → 重新运行 → 覆盖 scene.blend
  后端重新导出 glTF（hash 变化 → 新 exports/ 目录）
  前端追加消息 + 刷新场景
```

### 2.5 删除历史

```
前端 DELETE /api/sessions/{id}
  后端转发 Hermes DELETE
  输出文件夹保留（不删 generate/output/ 与 exports/）
```

### 2.6 打开 Finder

```
前端 POST /api/open-finder {folder_name}
  后端校验文件夹存在于 generate/output/ 下
  subprocess.run(["open", 文件夹绝对路径])
```

## 3. session_id ↔ 文件夹名映射

- **权威来源**: 每个任务的 `generate/output/<时间戳>/status.json` 增加 `session_id` 字段
- 生成链路改造: 后端 `session_created` 事件拿到 Hermes session_id 后写回 status.json
- **二次修改定位**: 前端直接传 `folder_name`（不依赖 session_id 反查），兼容旧会话（status.json 无 session_id 的历史数据）
- **兜底**: `find_folder_near_timestamp` 用 session.started_at（epoch 秒）转 `YYYYMMDD_HHMMSS`，±3 秒容差匹配旧文件夹
- 历史列表组装时: 先查 status.json 映射，缺失则用时间戳兜底

## 4. 后端转发层设计

```python
# backend/sessions.py（新增）
@router.get("/api/sessions")
async def list_sessions():
    # 转发 GET http://localhost:8643/api/sessions
    # 附加 folder_name / preview / has_output
    ...

@router.get("/api/sessions/{session_id}/messages")
async def get_session_messages(session_id: str):
    # 转发 → 转换层还原前端消息格式
    ...

@router.delete("/api/sessions/{session_id}")
async def delete_session(session_id: str):
    # 转发 DELETE（幂等，404 视为成功）
    ...

# 注：二次修改不设独立端点，复用 /api/generate（backend/generate.py）
#     GeneratePayload 含 session_id（续接）+ folder_name（定位输出文件夹）
```

- 鉴权: 复用 Hermes 的 API_SERVER_KEY（内部转发加 Bearer header）
- 错误兜底: Hermes 8643 不可用时返回 502 + 明确错误

## 5. 消息转换层

```python
def convert_hermes_messages(hermes_messages: list[dict]) -> list[dict]:
    """Hermes user/assistant/tool → 前端 UI 消息格式。"""
    result = []
    for msg in hermes_messages:
        role = msg["role"]
        if role == "user":
            result.append({"role": "user", "content": msg["content"]})
        elif role == "assistant":
            # reasoning（模型推理/思考）→ 折叠的 Thinking 块（在 agent 文本之前）
            reasoning = msg.get("reasoning") or msg.get("reasoning_content")
            if reasoning:
                result.append({"role": "reasoning", "content": reasoning})
            content = msg.get("content") or ""
            if content:
                result.append({"role": "agent", "content": content})
            # tool_calls → tool_start（参数截断）
            for call in json.loads(msg.get("tool_calls") or "[]"):
                result.append({
                    "role": "tool_start",
                    "name": call.get("name", "tool"),
                    "content": (call.get("arguments") or "")[:120],
                })
        elif role == "tool":
            output = msg.get("content") or ""
            result.append({"role": "tool_output", "content": output[:150]})
    return result
```

- tool_end 耗时在历史回放中省略（Hermes 未存）
- status（成功/失败/token 统计）由前端根据 session 元数据（end_reason / tokens）补

## 6. 二次修改的 skill 改动

- storyboard-scene-generator skill 增加"修改模式"约束:
  - 当输出目录已存在 script.py 时 → 读回 script.py 修改（不新建文件）
  - 按新指令只改相关部分，保留其他内容
  - 重新运行 script.py 生成 scene.blend 覆盖
- skill 由用户手动维护（skill_manage 不可改，需提示用户或直接改文件）

## 7. 前端状态管理

- store 扩展:
  - `currentSessionId: string | null`（当前活动会话）
  - `sessionList: SessionSummary[]`（历史列表缓存）
- 新建聊天: 清空 currentSessionId + messages
- 切换历史: 加载 messages + 恢复场景

## 8. 目录结构（V3 增量）

```
backend/sessions.py          （新增：转发层 + 转换层 + open-finder）
backend/tests/test_sessions.py（新增：mock Hermes session 端点）
frontend/src/components/HistoryDropdown.tsx（新增：历史下拉框）
frontend/src/components/TopBar.tsx（改：+ 新的聊天按钮）
frontend/src/components/ChatPanel.tsx（改：session 状态 + 二次修改）
frontend/src/store.ts        （改：currentSessionId/sessionList）
.hermes-home/skills/storyboard-scene-generator/SKILL.md（改：修改模式）
```

## 9. Thinking 折叠块（模型推理展示）

- **数据来源**: Hermes messages 表的 `reasoning` / `reasoning_content` 字段（deepseek 按需产生推理，非每次调用都有）
- **转换层**: assistant 消息的 reasoning 字段 → 独立的 `reasoning` 消息（在 agent 文本之前）
- **前端**: `ReasoningBlock` 组件渲染为可折叠块（`▸ Thinking` / `▾ Thinking`），点击展开/收起
- **能力边界（实测确认）**: 真正的 reasoning 字段**不流式推送**（仅消息完成后存 messages 表）；`tool.progress` 事件携带的是 content 而非 reasoning，故实时流式思考不可得，仅历史回放可见

## 10. 流式文本合并

- Hermes `/chat/stream` 的 `assistant.delta` 事件以极细粒度（甚至半个词）推送文本
- 前端按「连续 text delta 合并为一条 agent 消息」处理：最后一条是 agent 则追加内容，否则新建
- 修复了「每段文字一行」的严重换行问题

## 11. session_created 即时更新

- 会话在生成**开始**（POST /api/sessions）时即创建，后端发 `session_created` 事件
- 前端收到后立即 `setCurrentSessionId` + 刷新列表 → 下拉框从 "New chat" 变为文件夹名，无需等生成完成

## 12. 键盘焦点守卫

- `BrowseControls`（WASD/QE 视角）、`FreeView`（Tab 切模式）、`SelectionControls`（W/E/Esc）均用 `window.addEventListener('keydown')` 全局监听
- 统一守卫：`event.target` 为 `INPUT` / `TEXTAREA` / `contentEditable` 时直接忽略
- 修复「聊天框打字影响自由视角移动」；`BrowseControls` 的 keyup 无条件清除，避免按键残留卡视角

## 13. 关键坑位记录

- **POST /api/sessions 返回 201 Created**（非 200），判断须 `in (200, 201)`
- **session_id 两类格式**: 手动 POST /api/sessions 返回 `api_时间戳_随机`；Hermes 自动建会话为 UUID
- **folder_name 兜底**: 二次修改定位输出文件夹优先用前端传的 `folder_name`（兼容无 session_id 的旧数据），不依赖 session_id 反查
