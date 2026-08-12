# V2 Design — AI 场景生成架构

## 1. 架构总览

```
┌─────────────────────────────────────────────────────────┐
│ 浏览器 (React)                                          │
│  TopBar / Sidebar / ChatPanel / SettingsModal / 查看器   │
└───────────────┬─────────────────────────────────────────┘
                │ HTTP / SSE
┌───────────────▼─────────────────────────────────────────┐
│ FastAPI 后端 (8000)                                     │
│  · 现有: POST /api/shots, GET /api/shots/{hash}         │
│  · V2:   POST /api/generate                             │
│         GET  /api/generate/{id}  (status.json 查询)     │
│         GET  /api/generate/{id}/stream (SSE)            │
│         POST /api/generate/{id}/stop                    │
│         GET/POST /api/settings                          │
│  · agent_service.py — Hermes API Server 客户端          │
│  · export_shot.py — 现有 .blend→.gltf 转换（复用）       │
└───────┬───────────────────────────────┬─────────────────┘
        │ HTTP (OpenAI 兼容 + SSE)       │ subprocess
┌───────▼──────────────┐    ┌───────────▼─────────────────┐
│ Hermes API Server    │    │ Blender 无头 (export_shot)   │
│ (8643, HERMES_HOME=  │    │ 生成目录 → exports/<hash>/    │
│  .hermes-home/)      │    │ (glTF 静态服务)              │
│  · skill 加载         │    └─────────────────────────────┘
│  · agent 执行生成     │
└──────────────────────┘
```

## 2. 进程生命周期

- start.sh 启动: 前端 (vite 5173) → 后端 (uvicorn 8000) → Hermes API Server (8643)
- 后端启动时对 8643 做健康检查（GET /health），失败自动拉起
- 设置保存 → 写配置 → 重启 API Server（kill + 拉起）

## 3. 生成请求数据流

```
1. 前端 POST /api/generate {description}
2. 后端:
   - 生成输出目录 generate/output/<YYYYMMDD_HHMMSS>/
   - 写 status.json = running
   - 向 Hermes POST /v1/responses (SSE):
     system: "按 storyboard-scene-generator skill 执行，
              输出 .blend 到 {目录}/scene.blend"
     user:   {description}
   - 返回 task_id（= 时间戳目录名）
3. 前端 GET /api/generate/{id}/stream → 后端转发 Hermes SSE 事件
   （response.output_text.delta → 聊天文本；tool.start|progress|complete → 工具块；
     response.failed → 生成失败（错误在 response.error.message））
4. Hermes 完成 → 后端校验 scene.blend 存在
5. 调 export_shot.py 转 glTF（失败自动重试 1 次）
6. 成功 → status.json=done（携带 shot 元数据: export_hash/gltf_output_url/
   cameras/animations/duration）→ 前端自动加载场景
   失败 → status.json=failed + error → 前端错误 + 重试按钮
7. 取消 → POST /stop → cancel_event 终止任务
   + 扫描 blender 进程（命令行含本次目录）kill
   → status.json=cancelled
8. 超时 10 分钟 → status.json=failed("生成超时") + 残留清理
9. 状态查询 → GET /api/generate/{id}（返回 status.json，完成后可查）

SSE 断连不取消任务（EventSource 自动重连续收；取消只走 stop 端点）。
```

## 4. 目录结构（V2 增量）

```
.hermes-home/                    # Hermes 独立环境（HERMES_HOME）
├── config.yaml                  # api_server 8643 / 模型 / reasoning 级别
├── .env                         # DEEPSEEK_API_KEY + API_SERVER_KEY（gitignore）
└── skills/storyboard-scene-generator/
    └── SKILL.md                 # V2 定制 skill（git 管理）
assets/characters/               # 3 个 Mixamo FBX（从 test/ 复制）
generate/output/<时间戳>/
├── status.json                  # 状态机（done 携带 shot 元数据）
├── scene.blend                  # Hermes 产物
├── script.py                    # Blender 脚本（中间文件）
├── generation.log               # 失败日志
└── preview_*.png                # 机位自检预览图（agent 生成，可能无）
exports/<sha256>/                # glTF 导出缓存（前端静态服务）
└── scene.gltf / scene.bin / shot_metadata.json
```

## 5. 关键设计决策

| 决策 | 选择 | 理由 |
|------|------|------|
| Hermes 集成 | API Server (HTTP+SSE) | 官方 Web 集成接口，流式进度，与后端解耦 |
| 环境隔离 | HERMES_HOME=项目/.hermes-home | 使用者零配置认知，与本地 Hermes 互不影响 |
| 端口 | 8643（可配） | 与本地 Hermes 默认 8642 错开 |
| 行为定义 | 全部在 skill | 用户改 skill = 改生成行为，代码零改动 |
| 输出路径 | 后端运行时传入 | 后端能精确定位产物转 glTF |
| 状态管理 | status.json | 统一状态机，支撑后续历史/清理功能 |
| 模型设置 | 写入 config.yaml + 重启 API Server | Hermes reasoning 配置会话启动时固定 |
| 工具 | agent_service.py 封装 Hermes 客户端 | 测试可 mock，与 main.py 解耦 |
| SSE 断连 | 不取消任务 | 网络抖动不误杀生成；EventSource 重连续收 |
| 摄像机命名 | metadata 取 glTF 节点名（= object 名） | 数据块名（默认"摄像机"）与节点名不一致时前端找不到节点 |
| skill 自检 | 只做点积机位方向验证 + 8 分钟预算 | 像素级自检拖垮任务导致超时 |

## 6. 安全与隔离

- API Server 仅监听 127.0.0.1
- .hermes-home/.env 与 generate/ 进 .gitignore
- DeepSeek key 只存项目内 .env，不落日志
- 取消/超时主动清理 blender 残留进程（按输出目录匹配，不误杀）
