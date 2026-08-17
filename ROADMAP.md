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

## V4 — 镜头序列（Shot Sequence）✅ 完成

**核心变化**：把「多相机并行」升级为「镜头段序列」。底层用统一的「段」模型，最终演进为「一个相机一个轨道」——段按相机分组，时间轴全局（最长内容总时长），相机纯手动切换。

### V4 本期：识别与切换（不做编辑）

1. **生成端 skill 改造**：AI 生成「相机对象 + 多段组合」
   - 每个镜头段 = 一个独立 animation clip（时间范围 = 镜头时长）
   - 简单运动 = 2 个关键帧 pose + 朝向 TRACK_TO（S，可编辑）；复杂运动 = 3+ pose 折线（C，自由）
   - 段之间时间首尾相接；一个相机对象可被多段复用；静止镜头 = 2 相同 pose 跨 N 秒
   - 单相机多段为默认；仅用户明确要多个独立视角才新建相机
2. **ShotSegment 数据结构**：镜头段契约（相机名 / 起止时间 / 起终点 pose / S-C 类型），前后端共用
3. **后端识别逻辑**：读相机 NLA strips → 提取段 → 分通道判定 S/C（位置/朝向各自判：约束 + 插值 + 去重值）→ 按 start_time 排序；TRACK_TO 等可重演约束归简单、约束元数据写入 sidecar
4. **前端 UI**：段列表按相机 optgroup 分组（一个相机一个轨道）+ S/C 标记 + 时间轴全局 + 纯手动切换
5. **状态可视化**：Free View 生效=蓝/未生效=红 + 选中=实线/未选中=虚线；Camera View 边框同色
6. **收尾修复**：段边界 1 帧 gap（start_time 减 1 帧）；切换聊天自动重转；下拉标签英文；生成超时 20 分钟

## V5 — 手动编辑镜头 + 导出新 blend 🔮 待排期

- **编辑简单段（S）**：从当前视角设相机 / TransformControls 拖拽相机 / 数值面板（位置·朝向·FOV）/ 两 pose 插值（缓动 + 起幅落幅停留）/ 约束编辑（改 TRACK_TO 目标，前端 lookAt 重演朝向）/ 硬切·连续衔接
- **高级运动**：预设运动类型（推近/拉远/摇/横移/环绕）/ 逐帧关键帧
- **导出**：前端编辑结果 → JSON → 后端 Blender 应用 → 存为新 blend（新时间戳文件夹）

## 后续候选（未排期）

- 多任务队列
- 更多 provider / 模型选择扩展
- 生成目录自动清理策略
- 会话自定义重命名 / 搜索过滤
