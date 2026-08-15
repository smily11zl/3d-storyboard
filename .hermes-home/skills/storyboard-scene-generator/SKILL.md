---
name: storyboard-scene-generator
description: Use when the user wants to generate a 3D Blender scene with characters via text description. Handles FBX character import, simple-geometry environment, multi-camera setup, and saves a .blend for the storyboard-3d-pipeline web viewer. Output directory is provided by the backend at runtime.
---

# 3D Storyboard Scene Generator (V2)

生成一个**单场景、多机位**的 .blend 文件，供 web viewer 查看（摄像机下拉切换机位）。
不渲染视频、不生成 TTS 音频。所有中间文件必须写入本次输出目录内。

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
4. 重新运行 `blender --background --python {OUTPUT_DIR}/script.py` 覆盖生成 scene.blend
5. **不要新建代码文件**——在原有 script.py 上修改

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

### 步骤 3 — 多机位设计

基于已确认的场景和人物位置，根据用户描述的镜头含义设计**多个摄像机**（机位）。如果用户描述明确只需单机位，则只生成一个机位。

**输出: 机位计划表**

| 机位名 | 摄像机公式 | 参数 | 注视点 | 含义 |
|--------|----------|------|--------|------|
| cam_01 | `cam_front(男)` | pos/rot | 男人面部 | 男人正脸 |
| cam_02 | `cam_behind(女)` | pos/rot | 女人身后 | 女人背影 |
| ... | | | | |

**机位约定:**

- **机位数量 ≥ 1**（多机位是本功能的核心卖点；除非描述明确单视角）
- 机位名用 `cam_01`、`cam_02`…（web viewer 按名字列出，名字要能看出视角含义）
- 常见机位类型：正脸（cam_front）、背影（cam_behind）、侧面、特写、全景（手写坐标）
- 每个机位是一个独立的 `bpy.data.objects` 摄像机对象，全部加入场景并设置命名
- 场景相机（scene.camera）设为第一个机位
- 机位类型、数量、注视点由用户描述决定；不要添加用户未要求的机位含义

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
- 每个机位用 TRACK_TO 约束对准自己的注视点（`track_axis='TRACK_NEGATIVE_Z'`, `up_axis='UP_Y'`）

**约束:**

- 摄像机路径不穿入场景物体
- 帧1 摄像机 z ≥ 场景表面 z + 1.5m

---

### 步骤 4 — 生成并自检

写完整 Python 脚本到 `{OUTPUT_DIR}/script.py` → `blender --background --python {OUTPUT_DIR}/script.py` → 保存 `{OUTPUT_DIR}/scene.blend`。

**渲染后自检（必须执行，但保持精简）:**

用点积验证每个机位摄像机是否在人物预期的方向（前方/后方）。**只做这一项验证，不要做像素级画面分析**（不要采样渲染图、不要统计角色可见性、不要包围盒角点验证——这些耗时且非必要）：

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

完成后向用户报告: 机位数、每个机位名与视角含义、保存路径。

---

## Blender 代码规范

- **引擎:** `BLENDER_EEVEE_NEXT`
- **材质:** 同时设 `diffuse_color` + `Principled BSDF Base Color`
- **帧范围:** `scene.frame_start/end`，不是 `scene.render.frame_end`
- **节点遍历:** 用 `node.type` 不用 `node.name`
- **无阴影:** `eevee.use_shadows = False` + 灯光 `use_shadow = False`
- **关键帧插值:** LINEAR（避免 Bezier 过冲）
- 摄像机动画若需要：关键帧之间 LINEAR 插值

## 常见 LLM 错误（生成代码时避免）

| 错误 | 修正 |
|------|------|
| `BLENDER_EEEVEE_NEXT`（typo） | `BLENDER_EEVEE_NEXT` |
| `scene.render.frame_end` | `scene.frame_end` |
| `mat.diffuse_color` only | 加 Principled BSDF `Base Color` |
| `nodes["Background"]` | 按 `node.type == 'BACKGROUND'` 遍历 |
| `scene.eevee.use_ssr/use_gtao` | EEVEE_NEXT 不存在，删掉 |
