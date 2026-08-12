# V2 PRD — AI 场景生成（Hermes 集成）

状态: 已确认（grill-me 16 项 + grill-with-docs 12 项）→ ✅ 已实现（2026-08-13）
日期: 2026-08-01

## 1. 背景与目标

V1 提供 .blend 上传 → glTF 转换 → 双视口查看。用户仍需在 Blender 里手工搭建场景。
V2 引入 AI 生成：用户输入场景描述，项目内嵌的 Hermes Agent（作为开源引擎打包进项目）
按项目 skill 自动生成带多机位的 .blend，自动转换并展示——项目对使用者完全自包含，
使用者只配置一个 API key。

## 2. 用户故事

- 作为分镜创作者，我在 Web UI 输入"两个人在咖啡店对话"，系统自动生成 3D 场景并展示
- 作为使用者，我只需要配置 DeepSeek API key，不需要了解 Hermes
- 作为维护者，我修改项目 skill 文件即可改变生成流程与输出，不改代码

## 3. 功能规格

### F1 页面结构

- 顶部栏: 产品名 / 侧边栏展开收起按钮 / 设置入口(⚙)
- 左侧边栏: 两个选项 — "直接上传"(现有流程) / "AI 生成"
- AI 生成激活时侧边栏变为聊天样式（含返回按钮）: 输入框 + 生成过程流式日志
- 主内容区: 现有查看器（双视口/时间轴/摄像机切换/人物编辑），结构不变
- 生成中查看器保持上次场景；无场景时提示"生成或提交后可查看"
- 生成完成自动替换当前场景（查看器 = 当前场景，无多场景历史）

### F2 设置（设置弹窗）

- 配置项: Provider（V2 首版锁定 DeepSeek）/ 模型（deepseek-v4-flash / deepseek-v4-pro）/
  推理级别（low / high / max）/ API key
- key 验证: 后端直接调 DeepSeek 官方 API（GET /v1/models，带 key），200 才保存
- 保存: 写入 .hermes-home/.env（key）+ config.yaml（模型/推理级别），
  随后自动重启 Hermes API Server 使配置生效
- 已配置后重开显示掩码 key，可修改

### F3 生成流程

1. 用户输入描述 → POST /api/generate（后端创建任务: 生成输出目录 + status.json）
2. 后端向 Hermes API Server 发起请求:
   固定指令前缀 + "输出 .blend 到: {本次目录}/scene.blend" + 用户描述
   （所有指令内容在 skill 中，后端只有固定前缀）
3. SSE 流式转发 Hermes 输出到前端聊天界面（完整流式日志）
4. Hermes 完成后: 后端调现有 export_shot.py 转 glTF（失败自动重试 1 次）
5. 成功: status.json=done（携带 shot 元数据: gltf URL/机位/动画/时长）
   → 前端自动加载展示；失败: status.json=failed + 错误 + 重试按钮
6. 取消: 前端"停止" → POST /api/generate/{id}/stop
   （cancel_event 终止任务 + 清理残留 blender 进程，按命令行含本次输出目录匹配 kill）
   → status.json=cancelled
7. 超时: 后端总超时 10 分钟 → status.json=failed("生成超时") + 残留清理
8. 生成中禁止再次提交（前端按钮置灰 + 后端 409）
9. 状态查询: GET /api/generate/{id} 返回 status.json（任务完成后可查）

**SSE 断连语义（实现约定）:** 客户端断开连接**不取消任务**——任务继续运行，
浏览器 EventSource 会自动重连并续收剩余事件；若任务已结束，前端查询状态端点收尾。
取消只走显式的停止按钮（避免网络抖动误杀生成）。

### F4 生成产物管理

- 目录: generate/output/<时间戳>/（一次生成 = 一个自包含文件夹）
  - scene.blend / script.py（Hermes 中间文件）/ generation.log / status.json
  - 可能含: preview_*.png（机位自检预览图）/ selfcheck.py（agent 自检脚本）
