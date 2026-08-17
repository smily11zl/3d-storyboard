# V4 PRD — 镜头序列（Shot Sequence）

状态: 草案（待确认）
日期: 2026-08-16

## Problem Statement

现在生成的场景里，多个相机（机位）是**并行**存在的：它们同时存在于场景中、各自的动画同时播放，用户只能通过下拉框手动切换「看哪台相机」。这无法表达「分镜（storyboard）」的核心需求——**镜头按时间顺序排列成一条序列**（镜头1 播完接镜头2，镜头2 播完接镜头3），也无法自动播放这条序列，更无法区分「哪些镜头段是简单运动、将来可手动编辑」。

用户想要 V4 的核心：把「多相机并行」升级为「镜头段序列」，让镜头按时间顺序组织、可自动播放、可切换识别出的不同镜头段（并标记哪些段将来可编辑）。编辑与导出留到 V5。

## Solution

引入统一的「镜头段（Shot Segment）」模型作为底层：

- 每个镜头段 = 一个相机对象 + 一个时间区间 + 一段运动（起终点 pose + 缓动 + 起幅落幅停留）
- 统一「一个相机一个轨道」：段按相机分组，轨道内段按时间排序；不同相机轨道可时间重叠（并行）

三个环节：

1. **生成端（skill）**：让 AI 生成「相机对象 + 多段组合」——每段独立 animation clip、简单运动 2 pose / 复杂运动 3+ pose、段之间时间首尾相接不重叠、一个相机对象可被多段复用
2. **识别端（后端）**：导入时自动识别「驱动相机的动画 = 镜头段」，按 pose 数标 S/C，按时间重叠判序列/并行
3. **展示端（前端）**：一级段列表（段自带相机名 + 时间）+ 自动序列播放 + 旧并行 blend 走多轨道

## User Stories

1. As a user generating a scene, I want the AI to produce a **sequence of shot segments** (ordered on one timeline) rather than parallel cameras, so that I get an ordered series of shots like a storyboard.
2. As a user, I want the AI to **reuse one camera object across multiple segments**, so that the same camera position can appear in different shots without duplicating the camera.
3. As a user, I want simple camera motions (static / push / pull / pan / orbit) generated as **2-pose segments**, so that these segments are recognizable as editable later.
4. As a user, I want complex camera motions generated as **3+-pose segments**, so that free/composite movements are kept and distinguishable from simple ones.
5. As a user, I want **still shots to have an explicit duration** (not zero-length), so that a still shot occupies N seconds on the timeline before switching to the next shot.
6. As a viewer, I want the app to **automatically identify shot segments** from an imported blend, so that I don't have to manually mark them.
7. As a viewer, I want each segment **tagged S (simple/editable) or C (complex/free)**, so that I can tell at a glance which segments will support manual editing later.
8. As a viewer, I want segments **grouped by camera into tracks** (one camera = one track), so that the shot structure is organized by camera regardless of time overlap.
9. As a viewer, I want to see a **flat list of shot segments** (each showing its camera name and time range), so that I can understand the shot structure at a glance.
10. As a viewer, I want to **click a segment to jump to it**, so that the viewport switches to that segment's camera and jumps the playhead to its start time.
11. As a viewer, I want the timeline to **play on one global timeline** (length = longest content), so that all segments play in time order without the timeline changing when I switch cameras.
12. As a viewer, I want to **switch cameras manually** (default to the first camera on load), so that camera changes only happen when I explicitly pick a segment.

## Implementation Decisions

### 领域模型

- **相机对象（Camera Object）**：场景里的相机实体（位置/朝向/FOV）。通常一个相机承载多段运动
- **镜头段（Shot Segment）**：时间轴上的区间，引用一个相机对象 + 定义运动。一个段只引用一个相机
- **关系**：段 → 引用 → 相机（多对一）。通常一个相机承载全部段；需要切换视角时才引入多个相机（机位复用）

### ShotSegment 数据结构（前后端契约）

```
ShotSegment {
  camera_name: string,      // 引用的相机对象名
  start_time: number,       // 秒
  end_time: number,         // 秒
  start_pose: { position: [x,y,z], quaternion: [x,y,z,w] },
  end_pose:   { position: [x,y,z], quaternion: [x,y,z,w] },
  segment_type: "S" | "C",  // S=简单(可编辑) / C=复杂(自由)
}
```

ShotMetadata 增加 `segments: ShotSegment[]` 字段。段的时间位置（首尾相接 vs 重叠）由段的 start_time/end_time 自然表达，不再需要单独的 timeline_mode 标记。

### 识别逻辑（两段式）

**阶段 1 — Blender 脚本（export_shot.py 扩展）读 NLA strips：**
- 遍历相机的 NLA tracks（每段一个 track）→ 提取每段：相机名、绝对起止时间（strip frame_start/end）、action 名
- 分析每个 action 的关键帧 pose 数：去重后 ≤2 → S，>2 → C
- 写入 `segments.json` sidecar（含绝对时间 + S/C）

