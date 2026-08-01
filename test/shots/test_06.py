"""
test_06.py — 山坡场景：一个人上山，镜头从背后推远展示整座山
- 山：大圆锥体
- 树林：圆柱干 + 球冠
- 人物：圆柱身体 + 球头，面朝山顶
- 镜头：从背后近景推远到高空鸟瞰
"""
import bpy
import math
import random

random.seed(123)

# ============================================================
# 1. 清空
# ============================================================
bpy.ops.object.select_all(action='SELECT')
bpy.ops.object.delete()

scene = bpy.context.scene
scene.render.engine = 'BLENDER_EEVEE_NEXT'
scene.unit_settings.system = 'METRIC'
scene.render.fps = 24
scene.frame_start = 1
scene.frame_end = 96  # 4秒

# ============================================================
# 2. 包围盒验算
# ============================================================
# 山: 圆锥 center=(0,1,3) r=8 h=6 → 底z=0 顶z=6
# 人物: 站 (0, 4.5, z_surface)
#   dist_from_center=3.5, z_surface=6*(1-3.5/8)=3.375
#   身体: z_center=3.375+0.55=3.925 depth=1.1 → [3.375, 4.475]
#   头:   z_center=3.375+1.3=4.675 r=0.22 → [4.455, 4.895]
#   头顶4.895 < 山顶6 ✓

def surface_z(x, y, cx=0, cy=1, r=8, h=6):
    dist = math.sqrt((x-cx)**2 + (y-cy)**2)
    if dist > r:
        return 0
    return h * (1 - dist/r)

# ============================================================
# 3. 材质
# ============================================================
def make_material(name, color, roughness=0.6):
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    mat.diffuse_color = (*color, 1.0)
    for node in mat.node_tree.nodes:
        if node.type == 'BSDF_PRINCIPLED':
            node.inputs["Base Color"].default_value = (*color, 1.0)
            node.inputs["Roughness"].default_value = roughness
            break
    return mat

MAT_GROUND = make_material("Ground",  (0.45, 0.55, 0.30), 0.9)  # 草地
MAT_MOUNT  = make_material("Mountain",(0.40, 0.48, 0.35), 0.8)  # 山体
MAT_SNOW   = make_material("Snow",    (0.95, 0.95, 0.92), 0.4)  # 山顶雪
MAT_TRUNK  = make_material("Trunk",   (0.30, 0.22, 0.15), 0.8)  # 树干
MAT_LEAF   = make_material("Leaf",    (0.18, 0.45, 0.15), 0.7)  # 树叶
MAT_SHIRT  = make_material("Shirt",   (0.85, 0.30, 0.15), 0.6)  # 橙衣
MAT_PANTS  = make_material("Pants",   (0.20, 0.22, 0.28), 0.6)  # 深蓝裤
MAT_SKIN   = make_material("Skin",    (1.0, 0.85, 0.70), 0.5)   # 肤色
MAT_SKY    = make_material("Sky",     (0.55, 0.75, 0.95), 0.3)   # 天空

# ============================================================
# 4. 地面
# ============================================================
bpy.ops.mesh.primitive_plane_add(size=30, location=(0, 1, -.02))
bpy.context.active_object.name = "Ground"
bpy.context.active_object.data.materials.append(MAT_GROUND)

# ============================================================
# 5. 主山（圆锥体）
# ============================================================
bpy.ops.mesh.primitive_cone_add(
    vertices=32,
    radius1=8, radius2=0,
    depth=6,
    location=(0, 1, 3)
)
mountain = bpy.context.active_object
mountain.name = "Mountain"
mountain.data.materials.append(MAT_MOUNT)

# ============================================================
# 6. 山顶雪冠（小球体，放在锥尖）
# ============================================================
bpy.ops.mesh.primitive_uv_sphere_add(
    radius=0.6, location=(0, 1, 5.8)
)
snow = bpy.context.active_object
snow.name = "SnowCap"
snow.data.materials.append(MAT_SNOW)

# ============================================================
# 7. 小林（背景远处的矮山丘）
# ============================================================
for (bx, by, br, bh, bz) in [
    (-7, 3, 3.5, 2.5, 1.25),
    (7, 1, 3.0, 2.0, 1.0),
    (-5, -4, 4.0, 3.0, 1.5),
]:
    bpy.ops.mesh.primitive_cone_add(
        vertices=24,
        radius1=br, radius2=0,
        depth=bh,
        location=(bx, by, bz)
    )
    obj = bpy.context.active_object
    obj.name = "SmallHill"
    obj.data.materials.append(MAT_MOUNT)

