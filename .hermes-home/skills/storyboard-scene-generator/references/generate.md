# 生成流程 — 四步工作流程

每一步必须输出对应表格并通过约束自查，才可进入下一步。不要跳过表格直接写代码。

---

## 角色操作

### 角色导入

```python
pre = set(bpy.data.objects.keys())
bpy.ops.import_scene.fbx(filepath=f"{CHAR_DIR}/male_mixamo_stand.fbx")
scene.render.fps = 24  # Mixamo FBX 自带 30fps，导入会覆盖场景帧率，必须重新设回（否则时长缩水 20%）
arm = [o for o in bpy.data.objects if o.type == 'ARMATURE' and o.name not in pre][0]
arm.location = (x, y, z); arm.rotation_euler.z = rot_z
arm.name = name; arm.hide_viewport = True
```

### 面朝方向

```
rot=0    → -Y      rot=90°  → +X
rot=-90° → -X      rot=180° → +Y
```

面部高度 = 身高 × 0.85（2m 成人面部 z ≈ 1.7m，1m 小孩面部 z ≈ 0.85m）。

## 生成代码规范（补充主 skill 的 Blender 规范）

- **无阴影:** `eevee.use_shadows = False` + 灯光 `use_shadow = False`
- **关键帧插值:** LINEAR（避免 Bezier 过冲）

---

### 步骤 1 — 场景搭建

创建场景环境，不含人物。根据用户描述决定场景类型和元素。

**输出: 场景元素表**

| 元素 | x | y | z中心 | 尺寸 | z底 | z顶 | 说明 |
|------|---|---|------|------|-----|-----|------|
| 地面 | 0 | 0 | 0 | ?×? | 0 | 0 | 基准面 |
| ... | | | | | | | |

**约束:**

- 所有物体 z底 ≥ 0（不陷地）
- 坡面场景：标注 `surface_z(d)` 公式
- 室内场景：门高 ≥ 最高人物身高 + 0.4m，墙高 ≥ 门高 + 0.3m

---

### 步骤 2 — 人物摆放

基于步骤 1 的场景元素表，确定人物位置和朝向。

**输出: 人物位置表**

| 人物 | x | y | z脚底 | z头顶 | 朝向(rot_z) | 面朝谁 |
|------|---|---|------|------|------------|--------|
| 男人 | | | | | | |
| 女人 | | | | | | |

**约束:**

1. 脚底 z = 该位置场景表面 z（平地=0，坡面按公式算）
2. 头顶 z ≤ 上方遮挡物底面 z
3. 头顶上方 ≥ 0.3m 余量
4. 需要互看的两人: (y₁−c_y)×(y₂−c_y) > 0（同侧不被场景遮挡）
5. 互看时朝向差 ≈ ±π

---

### 步骤 3 — 镜头段设计

根据用户描述的镜头含义，设计**镜头段序列**。默认用**一个相机对象承载全部镜头段**；段之间的关系由用户描述决定，不要擅自改成多相机：

- **连续**：用户描述推近/拉远/环绕/横移/摇移/跟随等连续运动 → 段之间首尾位置衔接。
- **硬切**：用户描述"切到""跳到"、或镜头位置差异大 → 段之间位置直接跳变，**仍是同一个相机**（不是多个相机）。
- **多相机**：仅当用户明确要"多个独立视角"（如"一台正面机位 + 一台侧面机位"）时才创建多个相机对象。

**输出: 相机计划表**

| 相机名 | 摄像机公式 | 参数 | 注视点 | 含义 |
|--------|----------|------|--------|------|
| cam_01 | `cam_front(男)` | pos/rot | 男人面部 | 男人正脸 |
| ... | | | | |

> 单相机时只有一行 cam_01；多相机仅当用户明确要多个独立视角时才增加 cam_02、cam_03…。

**相机约定:**

- **默认一个相机（cam_01）承载全部镜头段**——"位置差异大的多个镜头"用同一个相机的多段硬切表达，不是多相机。
- 仅当用户明确要多个独立视角时，才创建 cam_02、cam_03…（每个相机一个独立视角）。
- 相机名用 `cam_01`、`cam_02`…（web viewer 按名字列出，名字要能看出视角含义）
- 常见镜头类型：正脸（cam_front）、背影（cam_behind）、侧面、特写、全景（手写坐标）
- 每个相机是一个独立的 `bpy.data.objects` 摄像机对象，全部加入场景并设置命名
- 场景相机（scene.camera）设为第一个相机
- **创建相机必须设初始 `location`**：设到第一个段的起点位置（如 `cam_01.location = seg_01 起点坐标`），禁止让相机基础位置停留在 (0,0,0)
- 镜头类型、数量、注视点由用户描述决定；不要添加用户未要求的机位/镜头含义