- status.json 状态机: running → done(带 shot 元数据) / failed(带 error) / cancelled
- done 状态的 shot 字段 = 导出后的场景元数据（export_hash / gltf_output_url /
  cameras / animations / duration_seconds），前端据此加载场景
- 中间文件约定: skill 规定所有中间文件放本次目录内
- 取消后保留目录（不删除半成品，无自动清理；后续迭代加）

### F5 Hermes 内嵌环境

- .hermes-home/（项目独立 HERMES_HOME）: config.yaml（预置）/ skills/ / .env（key）
- config.yaml 预置: platforms.api_server.enabled=true + extra.port=8643
- skill: .hermes-home/skills/storyboard-scene-generator/（V2 定制版，git 管理）
  - 基于现有 test/.hermes/skills/storyboard-scene-generator/ 定制
  - 更新: 资产路径 → assets/characters/；输出约定 → 单场景多机位 .blend；
    指令约定 → 输出目录由后端运行时传入；中间文件收本次目录
- 使用者机器无需安装/了解 Hermes（hermes-agent 为 pip 依赖，HERMES_HOME 指向项目）
- 与用户本地 Hermes 完全隔离（HERMES_HOME 不同 + 端口 8643 错开）
- **启动隔离（实现补充）:** 本地 Hermes 是 launchd 服务，会注入 WEIXIN_* 等环境变量
  到所有 shell → 项目 gateway 继承后会误加载微信平台被安全策略拦截。
  start.sh 用 `env -i`（仅保留 PATH/HOME/HERMES_HOME/LANG）+ `--force`
  （绕过 launchd 的"已有 gateway"保护，该项目环境与本地环境不同，安全）启动 agent。

### F6 资产

- assets/characters/: male/female/child_mixamo_stand.fbx（从 test/characters/ 复制）
- test/ 保持测试专用不动

### F7 启动

- start.sh 统一管理三进程: 前端(5173) / 后端(8000) / Hermes API Server(8643)
- 后端负责 API Server 健康检查（崩溃自动重启）

## 4. 非功能需求

- 生成总超时 10 分钟（后端兜底）
- API Server 仅监听 localhost
- 磁盘: 生成目录不自动清理（V2 首版），.gitignore 排除 .hermes-home/.env 与 generate/
- 并发: 同时只允许一个生成任务（前端限制）

## 5. 测试策略

- 自动化: mock Hermes API Server 响应，覆盖设置读写/验证、生成提交/取消/超时/
  状态机/导出衔接（pytest + httpx，沿用 V1 结构）— **26/26 全绿**（V1 回归 10 + V2 16）
- 手动集成验证清单: 真实生成一次 ✅（skill 四步流程 / 双机位 / 自动导出 / 前端展示）
- 前端: 构建验证 + 手动交互验证

## 6. 实现期发现并修复的问题（集成教训）

- **Hermes 错误事件是 `response.failed`**（错误在 `response.error.message`），
  不是 error 字段——解析后失败信息精确可用
- **SSE 断连误取消** → 改为仅显式 stop 取消（见 F3 断连语义）
- **asyncio.run 嵌套**（FastAPI 事件循环内调用）→ export_scene 改 async/await 链
- **camera 命名**（重要）: glTF 摄像机节点名 = Blender object 名（如 cam_01_front），
  metadata 必须取节点名而非相机数据块名（默认"摄像机"）——名字不一致会导致
  前端按名字找不到节点 → 机位切换/动画跟随失效
- **skill 时间预算**: 生成 agent 容易过度自检（像素级分析）拖垮任务 → skill 内
  显式"8 分钟预算 + 禁止像素级验证"，只保留点积机位方向验证

## 7. 范围外（后续迭代）

- 多任务队列、生成历史列表与场景库、模型下拉扩展、取消目录自动清理、
  连续会话（基于当前场景修改）、更多 provider
