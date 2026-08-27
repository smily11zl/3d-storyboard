# V5 Design — 技术规格

## 1. 编辑请求 JSON schema

编辑操作打包成 `operations` 列表，后端按顺序应用：

```json
{
  "operations": [
    {
      "type": "set_pose",
      "camera_name": "cam_01",
      "segment_name": "seg_01",
      "which": "start",
      "position": [0, 3, 1.75],
      "rotation": [0, 0, 0]
    },
    {
      "type": "set_target",
      "camera_name": "cam_01",
      "segment_name": "seg_01",
      "target_position": [0, 2, 1]
    },
    {
      "type": "delete_segment",
      "camera_name": "cam_01",
      "segment_name": "seg_02"
    },
    {
      "type": "add_segment",
      "camera_name": "cam_01",
      "start_time": 10.0,
      "end_time": 13.0,
      "start_pose": { "position": [0,0,1], "rotation": [0,0,0] },
      "end_pose":   { "position": [2,0,1], "rotation": [0,0,0] }
    }
  ]
}
```

- `set_pose`：改段起点（`which="start"`）或终点（`which="end"`）的 pose（位置 + 朝向）
- `set_target`：改 TRACK_TO 的目标点位置（朝向 lookAt 重算）
- `delete_segment`：删段（其 NLA strip + action）
- `add_segment`：加段（新建 action + NLA strip）

## 2. API 端点

- `POST /api/shots/{export_hash}/edit`：提交 `operations` → 后端回存新 blend → 返回新 ShotMetadata
- `GET /api/shots/{export_hash}/blends`：列出当前会话文件夹的 blend 版本（按修改时间排序 + 最新标记）

## 3. Blender 回存脚本

`apply_edit_to_blend(input_blend, operations, output_blend)`：

1. 读原 blend（`bpy.ops.wm.open_mainfile`）
2. 逐个 operation 应用：
   - `set_pose`：定位相机 + 段（NLA strip）→ 改 action 的起点/终点关键帧（location + rotation_euler）
   - `set_target`：定位 TRACK_TO 约束 → 改 target 对象的 location（或移动 target Empty）
   - `delete_segment`：删 NLA strip（+ 其 action）
   - `add_segment`：新建 action（写起点/终点关键帧）+ 新 NLA strip（接在轨道末尾）
3. 另存新 blend：聊天源写回 `output/<folder>/scene_vN.blend`（版本化）；上传源写新 `upload_output/<时间戳>.blend`（扁平，成为新源）

关键：直接改 blend 结构（关键帧值 / 约束 target），不经过 glTF，故无损。

## 4. 前端组件结构

- `EditToolbar`：顶栏编辑态（放弃 + "Edit Mode" + Save，脏标记亮 Save）
- `SegmentTrack`：底部一个相机一条轨道，轨道上排列段块（蓝=S / 橙=C，选中深/未选中浅）
- `SegmentSidebar`：选中段后右侧侧栏（S 段=编辑属性；C 段=只读+提示+删除）
- `Playhead`：时间轴上的播放头竖线（拖动 + 播放）
- `store.ts` 增加：`editMode` / `dirty` / `selectedSegment` / 编辑中 pose·target / `setSegmentPose` / `setTarget` / `deleteSegment` / `addSegment`

## 5. 数据流

```
编辑操作（前端拖拽/数值）
  ↓ 打包 operations JSON
POST /api/shots/{hash}/edit
  ↓ 后端 apply_edit_to_blend
读原 blend → 改关键帧/约束 → 聊天源存 scene_vN.blend / 上传源存新 upload_output 文件
  ↓ 重新导出 glTF + segments
返回新 ShotMetadata
  ↓
前端刷新（新 blend 版本 + 新段数据）
```