**摄像机相对位置公式:**

```python
def cam_behind(pos, rot_z, height=2.0, dist=1.5):
    """人物背后 — 站位在面朝方向的反方向"""
    face_z = height * 0.85
    return (pos[0] - dist*math.sin(rot_z),
            pos[1] + dist*math.cos(rot_z),
            pos[2] + face_z)

def cam_front(pos, rot_z, height=2.0, dist=1.5):
    """人物正前方 — 站位在面朝方向"""
    face_z = height * 0.85
    return (pos[0] + dist*math.sin(rot_z),
            pos[1] - dist*math.cos(rot_z),
            pos[2] + face_z)
```

**公式原理:** `sin(rot_z)/cos(rot_z)` 把朝向角自动转为 XY 偏移量，免手动算。

**注视点规则:**
- 拍人物背影时，注视点应设在人物身后中间区域（不是远处目标），确保人物全貌在画面中
- 拍人物正脸时，注视点 = 人物面部坐标
- 每个相机用 TRACK_TO 约束对准自己的注视点（`track_axis='TRACK_NEGATIVE_Z'`, `up_axis='UP_Y'`）
- **朝向不要手动打完整 rotation 关键帧**：俯仰/注视交给 TRACK_TO 约束，导出端会自动把约束结果烘焙成 rotation 动画（含恒定朝向段，如直线推近）。手动打完整 rotation 关键帧会破坏 NLA 求值（段边界跳回起点）

**约束:**

- 摄像机路径不穿入场景物体
- 帧1 摄像机 z ≥ 场景表面 z + 1.5m

### 镜头段时间轴分配

基于相机计划表，把**镜头段**分配到时间轴上，构成一条首尾相接的序列。每段指定起点/终点位置与运动方式；段之间的"连续"或"硬切"由步骤 3 的判断决定。

**输出: 镜头段计划表**

| 段名 | 相机 | 时间区间(秒) | 帧范围 | 运动 | 类型 |
|------|------|-------------|--------|------|------|
| seg_01 | cam_01 | 0–3 | 1–72 | 推近 | S |
| seg_02 | cam_01 | 3–5 | 73–120 | 环绕 | S |
| seg_03 | cam_01 | 5–8 | 121–192 | 静止 | S |

**镜头段约定（强约束）:**

1. **一段 = 一个独立 Action + 一个独立 NLA track**（一个 track 只放一个 strip；**禁止一个 track 塞多个 strip**，否则 web viewer 导不出动画）
2. **段之间时间首尾相接、互不重叠**（段 N 的结束帧 = 段 N+1 的开始帧）
3. **默认一个相机对象承载全部段**（一个相机多段运动）。段之间的"硬切"（位置跳变）和"连续"（位置衔接）都由用户描述决定，都用同一个相机；仅当用户明确要多个独立视角时才引入多个相机对象（不同段引用不同相机）
4. **简单运动（S）= 2 个关键帧 pose + LINEAR 缓动**（推近/拉远/横移/摇移/环绕）
5. **复杂运动（C）= 3+ 个关键帧 pose**（如先推后摇的复合运动）
6. **静止镜头 = 2 个相同 pose 跨 N 秒**（明确时长，不是零长度——起止关键帧值相同）
7. 段名用 `seg_01`、`seg_02`…（Action 名 = 段名，NLA track 名 = 段名 + `_track`）
8. 帧率 24fps：时间(秒) × 24 = 帧号。总时长 = 所有段时长之和

---

### 步骤 4 — 生成并自检

写完整 Python 脚本到指令提供的 script 文件名（如 `{OUTPUT_DIR}/script_v3.py`）→ `blender --background --python` 运行 → 保存为指令提供的 blend 文件名（如 `{OUTPUT_DIR}/scene_v3.blend`）。

**渲染后自检（必须执行，但保持精简）:**

用点积验证每个相机是否在人物预期的方向（前方/后方）。**只做这一项验证，不要做像素级画面分析**（不要采样渲染图、不要统计角色可见性、不要包围盒角点验证——这些耗时且非必要）：

**坑：** 脚本内新建对象后直接读 `matrix_world` 会拿到未求值的旧值（表现为相机位置全变 0，自检误报方向反了）。自检前必须先 `bpy.context.view_layer.update()`。

