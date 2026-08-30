# V6 PRD — 相机轴增删 + 段拖动 + 固定时间轴范围

## Problem

V5 已能编辑/删除段、在轨道末尾加段，但编辑态仍缺三件事：

1. **不能增删相机轴（机位）**：一个聊天场景里相机对象是固定的，无法在编辑态新增一个机位或删掉一个机位。
2. **段不能拖动**：段的时间段（起点/终点）只能靠侧栏改 `End` 数值，无法在时间轴上直接拖动平移/改时长。
3. **时间轴没有固定范围**：刻度总长随段的最大 `end_time` 动态伸缩，没有「10 分钟总长度 + 有效时长指示」。

## User Stories

1. As a user, I want to add a new camera track in edit mode, so that I can introduce a new camera angle.
2. As a user, I want to delete a camera track (and its segments), so that I can remove an unwanted camera angle.
3. As a user, I want to drag a segment on the timeline to shift it or change its duration, so that I can retime shots visually.
4. As a user, I want the timeline to always show a fixed 10-minute range with the effective duration marked, so that I have a stable time reference.

## Solution

### 1. 相机轴增删（Segment Track）

- **新增相机轴**：时间轴底部「+ 相机」按钮 → 新建一个相机对象（机位）+ 空轨道 + 初始一段（3 秒）。新相机初始值全默认：原点位置、朝向零、无注视目标（interpolate）。新增后自动选中新相机 + 它的第一段。
- **删除相机轴**：每个相机轴标签旁「✕」按钮 → 删除相机对象 + 该相机的所有段 + 它专属的 aim_target（被其它相机共享的 aim_target 保留）。删除当前活跃相机后，活跃相机切到剩余第一个。
- **dirty**：增删相机都标记 dirty（操作过即可保存）。

### 2. 段拖动（Shift / Re-time / Trim）

段 block 支持三种拖动，受约束「不越界、不重叠」：

| 动作 | 触发 | 语义 |
|---|---|---|
| **Shift（平移）** | 拖段中间 | 起止点同时平移，时长不变（S/C 通用） |
| **Re-time（重定时）** | 拖 S 段两端边缘 | 首尾 pose 值不变、重新线性插值，速度变 |
| **Trim（裁剪）** | 拖 C 段两端边缘 | 裁掉范围外的采样帧，帧值/速度不变 |

拖动边界（同轴内）：

- 起点 ≥ 0；起点 ≥ 前一段终点、终点 ≤ 后一段起点（不重叠、不越相邻段）；
- 时长 ∈ `[1 帧, 原始时长]`；运动段（起点≠终点）缩到 1 帧接受「瞬移」。

C 段与 S 段行为一致，唯一区别：**C 段 Duration（原始时长）只读**（逐帧采样，加长需补帧无数据）。

### 3. 固定时间轴范围（Fixed Timeline Range）

- 编辑态时间轴刻度固定 **10 分钟（600s）**，段按 `end_time / 600` 比例排布；
- 有效总时长（段最大 `end_time`）用一条**竖线**标出，0～竖线区间做**浅色高亮**，之后到 10 分钟为空白区。

### 4. 详情面板时长块

`SegmentSidebar` 的 Duration 块改为四项：

```
Duration    [ 3.00s ]   ← 可编辑（原始时长上限；仅 S 段可改，C 段只读）
Start       [ 0.00s ]   ← 可编辑（起点）
End         [ 3.00s ]   ← 可编辑（终点，现有）
Effective   2.50s / 3.00s   ← 只读（当前有效时长 / 原始上限）
```

`Start`/`End`/拖动边缘是同一个值、双向联动；改数值同样受「1 帧 ~ 原始时长、不越界、不重叠」约束。

## Implementation Decisions（grill-me 结论）

| # | 决策点 | 结论 |
|---|---|---|
| 1 | 时间轴 10 分钟 | 全 600s 平铺，段按比例排布 |
| 2 | 片段滑动交互 | 整体平移 + 拖两端边缘，都要 |
| 3 | 拖动边界 | 时长 ∈ [1 帧, 原始时长]；运动段缩 1 帧瞬移接受 |
| 4 | 详情面板时长块 | `Duration` + `Start`/`End`（可编辑）+ `Effective`（只读） |
| 5 | Duration 权限 | S 段可改，C 段只读 |
| 6 | 新增相机初始值 | 全默认（原点/无注视/朝向零），初始一段 3s |
| 7 | 删除相机范围 | 相机 + 所有段 + 专属 aim_target（共享保留） |
| 8 | 增删相机入口 | 按钮：轴标签旁「✕」删、底部「+ 相机」增 |
| 9 | 有效时长指示 | 竖线 + 0～有效时长高亮 |
| 10 | C 段滑动 | 与 S 段一致（平移 + 拖边缘），仅 Duration 只读 |
| 11 | dirty 语义 | 纯「操作过」标志：编辑操作置 1 → Save 可点；保存整份当前数据，不做 diff |

## Testing Decisions（seams）

1. **前端 store（单测）**：`shiftSegment` / `retimeSegment` / `trimSegment`（改 `start_time`/`end_time`，约束校验）；`addCamera` / `deleteCamera`；`ShotSegment.original_duration`。
2. **后端 `apply_edit.py`（模块层）**：新增相机（`_find_camera` 返回 None → 新建相机对象 + 段 + 约束）；删除相机（blend 有但 segments 无 → 删对象 + 专属 aim_target）；C 段 trim（`position_keyframes`/`rotation_keyframes` 裁到 `[start_time, end_time]`）。
3. **API 层**：`POST /api/shots/{hash}/edit`（复用，payload 里相机增删即触发后端增删）。
4. **前端组件层**：`EditTimeline`（固定 10 分钟 + 段拖动 + 相机增删按钮 + 有效时长标记）、`SegmentSidebar`（时长块四项）。

## Out of Scope

- 撤销/重做
- 拖拽 pose 编辑（重做）
- 中间空白区加段、段的复制/粘贴
- TRACK_TO 动态跟随（target 是移动模型）
- 相机参数编辑（FOV/景深）、预设运动类型、时间轴缩放
