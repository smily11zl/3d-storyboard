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
  │     POST   /api/sessions/{id}/chat  （续接生成 = 二次修改）
  ├─ /api/generate             —— 现有生成（改造：关联 session_id）
  ├─ /api/generate/{id}/status —— 现有
  └─ /api/open-finder/{folder} —— macOS open 命令

Hermes API Server (8643, 内嵌)
  └─ /api/sessions 系列 + /v1/responses（底层）
```

## 2. 数据流

### 2.1 新建聊天 + 生成（首轮）

```
前端 [+ 新的聊天] → 空会话（内存态，不落盘）
前端提交描述 → POST /api/generate {description}
  后端创建任务（时间戳文件夹 + status.json）
  后端向 Hermes 发起生成（沿用 /v1/responses 或改造为 session 续接）
  Hermes 自动建 session（state.db）
  后端把 session_id 写进 status.json（映射）
  生成完成 → 前端加载场景 + 聊天记录（内存）
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
前端在历史会话发消息 → POST /api/sessions/{id}/chat {message}
  后端转发到 Hermes session 续接（SSE 流式）
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
- 生成链路改造: 后端拿到 Hermes session_id 后写回 status.json
- **兜底**: session.started_at（epoch 秒）转 `YYYYMMDD_HHMMSS` 与文件夹名精确匹配
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
    # 转发 DELETE（幂等）
    ...

@router.post("/api/sessions/{session_id}/chat")
async def continue_session(session_id: str, payload):
    # 续接生成（SSE 流式，复用现有 generate 的流式逻辑）
    ...
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
