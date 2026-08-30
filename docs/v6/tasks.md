# V6 Tasks — 任务拆解

状态图例：⬜ 未开始 · 🔄 进行中 · ✅ 完成 · ❌ 取消

## 切片列表（垂直切片，端到端，按依赖顺序）

| # | 切片 | 依赖 | 类型 | 状态 |
|---|---|---|---|---|
| 1 | 前端 store：`original_duration` + 段拖动 action + `clampSegmentTimes` 约束 + 单测 | — | AFK | ✅ |
| 2 | 前端组件：`EditTimeline` 固定 600s + 有效时长标记 + 段拖动 UI | 1 | AFK | ✅ |
| 3 | 前端组件：`SegmentSidebar` 时长块四项 | 1 | AFK | ✅ |
| 4 | 前端 store + 组件：`addCamera` / `deleteCamera` + 增删按钮 UI | 1 | AFK | ✅ |
| 5 | 后端：`apply_full_segments` 相机增删 + C 段 trim | — | AFK | ✅ |
| 6 | 收尾：dirty 全覆盖检查 + 端到端验证 | 1–5 | HITL | ✅ |

## 切片明细

### 切片 1 — 前端 store（AFK）

- `types.ts`：`ShotSegment.original_duration?`
- `buildEditingSegments`：写 `original_duration = end_time - start_time`
- `addSegment`：初始化 `original_duration`
- 新增 `shiftSegment` / `retimeSegment` / `trimSegment` + 内部 `clampSegmentTimes`
- 单测：约束边界（0 / 相邻段 / 1 帧 / original_duration）、字段改动正确性

### 切片 2 — EditTimeline（AFK）

- 时间轴 `TIMELINE_TOTAL = 600` 固定刻度，段按 `end_time/600` 排布
- 有效总时长竖线 + 0～有效时长高亮
- 段 block 三档拖动（中段 Shift / 边缘 Re-time|Trim 按 `segment_type` 分派）

### 切片 3 — SegmentSidebar 时长块（AFK）

- `Duration`（S 可编辑 / C 只读）、`Start`/`End`（可编辑）、`Effective`（只读）
- 与拖动双向联动（同一 `start_time`/`end_time`/`original_duration`）

### 切片 4 — 相机增删 UI + store（AFK）

- `addCamera`（新建 cam_0N + 初始 3s 段）、`deleteCamera`（删相机 + 所有段）
- 轴标签旁「✕」按钮 + 底部「+ 相机」按钮；删除活跃相机后切到剩余第一个

### 切片 5 — 后端相机增删 + C 段 trim（AFK）

- `apply_full_segments`：新增相机（`_find_camera` None → 新建 + 约束 + 专属 aim_target）；删除相机（blend 有 segments 无 → 删对象 + 专属 aim_target）
- C 段 trim：`position_keyframes`/`rotation_keyframes` 裁到 `[start_time, end_time]`
- 验证：Blender 脚本回存后重新导出，断言相机数/段/关键帧正确

### 切片 6 — 收尾（HITL）

- 检查所有写 `editingSegments` 的 action 都置 `dirty: true`
- 端到端：新增相机 → 删除相机 → 拖动段 → 保存 → 重新加载，全链路验证

## 验收标准

1. 编辑态能新增相机轴（全默认 + 初始 3s 段）、删除相机轴（含专属 aim_target，共享保留）；
2. 段能整体平移 + 拖边缘改时长，受「≥0、不越相邻段、[1帧, 原始时长]」约束；
3. 时间轴固定 10 分钟显示，有效总时长用竖线+高亮标出；
4. 时长块 `Duration`/`Start`/`End`/`Effective` 四项工作正常，C 段 Duration 只读；
5. 后端保存后重新导出，相机增删和 C 段 trim 结果正确。

## 开发后修复记录（TDD 切片完成后端到端联调发现并修复）

1. 时间轴从「600s 平铺」改为「固定像素比例 + 横向滚动」（`PX_PER_SECOND` 30→90），段保持可操作宽度；0 秒对齐修正 `LABEL_WIDTH=178`；刻度每秒一个数字。
2. 滚动结构：加 `timelineContent` 包装层，段/刻度/有效时长/播放头同层滚动；轨道区固定最大高度 143px（3 相机 + 添加按钮），超出上下滚动。
3. 相机增删：引入 `editingCameras` 状态（相机列表镜像）；渲染层编辑态用独立 scene 副本（`cloneGLTF`），新增相机动态建节点、删除相机移除节点、退出编辑态副本丢弃——查看态与编辑态彻底隔离。
4. 段拖动渲染：`applySegmentToClip` 重建后同步 `clip.duration`；C 段进入编辑态就现读 keyframes（`buildEditingSegments`）。
5. C 段裁剪改为非破坏性：keyframes 完整保留，trim/shift 只改时间段，渲染/保存时按段范围过滤；加采样范围约束（拖长不超出 keyframes 采样范围，防崩溃）。
6. 段间空白显示前一段末尾画面（`scheduleSegmentWeights` 非末段上界延伸到下一段起点）；删除所有段后不补虚拟整段，轨道为空。
7. 交互细节：段边缘 hover 竖线把手 + `ew-resize` 光标；时间轴 `user-select:none` + mousedown `preventDefault` 消除拖动框选。
