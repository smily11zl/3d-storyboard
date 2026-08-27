# V5 PRD — 手动编辑镜头段 + 回存 blend

## Problem

V4 只能「识别 + 播放 + 切换」镜头段序列，无法编辑。用户需要：

1. **编辑 / 删除镜头段**：简单段（S）可编辑，复杂段（C）仅查看 + 删除
2. **编辑结果回存为 blend**：编辑能无损写回 `.blend`，在当前项目文件夹另存新文件，保留编辑历史
3. **同聊天多 blend 切换**：一个聊天对应文件夹里有多个 blend 时，切换自动加载最新、支持手动切换

## User Stories

1. As a user, I want to edit a simple (S) segment — change its start/end pose or its TRACK_TO target — so that I can adjust the camera motion.
2. As a user, I want to delete any segment (S or C), so that I can remove unwanted shots.
3. As a user, I want complex (C) segments to be view-only + deletable, so that I understand what I can't edit and why.
4. As a user, I want to add a new segment at the end of a camera track, so that I can extend the shot sequence.
5. As a user, I want my edits saved back to a new `.blend`, so that they persist without overwriting prior versions.
6. As a user, I want to switch between multiple `.blend` versions in one chat folder, so that I can compare or roll back.

## Solution

### 1. 编辑态（Edit Mode）

- 顶栏右上角「编辑」按钮进入全局编辑态
- 编辑态界面：
  - 顶栏简化：左上「放弃」+ 标题 "Edit Mode"，右上「Save」（有改动才亮，脏标记）
  - 聊天框收起
  - 中间保留摄像机视图 + 自由视图（双视口）
  - 底部 = 时间轴（刻度 + 播放头）+ 多相机轨道（一个相机一个轨道，最大高度可滚动）

### 2. 段的编辑

- **S 段（简单）可编辑**：
  - 两 pose 编辑：改起点 / 终点 pose（位置 + 朝向）——拖拽为主 + 侧栏数值微调，双向同步
  - 约束编辑：改 TRACK_TO 目标点——拖拽目标点 + 侧栏数值微调，朝向 lookAt 重算
- **C 段（复杂）仅查看 + 删除**：侧栏显示只读信息 +「复杂段不可编辑」提示 + 删除按钮
- **新增段**：轨道末尾加段，默认静止段（起点 = 终点 = 上一段终点），时长 3 秒可改，朝向继承上一段
- **删除段**：右键菜单（编辑 / 删除）+ 侧栏删除按钮；删后不补位（留空档，空档相机静止）；删前弹窗确认

### 3. 回存 blend（无损）

- 编辑操作直接作用在 **blend 结构层次**（关键帧值 / 约束 target），不经过 glTF，故无损
- 后端 Blender 脚本：读原 blend → 应用编辑（改关键帧 / 改约束 target / 删段 / 加段）→ 另存新 blend
- 保存策略（聊天源）：累积 + 版本号（`scene.blend` 原始，编辑存 `scene_v2.blend`、`scene_v3.blend`…，不覆盖）
- 保存策略（上传源）：扁平——源文件与保存输出统一存 `upload_output/<时间戳>.blend`，每次保存生成新文件成为新源（二次编辑读最新）

### 4. 多 blend 切换

- 后端扫描当前聊天文件夹的 `.blend`（按修改时间排序）
- 前端：blend 下拉框 + 切换聊天自动加载最新 + 手动切换

## Implementation Decisions

### 编辑态交互（grill-me 结论）

| # | 决策点 | 结论 |
|---|--------|------|
| 1 | 编辑入口 | 顶栏右上角「编辑」按钮 → 全局编辑态 |
| 2 | 编辑态界面 | 顶栏简化（放弃+标题+Save）、聊天收起、双视口保留、底部时间轴+多轨道 |
| 3 | 两 pose 编辑 | 拖拽为主 + 侧栏数值微调，双向同步 |
| 4 | 预览帧定位 | 改起点→跳起点帧，改终点→跳终点帧 |
| 5 | 约束编辑 | 拖拽目标点 + 侧栏数值微调 |
| 6 | 朝向编辑形态 | 侧栏按段类型切换：线性段→起点/终点朝向角度；TRACK_TO 段→目标点 |
| 7 | 跟随模型 | 本期不做；target 有动画 → 判复杂 C（约束元数据记 `target_animated`）|
| 8 | 新增段参数 | 默认静止段（起点=终点=上一段终点），时长 3 秒可改，朝向继承上一段 |
| 9 | Save 检测 | 脏标记，有改动才亮 Save |
| 10 | 删除交互 | 右键菜单（编辑/删除）+ 侧栏删除按钮 |
| 11 | 删除后 | 不补位（留空档，空档期间相机静止）|
| 12 | 删除确认 | 弹窗 |
| 13 | C 段侧栏 | 只读信息 +「复杂段不可编辑」提示 + 删除按钮 |
| 14 | 段颜色 | 蓝=S / 橙=C；选中=深、未选中=浅 |

### 回存与切换

| 决策点 | 结论 |
|--------|------|
| 回存路线 | 后端读原 blend → Blender 脚本改关键帧/约束 → 另存新 blend（无损）|
| 保存策略 | 聊天源：累积 + 版本号（`scene_vN.blend`）不覆盖；上传源：扁平 `upload_output/<时间戳>.blend`，每次保存新文件成为新源 |
| 多 blend | 后端扫描文件夹 blend（按修改时间排序）+ 前端下拉框（自动最新 + 手动切换）|

## Testing Decisions

测试 seams（从高到低）：

1. **API 层**：`POST /api/shots/{hash}/edit`（提交编辑 → 回存新 blend → 返回新 metadata）；`GET /api/shots/{hash}/blends`（列出 blend 版本）
2. **Blender 回存脚本**：`apply_edit_to_blend(input_blend, edit_json, output_blend)`——改关键帧 / 改约束 target / 删段 / 加段。验证方式：回存后重新导出，断言编辑生效且其它段无损
3. **后端纯函数**：`parse_edit_request(edit_json)`（解析编辑请求 + 字段校验）；`build_blend_version_list(folder_path)`（扫描文件夹 → 版本列表）
4. **前端 Zustand store**：编辑态状态（editMode / dirty / 选中段 / 编辑中 pose/target）+ 编辑操作（setSegmentPose / setTarget / deleteSegment / addSegment）
5. **前端组件**：EditToolbar、SegmentTrack、SegmentSidebar、Playhead

## Out of Scope（V5 扩展，后续）

- 高优先级：撤销/重做、相机参数编辑（FOV/景深）、段的时间拖动
- 中优先级：删除/新增相机轨道、中间空白加段、TRACK_TO 动态跟随、预设运动类型、段复制粘贴
- 低优先级：摄像机实时录制、逐帧关键帧编辑、转场效果、时间轴缩放
