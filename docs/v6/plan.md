# V6 Plan — 相机轴增删 + 段拖动 + 固定时间轴范围

## 决策记录（grill-me + grill-with-docs）

术语已同步进 `CONTEXT.md`：新增 `Segment Shift` / `Re-time` / `Trim` / `Segment Duration` / `Effective Duration` / `Fixed Timeline Range`；更新 `Segment Track`（可增删）、`Static Target`（每段独立）。

| # | 决策点 | 结论 |
|---|---|---|
| 1 | 时间轴 | 固定 600s 平铺，段按比例，有效时长竖线+高亮 |
| 2 | 滑动 | 整体平移 + 拖边缘，都要 |
| 3 | 边界 | 时长 ∈ [1帧, 原始时长]；运动段 1 帧瞬移接受 |
| 4 | 时长块 | Duration + Start/End（可编辑）+ Effective（只读） |
| 5 | Duration | S 可改、C 只读 |
| 6 | 新增相机 | 全默认（原点/无注视/朝向零）+ 初始 3s 段 |
| 7 | 删除相机 | 相机 + 所有段 + 专属 aim_target（共享保留） |
| 8 | 入口 | 轴标签旁「✕」删、底部「+ 相机」增 |
| 9 | 有效时长 | 竖线 + 0～有效时长高亮 |
| 10 | C 段滑动 | 同 S，仅 Duration 只读 |
| 11 | dirty | 纯「操作过」标志，保存整份当前数据，不做 diff |

## 实现计划

### 前端 store（`store.ts` / `types.ts`）

1. `types.ts`：`ShotSegment` 加 `original_duration?: number`（原始时长上限）。
2. `buildEditingSegments`：进入编辑态时，为每段写入 `original_duration = end_time - start_time`。
3. `addSegment`：新增段同时继承/初始化 `original_duration`。
4. 新增 `addCamera`：新建相机对象（命名 `cam_0N` 顺延）+ 一个初始段（默认 3s、全默认 pose、interpolate、`original_duration = 3`）。
5. 新增 `deleteCamera`：删除该相机的所有段 + 专属 aim_target 的标记（共享判断交给后端/保存时）。
6. 新增段拖动 action：`shiftSegment`（整体平移）/ `retimeSegment`（S 段改时长）/ `trimSegment`（C 段裁帧），统一走一个内部约束函数 `clampSegmentTimes`（起点≥0、不越相邻段、时长∈[1帧, original_duration]）。
7. 所有编辑 action 统一置 `dirty: true`。

### 前端组件

8. `EditTimeline`：
   - 时间轴刻度固定 600s（`duration` 常量），段按 `end_time / 600` 排布；
   - 有效时长竖线 + 0～有效时长高亮；
   - 段 block 三档拖动（中段 Shift、边缘 Re-time/Trim，按 `segment_type` 分派）；
   - 每个相机轴标签旁「✕」删除按钮 + 底部「+ 相机」按钮。
9. `SegmentSidebar`：Duration 块四项（Duration 可编辑仅 S / Start / End / Effective 只读），与拖动双向联动。
10. `EditToolbar` / `saveEdit`：dirty 保持「操作过」语义（不砍，但确认所有编辑 action 都置 dirty）。

### 后端（`apply_edit.py` / `edit_operations.py`）

11. `apply_full_segments`：
    - **新增相机**：`_find_camera` 返回 None → 新建相机对象（含段 + 约束；若 follow 则新建专属 aim_target）；
    - **删除相机**：blend 有但 segments 无的相机 → 删除对象 + 专属 aim_target（共享的 aim_target 保留）；
    - **C 段 trim**：`position_keyframes`/`rotation_keyframes` 按 `[start_time, end_time]` 裁帧后再写回。
12. `edit_operations.py`：无需结构改动（segments 已含 `camera_name`），必要时补相机名校验。

## 切片顺序（供 to-issues 拆票参考）

1. 前端 store：`original_duration` + 段拖动 action（约束）+ 单测（先 S 后 C）
2. 前端组件：时间轴固定 600s + 有效时长标记 + 段拖动 UI
3. 前端组件：时长块四项（SegmentSidebar）
4. 前端 store：`addCamera` / `deleteCamera` + 增删按钮 UI
5. 后端：相机增删 + C 段 trim（`apply_full_segments`）
6. 收尾：dirty 全覆盖检查 + 端到端验证
