---
name: storyboard-scene-generator
description: Use when the user wants to generate a 3D Blender scene with characters. Handles FBX character import, simple-geometry environment, camera setup, and rendering into .blend files for the storyboard-3d-pipeline project.
---

# 3D Storyboard Scene Generator

## 项目路径

```
CHAR_DIR = "/Users/zengle/Documents/storyboard-3d-pipeline/characters"
OUT_DIR  = "/Users/zengle/Documents/storyboard-3d-pipeline/render"
SHOT_DIR = "/Users/zengle/Documents/storyboard-3d-pipeline/shots"
```

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
- 渲俯视图 + 正面图，确认外观

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

通过后渲染俯视图确认。

---

### 步骤 3 — 镜头设计

基于已确认的场景和人物位置，根据用户描述的镜头运动设计摄像机路径。

**输出: 镜头计划表**

| 帧段 | 摄像机公式 | 参数 | 注视点 | 含义 |
|------|----------|------|--------|------|
| ?-? | `cam_front(男)` 或 `cam_behind(女)` | pos/rot | 对应人物面部 | 按用户描述的镜头含义 |

> 帧段数量、摄像机类型（正脸/背影/手写坐标）、注视点完全由用户描述决定。不要添加用户未要求的镜头段。下方是几个常见组合的样例：

**样例 A: "男人正脸停留 → 女人正脸停留"**

| 帧段 | 摄像机公式 | 注视点 | 
|------|----------|--------|
| 1-40 | `cam_front(男)` | 男人面部 |
| 40-120 | `cam_front(女)` | 女人面部 |

**样例 B: "女人背后 → 到男人面前停留 → 后拉全山"**

| 帧段 | 摄像机公式 | 注视点 |
|------|----------|--------|
| 1-40 | `cam_behind(女)` | 女人身后方向 |
| 40-120 | `cam_front(男)` | 男人面部 |
| 120-160 | 手写坐标 | 场景中心 |

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
- 过渡段注视点从上一段平滑切换到下一段

**约束:**

- 摄像机路径不穿入场景物体
- 关键帧之间用 LINEAR 插值（避免 Bezier 过冲）
- 帧1 摄像机 z ≥ 场景表面 z + 1.5m

---

### 步骤 4 — 生成并自检

写完整 Python 脚本 → `blender --background --python` → 渲染 .blend + .png。

**渲染后自检（必须执行）:**

用点积验证每段镜头摄像机是否在人物预期的方向（前方/后方）：

```python
for f, name, pos, rot, expected in [
    (1,  '人物A', POS_A, ROT_A, 'front'),  # 预期: front或behind
    (80, '人物B', POS_B, ROT_B, 'front'),
]:
    scene.frame_set(f)
    cam = scene.camera
    dx = cam.matrix_world.translation.x - pos[0]
    dy = cam.matrix_world.translation.y - pos[1]
    face_dir = (math.sin(rot), -math.cos(rot))
    dot = dx*face_dir[0] + dy*face_dir[1]
    actual = 'front' if dot > 0 else 'behind'
    print(f'{name}: 预期{expected} 实际{actual} {"✓" if actual==expected else "✗ 方向反了!"}')
```

**dot > 0 = 在前方，dot < 0 = 在后方。** 与预期不一致报 ✗，不交付。

---

## Blender 代码规范

- **引擎:** `BLENDER_EEVEE_NEXT`
- **材质:** 同时设 `diffuse_color` + `Principled BSDF Base Color`
- **帧范围:** `scene.frame_start/end`，不是 `scene.render.frame_end`
- **节点遍历:** 用 `node.type` 不用 `node.name`
- **无阴影:** `eevee.use_shadows = False` + 灯光 `use_shadow = False`

## 输出

1. `shots/test_XX.py` — 可重复运行脚本
2. `render/test_XX.blend` — Blender 工程
3. `render/test_XX.png` — 预览图
