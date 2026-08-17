# V4 Design — 技术规格

## 1. 数据流

```
blend 上传
  ↓ Blender 无头脚本（export_shot.py 扩展）
  读相机 NLA strips → 提取每段（相机名 / 绝对起止时间 / S-C）
  写 segments.json sidecar（含绝对时间 + S/C）
  ↓ 导出 glTF（每段一个独立 animation）
后端
  ↓ 读 segments.json → 组装 ShotSegment 列表（按 start_time 排序）
  ↓ 写进 ShotMetadata.segments
前端
  ↓ 读 metadata.segments → 按相机分组轨道（一个相机一个轨道）
  ↓ 时间轴全局播放；用户手动切换相机；生效/未生效用颜色区分
```

## 2. ShotSegment 数据结构（前后端契约）

```typescript
interface ShotSegment {
  camera_name: string;          // 引用的相机对象名
  segment_name: string;         // 段名（action 名或 strip 名）
  start_time: number;           // 秒（绝对）
  end_time: number;             // 秒（绝对）
  start_pose: Pose;             // 起点姿态
  end_pose: Pose;               // 终点姿态
  segment_type: "S" | "C";      // S=简单(可重演/可编辑) / C=复杂
  constraint?: SegmentConstraint; // 约束元数据（有约束才填）
}

interface SegmentConstraint {
  position?: ConstraintEntry[]; // 位置约束（FOLLOW_PATH 等）
  rotation?: ConstraintEntry[]; // 朝向约束（TRACK_TO 等）
}

interface ConstraintEntry {
  type: string;                 // 约束类型（TRACK_TO / FOLLOW_PATH …）
  target: string | null;        // 目标对象名
  track_axis?: string;          // TRACK_TO 专用
  up_axis?: string;             // TRACK_TO 专用
}

interface Pose {
  position: [number, number, number];
  quaternion: [number, number, number, number];
}
```

`ShotMetadata` 增加：
- `segments: ShotSegment[]`

## 3. segments.json sidecar 格式

```json
{
  "segments": [
    {
      "camera_name": "cam_01",
      "segment_name": "seg_01",
      "start_time": 0.0,
      "end_time": 3.0,
      "start_pose": { "position": [0,0,5], "quaternion": [0,0,0,1] },
      "end_pose":   { "position": [0,0,2], "quaternion": [0,0,0,1] },
      "segment_type": "S",
      "constraint": {
        "rotation": [{ "type": "TRACK_TO", "target": "LookTarget", "track_axis": "TRACK_NEGATIVE_Z", "up_axis": "UP_Y" }]
      }
    }
  ]
}
```

## 4. 识别逻辑（两段式）

**阶段 1 — Blender 脚本（export_shot.py 扩展）：**
- 段识别：遍历相机的 NLA tracks（每段一个 track）→ 提取相机名 + strip frame_start/end（绝对时间）；无 NLA track 但直接挂 Action 的相机，把 Action 关键帧范围当一个段（旧项目兼容）
- 类型判定：分通道（位置/朝向）判定 S/C，见 4.1
- 写 segments.json（含 segment_type + 约束元数据）

**阶段 2 — 后端 `parse_segments_sidecar(sidecar_json)`：**
- 读 segments.json → 组装 ShotSegment[]（按 start_time 排序）

### 4.1 S/C 判定（分通道）

每个段拆成「位置轨迹」和「朝向轨迹」两条独立通道，各自判定再组合。每条通道判「简单」需同时满足：

1. **无难重演约束**：TRACK_TO / LOCKED_TRACK / DAMPED_TRACK（lookAt 系）与 COPY_LOCATION / COPY_ROTATION（复制系）是确定性函数、可前端无损重演 → 不算复杂；FOLLOW_PATH / LIMIT_LOCATION / LIMIT_ROTATION（路径/限制系）难重演 → 复杂
2. **插值 glTF 可承载**：LINEAR / CONSTANT / BEZIER（= glTF 的 LINEAR / STEP / CUBICSPLINE）→ 简单；BACK / BOUNCE / ELASTIC 等特殊缓动 → 复杂
3. **去重值 ≤2**：2 pose（直线/静止）→ 简单；3+ pose（折线）→ 复杂

组合：**位置简单 且 朝向简单 → S；任一复杂 → C。**

约束元数据（TRACK_TO 的 target / track_axis / up_axis）始终写进 sidecar，供前端 lookAt 重演 + V5 编辑分流。

## 5. API 变更

- `ShotMetadata` 增加 `segments` 和 `timeline_mode` 字段
- 上传/导出流程扩展：Blender 脚本额外写 segments.json，后端读它

## 6. NLA 存储结构（Blender 内）

```
相机对象 cam_01
  animation_data
    ├─ nla_track_1: [strip "seg1" 0-3s → Action "seg1_push"]
    └─ nla_track_2: [strip "seg2" 3-5s → Action "seg2_truck"]
```

约束：每段一个独立 Action + 一个独立 NLA track（一个 track 一个 strip）。

## 7. 前端 UI 架构

- **一级段列表**（替代相机下拉框）：按相机 optgroup 分组（一个相机一个轨道），每项 `相机名 + Shot N + S/C + 起止时间`
- **时间轴全局**：时长 = 最长内容总时长，选择相机只切视角、不改时长
- **手动切换相机**：加载后默认第一个相机，用户下拉框选段才切（无自动切换）
- **状态可视化**：Free View 生效=蓝/未生效=红 + 选中=实线/未选中=虚线；Camera View 边框同色

## 8. 目录结构（V4 增量）

```
backend/export_shot.py       （改：读 NLA strips + 写 segments.json）
backend/shot_segments.py     （新增：parse_segments_sidecar + 组装 + 排序）
backend/tests/test_segments.py（新增：mock sidecar 单测）
frontend/src/types.ts        （改：ShotSegment + ShotMetadata.segments）
frontend/src/components/SegmentList.tsx（新增：一级段列表）
frontend/src/components/SceneModel.tsx（改：自动序列播放切相机）
.hermes-home/skills/storyboard-scene-generator/SKILL.md（改：多段序列 + NLA track 约束）
```
