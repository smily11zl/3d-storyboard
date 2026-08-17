---
name: storyboard-scene-generator
description: Use when the user wants to generate a 3D Blender scene with characters via text description. Handles FBX character import, simple-geometry environment, multi-camera shot-segment sequences, and saves a .blend for the storyboard-3d-pipeline web viewer. Output directory is provided by the backend at runtime.
---

# 3D Storyboard Scene Generator

生成一个**单场景、镜头段序列**的 .blend 文件，供 web viewer 查看（时间轴自动序列播放 + 段切换）。
不渲染视频、不生成 TTS 音频。所有中间文件必须写入本次输出目录内。

**镜头段序列模型**：**一个相机对象在时间轴上承载多段运动（镜头段）**——相机按时间顺序经过多个运动段（如 0-3s 推近 → 3-5s 环绕 → 5-8s 静止），每段 = 一个时间区间 + 该相机的一段运动，段首尾相接成一条序列。web viewer 自动识别段并按时间轴顺序播放、在段边界自动切换相机。需要切换视角时可引入多个相机对象（相机复用，不同段引用不同相机）。

## 运行时约定

- 工作目录 = 项目根目录（`pwd` 检测，不要假设绝对路径）
- 角色资产目录 = `assets/characters/`
- **输出目录 OUTPUT_DIR**：由后端在指令中提供（`{OUTPUT_DIR}` 占位符），
  最终 .blend 保存为 `{OUTPUT_DIR}/scene.blend`，Blender 脚本保存为 `{OUTPUT_DIR}/script.py`
- 不要在其他位置创建文件（shots/、render/、根目录等一律不写）

## 修改模式（二次修改）

当输出目录里 **`{OUTPUT_DIR}/script.py` 已存在**时，说明这是对已有场景的二次修改（不是首次生成）。

**此时必须：**

1. 先读回 `{OUTPUT_DIR}/script.py`，了解现有场景结构（人物、机位、环境、材质）
2. **只修改用户要求的部分**（换人物 / 调机位 / 改材质 / 移动物体）
3. 保留未涉及的内容（场景环境、灯光、其他人物和机位）
4. **区分"扩展镜头段"和"新增相机"**：
   - 用户描述"先…再…"这类顺序运动 → 仍是**一个相机 + 多段**，在同一个相机上扩展时间轴段，不要新增相机对象。
   - 用户明确要求"新增相机/机位"（独立视角）→ 才新增相机对象；用户没提这个新相机从哪里开始，默认从 0 开始（frame 1）。
5. 重新运行 `blender --background --python {OUTPUT_DIR}/script.py` 覆盖生成 scene.blend
6. **不要新建代码文件**——在原有 script.py 上修改

**不要**从头重新生成整个场景（会丢失之前已调好的细节）。修改后仍需执行步骤 4 的点积自检。

---

## 角色库

三个 Mixamo FBX 角色（各 49 块骨骼，前缀 `mixamorig:`）：

| 文件 | 身高 | rot=0 朝向 | 说明 |
|------|------|-----------|------|
| male_mixamo_stand.fbx | 2m | **-Y** | 成年男性 |
| female_mixamo_stand.fbx | 2m | **-Y** | 成年女性 |
| child_mixamo_stand.fbx | 1m | **-Y** | 小孩 |

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

---

## 四步工作流程

每一步必须输出对应表格并通过约束自查，才可进入下一步。不要跳过表格直接写代码。

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

写完整 Python 脚本到 `{OUTPUT_DIR}/script.py` → `blender --background --python {OUTPUT_DIR}/script.py` → 保存 `{OUTPUT_DIR}/scene.blend`。

**渲染后自检（必须执行，但保持精简）:**

用点积验证每个相机是否在人物预期的方向（前方/后方）。**只做这一项验证，不要做像素级画面分析**（不要采样渲染图、不要统计角色可见性、不要包围盒角点验证——这些耗时且非必要）：

**坑：** 脚本内新建对象后直接读 `matrix_world` 会拿到未求值的旧值（表现为相机位置全变 0，自检误报方向反了）。自检前必须先 `bpy.context.view_layer.update()`。

```python
for cam_name, pos, rot, expected in [
    ('cam_01', POS_A, ROT_A, 'front'),  # 预期: front或behind
    ('cam_02', POS_B, ROT_B, 'behind'),
]:
    cam = bpy.data.objects[cam_name]
    dx = cam.matrix_world.translation.x - pos[0]    dy = cam.matrix_world.translation.y - pos[1]
    face_dir = (math.sin(rot), -math.cos(rot))
    dot = dx*face_dir[0] + dy*face_dir[1]
    actual = 'front' if dot > 0 else 'behind'
    print(f'{cam_name}: 预期{expected} 实际{actual} {"✓" if actual==expected else "✗ 方向反了!"}')
```

**dot > 0 = 在前方，dot < 0 = 在后方。** 与预期不一致报 ✗，修正后重跑；一致即交付。

**时间预算（重要）:** 整个生成过程（含自检与修正）控制在 **8 分钟内**。若自检通过，立即保存并结束——不要反复检查、不要重新渲染验证、不要优化细节。超时会被系统终止，浪费已完成的工作。

**脚本末尾必须:**
```python
bpy.ops.wm.save_as_mainfile(filepath="{OUTPUT_DIR}/scene.blend")
print("GENERATION_DONE")
```

完成后向用户报告: 镜头段数、每个段的机位/时间区间/运动类型/保存路径。

---

## Blender 代码规范

- **引擎:** `BLENDER_EEVEE_NEXT`
- **材质:** 同时设 `diffuse_color` + `Principled BSDF Base Color`
- **帧范围:** `scene.frame_start/end`，不是 `scene.render.frame_end`
- **节点遍历:** 用 `node.type` 不用 `node.name`
- **无阴影:** `eevee.use_shadows = False` + 灯光 `use_shadow = False`
- **关键帧插值:** LINEAR（避免 Bezier 过冲）
- 摄像机动画若需要：关键帧之间 LINEAR 插值
- **镜头段 NLA 代码模板（必须按此写法）:**

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

## 常见 LLM 错误（生成代码时避免）

| 错误 | 修正 |
|------|------|
| `BLENDER_EEEVEE_NEXT`（typo） | `BLENDER_EEVEE_NEXT` |
| `scene.render.frame_end` | `scene.frame_end` |
| `mat.diffuse_color` only | 加 Principled BSDF `Base Color` |
| `nodes["Background"]` | 按 `node.type == 'BACKGROUND'` 遍历 |
| `scene.eevee.use_ssr/use_gtao` | EEVEE_NEXT 不存在，删掉 |
| 导入 Mixamo FBX 后 fps 被覆盖成 30（时长缩水 20%）| 导入后重新设 `scene.render.fps = 24` |
