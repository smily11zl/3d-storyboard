# ROADMAP — Storyboard 3D Pipeline

## V1 — Web Shot Viewer ✅ 已完成

- .blend 上传 → 无头 Blender 转 glTF（hash 去重 + 磁盘配额）
- 双视口查看器: 摄像机视图（锁定机位 + 下拉切换）/ 自由视图（轨道控制）
- 共享时间轴动画播放（播放/暂停/拖动/Space）
- 人物选择与变换（编辑模式: 移动/旋转手柄，双视口同步）
- 浏览模式（WASD 走位视角 + 方位/俯仰角显示 + XYZ 旋转球）
- 摄像机线框指示（半透明锥体 + 缩短视锥）
- 本地环境光（无 CDN 依赖）、灯光归一化/移除（无硬阴影）
- Spotify 暗色 UI（ui-design/DESIGN.md）
- 文档: docs/v1/spec.md、docs/architecture.md、README.md

## V2 — AI 场景生成（Hermes 集成）✅ 完成

- ✅ 切片 01: 内嵌 Agent 环境 + API Server 启动（assets/.hermes-home/skill/start.sh 三进程）
- ✅ 切片 02: 后端设置接口 + key 验证（settings API + agent_service + DeepSeek 验证，16/16 测试）
- ✅ 切片 03: 生成任务核心链路（提交/SSE/导出衔接/失败/取消/超时，24/24 测试 + 真实失败路径验证）
- ✅ 切片 04: 前端页面结构（TopBar/Sidebar/SettingsModal + App 重组，浏览器验证通过）
- ✅ 切片 05: 前端生成交互（ChatPanel 聊天 + SSE 流式 + 失败/重试/停止，浏览器验证通过）
- ✅ 切片 06: 验证与收尾（26/26 测试 + 真实生成全链路验证 + README/.gitignore）
- 文档: docs/v2/{prd,design,plan,tasks}.md

## V3 — 候选（未排期）

- 多任务队列 / 生成历史列表与场景库
- 连续会话（基于当前场景增量修改）
- 更多 provider / 模型选择扩展
- 生成目录自动清理策略