# ============================================================
# 8. 树木生成
# ============================================================
def create_tree(x, y):
    z = surface_z(x, y)
    # 树干
    th = 1.0 + random.uniform(0, 1.0)
    bpy.ops.mesh.primitive_cylinder_add(
        radius=0.08, depth=th,
        location=(x, y, z + th/2)
    )
    bpy.context.active_object.data.materials.append(MAT_TRUNK)
    # 树冠
    cr = 0.4 + random.uniform(0, 0.3)
    bpy.ops.mesh.primitive_uv_sphere_add(
        radius=cr,
        location=(x, y, z + th + cr * 0.5)
    )
    bpy.context.active_object.data.materials.append(MAT_LEAF)

# 山坡上散布树木（避开摄像机路径）
tree_positions = []
for _ in range(40):
    angle = random.uniform(0, 2*math.pi)
    dist = random.uniform(1.5, 8)
    tx = dist * math.cos(angle)
    ty = 1 + dist * math.sin(angle)
    # 避开人物前方和摄像机弧线
    if abs(tx) < 1.0 and 2.0 < ty < 6.0:
        continue
    if surface_z(tx, ty) > 0.3:
        tree_positions.append((tx, ty))

for tx, ty in tree_positions:
    create_tree(tx, ty)

# 山脚下也有树
for _ in range(20):
    tx = random.uniform(-10, 10)
    ty = random.uniform(-7, 9)
    if surface_z(tx, ty) < 0.2:  # 山脚平地
        bpy.ops.mesh.primitive_cylinder_add(
            radius=0.06, depth=1.2,
            location=(tx, ty, 0.6)
        )
        bpy.context.active_object.data.materials.append(MAT_TRUNK)
        bpy.ops.mesh.primitive_uv_sphere_add(
            radius=0.3, location=(tx, ty, 1.6)
        )
        bpy.context.active_object.data.materials.append(MAT_LEAF)

# ============================================================
# 9. 人物
# ============================================================
person_x, person_y = 0, 5.0
person_z = surface_z(person_x, person_y)  # ≈ 3.0

# 腿
bpy.ops.mesh.primitive_cylinder_add(
    radius=0.18, depth=0.6,
    location=(person_x, person_y, person_z + 0.3)
)
bpy.context.active_object.name = "Person_Legs"
bpy.context.active_object.data.materials.append(MAT_PANTS)

# 身体
bpy.ops.mesh.primitive_cylinder_add(
    radius=0.22, depth=0.8,
    location=(person_x, person_y, person_z + 0.9)
)
bpy.context.active_object.name = "Person_Body"
bpy.context.active_object.data.materials.append(MAT_SHIRT)

# 头
bpy.ops.mesh.primitive_uv_sphere_add(
    radius=0.22,
    location=(person_x, person_y, person_z + 1.42)
)
bpy.context.active_object.name = "Person_Head"
bpy.context.active_object.data.materials.append(MAT_SKIN)

print(f"人物站: z_surface={person_z:.2f} 头顶={person_z+1.64:.2f}")

# ============================================================
# 10. 天空球（大球壳包裹场景）
# ============================================================
bpy.ops.mesh.primitive_uv_sphere_add(
    radius=20, location=(0, 1, 5)
)
sky = bpy.context.active_object
sky.name = "SkyDome"
sky.data.materials.append(MAT_SKY)

# ============================================================
# 11. 镜头动画
# ============================================================
bpy.ops.object.camera_add(location=(0.3, 3.5, person_z + 1.0))
cam = bpy.context.active_object
cam.name = "ShotCamera"
cam.data.lens = 28
scene.camera = cam

# 注视点
bpy.ops.object.empty_add(type='PLAIN_AXES', location=(0, 6, person_z + 1.2))
look = bpy.context.active_object
look.name = "LookTarget"
c = cam.constraints.new(type='TRACK_TO')
c.target = look
c.track_axis = 'TRACK_NEGATIVE_Z'
c.up_axis = 'UP_Y'

# 镜头：从右侧远处 → 拉远升高到鸟瞰
# 验证: cam_start(2.5,2.5,5.5) 处山面z=3.81, 镜头5.5>3.81 ✓
cam_start = (2.5, 2.5, 5.5)   # 右侧坡外，高于山面
cam_end   = (0, -2, 12)        # 高空远眺

cam.location = cam_start
cam.keyframe_insert('location', frame=1)
cam.location = cam_end
cam.keyframe_insert('location', frame=72)
cam.location = cam_end
cam.keyframe_insert('location', frame=96)

for fc in cam.animation_data.action.fcurves:
    for kf in fc.keyframe_points:
        kf.interpolation = 'BEZIER'

# 注视：看人物上山 → 最终看整座山
look.location = (0, 6, person_z + 0.8)
look.keyframe_insert('location', frame=1)
look.location = (0, 1, 3.5)
look.keyframe_insert('location', frame=72)

for fc in look.animation_data.action.fcurves:
    for kf in fc.keyframe_points:
        kf.interpolation = 'BEZIER'

print("✅ 山坡场景已生成")