**阶段 2 — 后端读 sidecar 组装：**
- 读 segments.json → 组装 ShotSegment 列表
- 段按 start_time 排序返回（轨道分组由前端按 camera_name 完成）
- 无动画的相机：进素材池（本 V4 不单独展示，作为段的引用来源）

**为何要 sidecar（关键验证结论）**：glTF 导出会丢失 NLA strip 的绝对时间偏移（只保留 action 的相对时长），所以「段在时间轴上的绝对位置」必须由 Blender 脚本在导出时从 NLA strips 读出并写进 sidecar，不能靠读 glTF 还原。

**S/C 判据的准确表述**：S（简单）= 恰好能用「2 个 pose + LINEAR/CUBICSPLINE 缓动」无损表达；C（复杂）= 做不到这点的（多关键帧 / Back·Bounce·Elastic 特殊缓动 / Follow Path·Track To 等约束 / 复杂贝塞尔曲线）。由于 glTF 仅支持 LINEAR/STEP/CUBICSPLINE，特殊缓动和约束导出时会被采样/烘焙成密集关键帧，所以**凡是 C，导出到 glTF 后必然表现为「去重后 pose 数 > 2」**——用 pose 数判断不会漏。

### 生成端 skill 约定（强约束）

- **每段一个独立 Action**：一个镜头段 = 一个 Action，命名清晰（如 `seg_01_push`）
- **每段一个独立 NLA track**：每个段用一条独立 NLA track（一个 track 只放一个 strip）。**禁止一个 track 塞多个 strip**（实测：会导致 glTF 导出 0 个动画）
- 简单运动 = 2 个关键帧 pose + 缓动（LINEAR / CUBICSPLINE）；复杂运动 = 3+ pose
- 静止镜头 = 2 个相同 pose 跨 N 秒（有明确时长）
- 段之间时间首尾相接、互不重叠
- 一个相机对象可被多段复用（多段 = 挂同一相机对象的多个 NLA track）

### 前端 UI

- **一级段列表**（替代现有相机下拉框）：按相机 optgroup 分组（一个相机一个轨道），每项显示 `相机名 + Shot N + S/C + 起止时间`
- **时间轴全局**：时长 = 最长内容总时长，选择相机只切视角不改时长
- **手动切换**：加载后默认第一个相机，用户下拉框选段才切（无自动切换）
- **状态可视化**：Free View 生效=蓝/未生效=红 + 选中=实线/未选中=虚线；Camera View 边框同色

### 插值类型约束

- glTF 仅支持 LINEAR / STEP / CUBICSPLINE
- 可编辑段（S）的插值 = LINEAR 或 CUBICSPLINE（匀速 / 缓动）
- 起幅落幅停留 = 重复关键帧（不增加 pose 数）；缓动 = 切线（CUBICSPLINE，不增加 pose 数）

## Testing Decisions

- **Seam 1（核心）**：后端纯函数 `parse_segments_sidecar(sidecar_json) → ShotSegment[]`，单元测试用 mock sidecar 覆盖：单段透传、相邻段、重叠段保留、空段、乱序按 start_time 排序
- **Seam 2（API 契约）**：`ShotMetadata.segments` 字段，集成测试验证真实 blend → metadata.segments 正确
- **测试原则**：只测外部行为（组装结果正确），不测实现细节（sidecar 解析内部步骤）
- **非自动化**：Blender 脚本读 NLA strips（阶段 1）和 skill 改动，通过手动生成验证（blend 结构 + sidecar 正确性）

## Out of Scope

- **手动编辑镜头段**（拖拽相机 / 两 pose 插值 / 数值面板 / 预设运动）→ V5
- **导出新 blend**（编辑结果写回 .blend）→ V5
- **逐帧关键帧编辑** → V5
- **预设运动类型**（推/拉/摇/移/环绕的下拉预设）→ V5
- **手动把并行 blend 转成序列**（多轨道重排）→ 后续

## Further Notes

- 术语见 CONTEXT.md（Shot Segment / Pose / S-C / Sequence / Parallel / Hold / Easing）
- 现有 `Shot`（完整场景）与 `Shot Segment`（镜头段）是两个不同概念，命名上注意区分
- 段的「起终点 pose」用 quaternion 存储（与 glTF 节点变换一致）
- 相机切换为纯手动：加载后默认第一个相机，用户下拉框选段才切；时间轴始终全局（最长内容总时长）

### 已验证结论（NLA 实测）

1. **每段一个独立 NLA track 可行**：一个相机 + 多个 Action + 每段一个 track → glTF 导出多个独立 animation（段边界透传 ✅）
2. **一个 track 塞多个 strip 不行**：导出 0 个动画 + 警告（"only single-strip tracks supported"）→ 必须每段一个 track
3. **glTF 丢失绝对时间偏移**：strip 的 frame_start 偏移不导出，glTF animation 只有相对时长 → 段的绝对起止时间必须靠 sidecar 补救
4. **现有 AI 生成的 blend**：一个相机一个 Action（命名 `相机名+动作`），完全没用 NLA → skill 必须明确教「每段一个 Action + 每段一个 NLA track」
