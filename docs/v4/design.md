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
  start_time: number;           // 秒（绝对）
  end_time: number;             // 秒（绝对）
  start_pose: Pose;             // 起点姿态
  end_pose: Pose;               // 终点姿态
  segment_type: "S" | "C";      // S=简单(可编辑) / C=复杂(自由)
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
      "start_time": 0.0,
      "end_time": 3.0,
      "start_pose": { "position": [0,0,5], "quaternion": [0,0,0,1] },
      "end_pose":   { "position": [0,0,2], "quaternion": [0,0,0,1] },
      "segment_type": "S"
    }
  ]
}
```

## 4. 识别逻辑（两段式）

**阶段 1 — Blender 脚本（export_shot.py 扩展）：**
- 遍历相机的 NLA tracks（每段一个 track）→ 提取相机名 + strip frame_start/end（绝对时间）
- 读每个段 action 的关键帧 → 去重 pose 数 → S（≤2）/ C（>2）
- 写 segments.json

**阶段 2 — 后端 `parse_segments_sidecar(sidecar_json)`：**
- 读 segments.json → 组装 ShotSegment[]（按 start_time 排序）

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
