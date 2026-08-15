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

## V3 — 多会话历史 ✅ 已完成

- 复用 Hermes `/api/sessions` 存储（历史列表 / 消息 / 删除 / 续接）
- 历史下拉框（标题旁）+ 顶部"新的聊天" + 删除 + 打开 Finder
- 二次修改（增量：改 script.py 重新生成，覆盖同文件夹）
- 会话 ↔ 文件夹名映射（status.json session_id + 时间戳容差兜底 + folder_name 直传）
- 思考过程展示（Thinking 折叠块，历史 reasoning 字段还原）
- 交付后修复：201 会话创建 / 流式文本合并 / 下拉框即时更新 / 键盘焦点守卫
- 文档: docs/v3/（prd / design / plan / tasks）
- 切片进度: 阶段 1-5（见 docs/v3/tasks.md）

## 后续候选（未排期）

- 多任务队列
- 更多 provider / 模型选择扩展
- 生成目录自动清理策略
- 会话自定义重命名 / 搜索过滤