```python
for cam_name, pos, rot, expected in [
    ('cam_01', POS_A, ROT_A, 'front'),  # 预期: front或behind
    ('cam_02', POS_B, ROT_B, 'behind'),
]:
    cam = bpy.data.objects[cam_name]
    dx = cam.matrix_world.translation.x - pos[0]
    dy = cam.matrix_world.translation.y - pos[1]
    face_dir = (math.sin(rot), -math.cos(rot))
    dot = dx*face_dir[0] + dy*face_dir[1]
    actual = 'front' if dot > 0 else 'behind'
    print(f'{cam_name}: 预期{expected} 实际{actual} {"✓" if actual==expected else "✗ 方向反了!"}')
```

**dot > 0 = 在前方，dot < 0 = 在后方。** 与预期不一致报 ✗，修正后重跑；一致即交付。

**时间预算（重要）:** 整个生成过程（含自检与修正）控制在 **8 分钟内**。若自检通过，立即保存并结束——不要反复检查、不要重新渲染验证、不要优化细节。超时会被系统终止，浪费已完成的工作。

**脚本末尾必须:**
```python
bpy.ops.wm.save_as_mainfile(filepath="{OUTPUT_DIR}/{指令提供的 blend 文件名}")
print("GENERATION_DONE")
```

完成后向用户报告: 镜头段数、每个段的机位/时间区间/运动类型/保存路径。

---

## 镜头段 NLA 代码模板（必须按此写法）

```python
def add_segment(camera_obj, segment_name, start_frame, end_frame,
                start_pos, end_pos, start_rot_z=None, end_rot_z=None):
    """一个镜头段 = 一个独立 Action + 一个独立 NLA track（一个 track 一个 strip）。"""
    # 1. 创建独立 Action 并设为 active（每段一个 Action）
    action = bpy.data.actions.new(segment_name)
    camera_obj.animation_data_create()
    camera_obj.animation_data.action = action

    # 2. 打关键帧（打到 active action）。简单运动 2 pose（起+终）；
    #    静止镜头 = start_pos == end_pos（起终值相同，跨 N 秒）。
    #    关键帧用「绝对帧」：glTF 导出的 animation 时间就是绝对时间，
    #    前端靠全局时间轴直接采样 + weight 调度各段（无需 startAt）。
    camera_obj.location = start_pos
    camera_obj.keyframe_insert(data_path="location", frame=start_frame)
    if start_rot_z is not None:
        camera_obj.rotation_euler.z = start_rot_z
        camera_obj.keyframe_insert(data_path="rotation_euler", index=2, frame=start_frame)

    camera_obj.location = end_pos
    camera_obj.keyframe_insert(data_path="location", frame=end_frame)
    if end_rot_z is not None:
        camera_obj.rotation_euler.z = end_rot_z
        camera_obj.keyframe_insert(data_path="rotation_euler", index=2, frame=end_frame)

    # 3. LINEAR 插值（避免 Bezier 过冲）
    for fc in action.fcurves:
        for kp in fc.keyframe_points:
            kp.interpolation = 'LINEAR'

    # 4. 每个段一个独立 NLA track（一个 track 只放一个 strip；
    #    禁止一个 track 塞多个 strip，否则 glTF 导出 0 个动画）
    track = camera_obj.animation_data.nla_tracks.new()
    track.name = segment_name + "_track"
    strip = track.strips.new(segment_name, start=start_frame, action=action)
    strip.frame_end = end_frame
    strip.extrapolation = 'NOTHING'  # 只在时间范围内生效，不 HOLD 覆盖其他段
```

调用示例（段首尾相接）：

```python
add_segment(cam_01, "seg_01", 1, 72, (0,0,5), (0,0,2))          # 0-3s 推近
add_segment(cam_01, "seg_02", 73, 120, (3,0,5), (1.5,0,3), None, None)  # 3-5s 环绕
add_segment(cam_01, "seg_03", 121, 192, (0,0,2), (0,0,2))      # 5-8s 静止（起终相同）

# 所有段创建完成后，必须清除 active action——
# 否则它作为 tweak 层覆盖 NLA 求值，只有最后一段生效
cam_01.animation_data.action = None
```

注意：`add_segment` 设了 `animation_data.action`，若一个相机有多段，**每次调用都新建独立 Action + 独立 track**，不要复用同一个 Action。

---

## 完整脚本骨架（可直接套用）

以下是从 import 到保存的完整结构，AI 套用后填充场景细节即可，**不要再去搜索项目里的历史 script.py 参考**。

