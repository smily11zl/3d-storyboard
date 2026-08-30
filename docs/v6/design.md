# V6 Design — 技术规格

## 数据结构

### `ShotSegment` 扩展

```ts
interface ShotSegment {
  // ...现有字段
  /** 原始时长（秒）：进入编辑态那刻的 end_time - start_time，拖动时长的上限。S 段可改，C 段只读。 */
  original_duration?: number;
}
```

### 相机增删契约

前端不维护独立相机列表——相机轴列表 = `editingSegments` 里 `camera_name` 去重 + `shot.cameras`（无段相机补虚拟段）。保存时，后端以「segments 的 camera_name 集合」和「blend 里的相机集合」的差集识别增删：

- **新增**：`camera_name ∈ segments 且 ∉ blend` → 新建相机对象；
- **删除**：`camera_name ∈ blend 且 ∉ segments` → 删除相机对象 + 专属 aim_target。

## 前端 store action

```ts
// 相机轴
addCamera(): void
  // 新建 cam_0N（N 顺延）+ 一个初始段（3s、position [0,0,0] rotation [0,0,0]、
  //   orientation_mode 'interpolate'、original_duration 3、segment_type 'S'）
deleteCamera(cameraName: string): void
  // 删除该 camera_name 的所有段；活跃相机若被删则切到剩余第一个

// 段拖动（统一约束入口 clampSegmentTimes）
shiftSegment(cameraName: string, segmentName: string, deltaTime: number): void
  // 整体平移：start_time/end_time 同时 +delta，时长不变
retimeSegment(cameraName: string, segmentName: string, which: 'start'|'end', newTime: number): void
  // S 段拖边缘：只改 which 一端，pose 值不变（速度变）
trimSegment(cameraName: string, segmentName: string, which: 'start'|'end', newTime: number): void
  // C 段拖边缘：改 which 一端 + 裁掉范围外的 position_keyframes/rotation_keyframes
```

### 约束算法 `clampSegmentTimes`

对目标段（同 `camera_name` 内）计算合法 `[newStart, newEnd]`：

1. `newStart = max(newStart, 0)`；
2. `newStart = max(newStart, 前一段.end_time)`（若存在前一段）；
3. `newEnd = min(newEnd, 后一段.start_time)`（若存在后一段）；
4. 时长下限 `1/fps`（1 帧），上限 `original_duration`：若 `newEnd - newStart > original_duration` 则收窄到 `original_duration`（保持拖动的那一端不动，另一端回退）；若 `< 1/fps` 则收到 `1/fps`。

所有拖动/增删统一置 `dirty: true`。

## 前端组件

### `EditTimeline`

- `TIMELINE_TOTAL = 600`（10 分钟）常量，取代动态 `duration` 参与段 `left`/`width` 百分比计算；
- 有效总时长 `effectiveEnd = max(segments.end_time)`，画一条竖线 + 0～`effectiveEnd` 浅色高亮；
- 段 block 三档命中区：左边缘（拖起点）、右边缘（拖终点）、中段（平移）；`segment_type === 'C'` 时边缘拖走 `trimSegment`，否则 `retimeSegment`；
- 相机轴标签旁「✕」按钮 → `deleteCamera`（弹窗确认）；轨道区底部「+ 相机」按钮 → `addCamera`。

### `SegmentSidebar` Duration 块

```
Duration   [number]  ← S 可编辑（改 original_duration），C 只读
Start      [number]  ← 可编辑（改 start_time，走 retime/trim 约束）
End        [number]  ← 可编辑（改 end_time）
Effective  "x.xxs / y.yys"  ← 只读（end-start / original_duration）
```

## 后端 `apply_edit.py`

### 新增相机（`apply_full_segments` 内，`_find_camera` 返回 None 时）

1. `bpy.ops.object.camera_add(...)` 新建相机，命名 `camera_name`；
2. 若该相机任一 follow 段有 target 名且目标不存在 → 新建专属 Empty 作为 aim_target；
3. 正常走 `_rebuild_constraints` + `_rebuild_segment`。

### 删除相机（`apply_full_segments` 内，清空后）

1. 收集 blend 所有相机名；对「blend 有但 segments 无」的相机：
2. 若它独占某个 aim_target（无其它相机引用）→ 删除该 Empty；
3. 删除相机对象。

### C 段 trim（`_rebuild_segment` 写回前）

`position_keyframes`/`rotation_keyframes` 按 `keyframe.time ∈ [start_time, end_time]` 过滤后再 `_write_keyframe_series`，边界帧保留（起点/终点各确保有采样，必要时取最邻近采样值）。

## 测试

- 前端 store 单测：`clampSegmentTimes` 边界（0/相邻段/1帧/原始时长）、`shift`/`retime`/`trim` 的字段改动、`addCamera`/`deleteCamera`。
- 后端：`apply_full_segments` 对「新增相机」「删除相机」「C 段 trim」分别跑 Blender 脚本后重新导出，断言相机数、段、关键帧正确。

## 实现后的关键设计决策（端到端联调后补充）

1. **编辑态/查看态 scene 隔离**：编辑态用 `cloneGLTF` 克隆独立 scene 副本（`gltfForCameraEdit`/`gltfForFreeEdit`），新增相机的动态节点只加在副本；退出编辑态副本整体丢弃，查看态原始 scene 从头到尾不动（不再需要 cleanup 擦除）。
2. **`editingCameras` 相机列表镜像**：编辑态相机列表独立于 `shot.cameras`，增删相机同步它；`EditTimeline` 用 `editingCameras ?? shot.cameras` 渲染轨道。
3. **C 段非破坏性裁剪**：`position_keyframes`/`rotation_keyframes` 进入编辑态即现读完整采样（`buildEditingSegments`），trim/shift 只改时间段、不删帧；渲染（`applySegmentToClip`）与保存（`saveEdit`）时按 `[start_time, end_time]` 过滤，拖回即恢复被裁帧。
4. **采样范围约束**：`clampSegmentTimes` 对 C 段把区间 clamp 到 keyframes 的 `[min time, max time]`，防止拖出采样范围导致空 track 崩溃。
5. **段间空白（gap）**：`scheduleSegmentWeights` 非末段上界延伸到下一段起点，gap 内保持前一段 `weight=1`，由 `clampWhenFinished` 停在前一段末尾画面。
