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

## V5 — 手动编辑镜头 + 回存 blend ✅ 已完成

### V5 本期

1. **段的编辑、删除**：S 段可编辑（两 pose 编辑 + 约束编辑），C 段只查看 + 删除；编辑态 UI（顶栏「编辑」按钮 → 底部段轨道 + 侧栏 + 播放头）
2. **回存 blend**：编辑结果 → 后端 Blender 脚本改关键帧/约束 → 另存版本化 blend（`scene_vN.blend`，不覆盖，保留编辑历史）
3. **多 blend 切换**：当前聊天文件夹的 blend 列表 + 切换自动加载最新 + 手动切换
4. **存储层重构 + 上传源扁平化**：`exports/<hash>/` 回归纯渲染缓存（不再存 blend）；源 blend 统一——聊天源 `output/<folder>/`（scene_vN 版本化）、上传源 + 保存输出扁平 `upload_output/<时间戳>.blend`；`source` 字段统一（upload=file / chat=folder）；保存 = 新 blend 成为新源（二次编辑不丢）；缓存命中补回源文件

### V5 已知问题

1. ~~**编辑态与保存后不一致**~~ ✅ 已修复：多个根因——TRACK_TO 约束丢失（漏写 orientation_mode）、关键帧残留 BEZIER、C 段被简化（改逐帧复刻）、旧缓存缺 orientation_mode（前后端兜底）、follow/interpolate 段级混用（约束 influence 动画方案）、复杂段朝向 X/Y 互换（`rotation_euler` 按 intrinsic 读写但 Blender 求值是 extrinsic，多轴朝向翻车；保存/导出端对称改为 extrinsic `mathutils.Euler('XYZ')`）
2. ~~**片段类型误判**~~ ✅ 已修复（BEZIER 残留根因）
3. **手动拖动交互已移除**：曾实现拖相机箭头改 pose（`CameraEditControls`），但存在 bug——attach/切换段时误触发写回，把「播放头处的实时相机朝向」污染进段数据；本期已砍掉该组件调用，位置/朝向暂靠侧栏数值编辑，拖拽交互留待后续版本重做。
4. ~~**编辑模式切换清空聊天历史**~~ ✅ 已修复：ChatPanel 在编辑模式下被卸载（`{!editMode && <ChatPanel />}`），消息是 useState 本地状态、卸载即丢失；改为始终挂载 + CSS 隐藏（`(sidebarCollapsed || editMode) ? hidden`）。
5. ~~**重复选择同一聊天版本下拉消失**~~ ✅ 已修复：`loadShotIntoViewer` 清空 blendVersions，但同一聊天 export_hash 不变，App.tsx 依赖 export_hash 的 useEffect 不重新触发；改为清空后主动 `loadBlendVersions`。
6. ~~**版本下拉样式不统一**~~ ✅ 已修复：版本选择原为原生 `<select>`（浏览器默认样式），与聊天切换的 HistoryDropdown 风格不一致；新建 BlendVersionDropdown 自定义下拉，复用 HistoryDropdown 的 pill trigger + 深色 menu 样式。

### V5 扩展（本期不做，后续，按优先级）

**高（编辑刚需，最可能先做）**
1. 撤销 / 重做
2. 相机参数编辑（FOV / 景深）
3. 段的时间拖动
4. 拖拽 pose 编辑（重做：拖相机箭头改位置/朝向，修复 attach 误触发写回 bug）

**中（自然延伸）**
4. 删除相机轨道 / 新增相机轨道
5. 中间空白区域增加段（当前只在末尾加段）
6. TRACK_TO 动态跟随支持（target 是移动模型）
7. 预设运动类型（推近 / 拉远 / 摇 / 横移 / 环绕）
8. 段的复制 / 粘贴

**低（有了更好 / 复杂度高）**
9. 摄像机实时录制（手动操作相机，实时记录关键帧）
10. 逐帧关键帧编辑（复杂段）
11. 转场效果（淡入淡出，现在是硬切）
12. 时间轴缩放

## V6 — 相机轴增删 + 段拖动 + 固定时间轴范围 ✅ 已完成

1. **相机轴增删**：编辑态新增/删除机位——新增 = 全默认相机（原点/无注视/朝向零）+ 初始 3s 段；删除 = 相机对象 + 所有段 + 专属 aim_target（共享保留）
2. **段拖动**：整体平移（Shift）+ 拖两端边缘（S 段 Re-time 重定时 / C 段 Trim 裁剪），约束「起点≥0、不越相邻段、时长∈[1帧, 原始时长]、C 段不超出采样范围」
3. **固定时间轴范围**：编辑态时间轴固定 10 分钟总长度、按固定像素比例（1 秒=90px）横向滚动，有效总时长用竖线 + 高亮标出
4. **时长块**：`Duration`（原始时长上限，S 可改 / C 只读）+ `Start`/`End`（可编辑）+ `Effective`（只读）
5. 文档：docs/v6/{prd,plan,design,tasks}.md + CONTEXT.md 术语更新（Shift / Re-time / Trim / Segment Duration / Effective Duration / Fixed Timeline Range）

## V7 — 导出 MP4 + 导出 Blend ✅ 已完成

1. **Export 按钮**：顶部栏 Edit 和 Settings 之间，下拉 Export 1080p MP4 / Export 720p MP4 / Export Blend
2. **Export MP4**：后端 Blender 无头**异步**渲染（task_id + 轮询进度），每个相机「整段 min~max 连续 + 每段 start~end」，**分块渲染防卡死**（每块 ≤50 帧重启 Blender）+ 逐个合成，compositor CurveRGB S 曲线拉对比防灰蒙蒙，落到 `{folder_name}_{blend前缀名}` 文件夹（无 session 时 `{blend前缀名}`）；进度胶囊 + ✕ 取消（确认弹窗）+ 刷新恢复 + 重复导出拦截
3. **Export Blend**：复制当前 blend 到目标文件夹，文件名加 `{folder_name}_` 前缀（无 session 时原名）
4. **自定义弹窗**：ConfirmDialog（ui-design 规范）替换系统弹窗（停止导出确认 / 重复导出提示 / 删除相机 / 删除段）
5. 文档：docs/v7/{prd,plan,design,tasks}.md + CONTEXT.md 术语（Export / Full Shot Export / Segment Export / Blend Export / Chat Name / Blend Prefix）

## 后续候选（未排期）

- 多任务队列
- 更多 provider / 模型选择扩展
- 生成目录自动清理策略
- 会话自定义重命名 / 搜索过滤