```python
import bpy
import math

CHAR_DIR = "/Users/zengle/Documents/storyboard-3d-pipeline/assets/characters"
OUTPUT_DIR = "{OUTPUT_DIR}"   # 后端指令提供的输出目录
SCRIPT_NAME = "{指令提供的 script 文件名}"   # 如 script_v3.py 或 script.py
BLEND_NAME = "{指令提供的 blend 文件名}"     # 如 scene_v3.blend 或 scene.blend
scene = bpy.context.scene
scene.render.fps = 24

# ── 材质 ──
def make_material(name, color, roughness=0.7):
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    mat.diffuse_color = color  # 视口
    for node in mat.node_tree.nodes:
        if node.type == 'BSDF_PRINCIPLED':
            node.inputs["Base Color"].default_value = color  # 渲染
            node.inputs["Roughness"].default_value = roughness
            break
    return mat

# ── 角色导入 ──
def import_character(fbx_name, location, rot_z, name):
    pre = set(bpy.data.objects.keys())
    bpy.ops.import_scene.fbx(filepath=f"{CHAR_DIR}/{fbx_name}")
    scene.render.fps = 24  # Mixamo 导入会覆盖帧率，重新设回
    arm = [o for o in bpy.data.objects if o.type == 'ARMATURE' and o.name not in pre][0]
    arm.location = location
    arm.rotation_euler.z = rot_z
    arm.name = name
    arm.hide_viewport = True
    return arm

# ── 场景搭建（按步骤 1 的场景元素表，逐个创建物体）──
# 地面 / 墙 / 桌椅等，材质用 make_material，坐标按表

# ── 相机 + 注视目标 ──
bpy.ops.object.camera_add(location=(0, 0, 2))
cam = bpy.context.object
cam.name = "cam_01"
scene.camera = cam

bpy.ops.object.empty_add(type='PLAIN_AXES', location=(0, 0, 1.5))
aim = bpy.context.object
aim.name = "aim_target"
track = cam.constraints.new(type='TRACK_TO')
track.target = aim
track.track_axis = 'TRACK_NEGATIVE_Z'
track.up_axis = 'UP_Y'

# ── 镜头段（每段 = 独立 Action + 独立 NLA track，同上方 add_segment 模板）──
def add_segment(camera_obj, segment_name, start_frame, end_frame,
                start_pos, end_pos, start_rot_z=None, end_rot_z=None):
    action = bpy.data.actions.new(segment_name)
    camera_obj.animation_data_create()
    camera_obj.animation_data.action = action
    camera_obj.location = start_pos
    camera_obj.keyframe_insert(data_path="location", frame=start_frame)
    if start_rot_z is not None:
        camera_obj.rotation_euler.z = start_rot_z
        camera_obj.keyframe_insert(data_path="rotation_euler", index=2, frame=start_frame)
    camera_obj.location = end_pos
    camera_obj.keyframe_insert(data_path="location", frame=end_frame)
    if end_rot_z is not None:
        camera_obj.rotation_euler.z = end_rot_z
        camera_obj.keyframe_insert(data_path="rotation_euler", index=2, frame=end_frame)
    for fc in action.fcurves:
        for kp in fc.keyframe_points:
            kp.interpolation = 'LINEAR'
    track = camera_obj.animation_data.nla_tracks.new()
    track.name = segment_name + "_track"
    strip = track.strips.new(segment_name, start=start_frame, action=action)
    strip.frame_end = end_frame
    strip.extrapolation = 'NOTHING'

# 段调用（首尾相接，按镜头段计划表）
add_segment(cam, "seg_01", 1, 72, (0, 0.2, 1.7), (0, 0.2, 1.7))
add_segment(cam, "seg_02", 73, 120, (0, -0.2, 1.7), (0, -0.2, 1.7))
add_segment(cam, "seg_03", 121, 216, (1.8, 0.4, 2.0), (4.2, 0.6, 2.2))

# 所有段创建后清除 active action（否则 tweak 层覆盖 NLA 求值）
cam.animation_data.action = None

scene.frame_end = 216

# ── 点积自检（步骤 4）──
bpy.context.view_layer.update()
for cam_name, pos, rot, expected in [
    ('cam_01', (0, -1, 1.7), 0.0, 'front'),  # 按实际人物坐标填
]:
    c = bpy.data.objects[cam_name]
    dx = c.matrix_world.translation.x - pos[0]
    dy = c.matrix_world.translation.y - pos[1]
    face_dir = (math.sin(rot), -math.cos(rot))
    dot = dx * face_dir[0] + dy * face_dir[1]
    actual = 'front' if dot > 0 else 'behind'
    print(f'{cam_name}: 预期{expected} 实际{actual} {"✓" if actual == expected else "✗"}')

# ── 保存 ──
bpy.ops.wm.save_as_mainfile(filepath=f"{OUTPUT_DIR}/{BLEND_NAME}")
print("GENERATION_DONE")
```
