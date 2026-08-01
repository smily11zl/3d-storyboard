"""
test_07.py — 咖啡馆场景：男女面对面交谈
- 使用 low-poly 骨骼角色模型（male.blend / female.blend）
- 简单咖啡馆环境
"""
import bpy
import math

CHAR_DIR = "/Users/zengle/Documents/storyboard-3d-pipeline/characters"
OUT_DIR  = "/Users/zengle/Documents/storyboard-3d-pipeline/render"

# ============================================================
# 1. 清空
# ============================================================
bpy.ops.object.select_all(action='SELECT')
bpy.ops.object.delete()

scene = bpy.context.scene
scene.render.engine = 'BLENDER_EEVEE_NEXT'
scene.render.resolution_x = 1920
scene.render.resolution_y = 1080
scene.render.fps = 24
scene.frame_start = 1
scene.frame_end = 1

# ============================================================
# 2. 环境材质
# ============================================================
def make_material(name, color):
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    mat.diffuse_color = (*color, 1.0)
    for node in mat.node_tree.nodes:
        if node.type == 'BSDF_PRINCIPLED':
            node.inputs["Base Color"].default_value = (*color, 1.0)
            node.inputs["Roughness"].default_value = 0.7
            break
    return mat

MAT_FLOOR   = make_material("Floor",   (0.35, 0.30, 0.25))
MAT_WALL    = make_material("Wall",    (0.78, 0.74, 0.68))
MAT_COUNTER = make_material("Counter", (0.40, 0.32, 0.22))
MAT_TABLE   = make_material("Table",   (0.38, 0.25, 0.15))
MAT_CHAIR   = make_material("Chair",   (0.22, 0.20, 0.18))
MAT_CUP     = make_material("Cup",     (0.90, 0.90, 0.85))

# ============================================================
# 3. 地面
# ============================================================
bpy.ops.mesh.primitive_plane_add(size=14, location=(0, 1.5, 0))
bpy.context.active_object.name = "Floor"
bpy.context.active_object.data.materials.append(MAT_FLOOR)

# ============================================================
# 4. 墙壁（三面，正面开放）
# ============================================================
# 后墙
bpy.ops.mesh.primitive_cube_add(size=1, location=(0, 4.5, 1.5))
w = bpy.context.active_object
w.name = "BackWall"; w.dimensions = (6.5, 0.15, 3); bpy.ops.object.transform_apply(scale=True)
w.data.materials.append(MAT_WALL)

# 左墙
bpy.ops.mesh.primitive_cube_add(size=1, location=(-3.25, 1.5, 1.5))
w = bpy.context.active_object
w.name = "LeftWall"; w.dimensions = (0.15, 6, 3); bpy.ops.object.transform_apply(scale=True)
w.data.materials.append(MAT_WALL)

# 右墙
bpy.ops.mesh.primitive_cube_add(size=1, location=(3.25, 1.5, 1.5))
w = bpy.context.active_object
w.name = "RightWall"; w.dimensions = (0.15, 6, 3); bpy.ops.object.transform_apply(scale=True)
w.data.materials.append(MAT_WALL)

# ============================================================
# 5. 柜台（后墙前）
# ============================================================
bpy.ops.mesh.primitive_cube_add(size=1, location=(0, 3.8, 0.55))
counter = bpy.context.active_object
counter.name = "Counter"; counter.dimensions = (4.5, 0.6, 1.1)
bpy.ops.object.transform_apply(scale=True)
counter.data.materials.append(MAT_COUNTER)
# 柜台上的杯子
for dx in [-1.2, -0.4, 0.5, 1.3]:
    bpy.ops.mesh.primitive_cylinder_add(radius=0.05, depth=0.12, location=(dx, 4.1, 1.1))
    bpy.context.active_object.data.materials.append(MAT_CUP)

# ============================================================
# 6. 桌椅
# ============================================================
for tx in [-2.0, 0, 2.0]:
    # 桌子
    bpy.ops.mesh.primitive_cube_add(size=1, location=(tx, 2.2, 0.72))
    t = bpy.context.active_object
    t.name = f"Table_{tx}"; t.dimensions = (1.2, 0.7, 0.08)
    bpy.ops.object.transform_apply(scale=True)
    t.data.materials.append(MAT_TABLE)
    # 桌腿
    for lx, ly in [(-0.5,-0.25), (0.5,-0.25), (-0.5,0.25), (0.5,0.25)]:
        bpy.ops.mesh.primitive_cylinder_add(radius=0.04, depth=0.65, location=(tx+lx, 2.2+ly, 0.35))
        bpy.context.active_object.data.materials.append(MAT_TABLE)
    # 椅子（桌子两侧）
    for cy in [1.6, 2.8]:
        bpy.ops.mesh.primitive_cube_add(size=1, location=(tx, cy, 0.42))
        c = bpy.context.active_object
        c.name = f"Chair_{tx}_{cy}"; c.dimensions = (0.45, 0.45, 0.06)
        bpy.ops.object.transform_apply(scale=True)
        c.data.materials.append(MAT_CHAIR)
        for lx, ly in [(-0.16,-0.16),(0.16,-0.16),(-0.16,0.16),(0.16,0.16)]:
            bpy.ops.mesh.primitive_cylinder_add(radius=0.02, depth=0.35, location=(tx+lx, cy+ly, 0.18))
            bpy.context.active_object.data.materials.append(MAT_CHAIR)
        # 靠背
        bpy.ops.mesh.primitive_cube_add(size=1, location=(tx, cy+0.2, 0.78))
        b = bpy.context.active_object
        b.dimensions = (0.4, 0.05, 0.6); bpy.ops.object.transform_apply(scale=True)
        b.data.materials.append(MAT_CHAIR)

# ============================================================
# 7. 导入男女角色（用 wm.append 逐个导入） 
# ============================================================
def import_character(blend_path):
    """从 blend 文件导入整个 Collection"""
    bpy.ops.wm.append(
        filepath=f"{blend_path}/Collection/",
        directory=f"{blend_path}/Collection/",
        filename="Collection"
    )

# 男性
import_character(f"{CHAR_DIR}/male.blend")
# 女性
import_character(f"{CHAR_DIR}/female.blend")

# ============================================================
# 8. 角色定位：面对面站立
# ============================================================
# 导入后网格名: Character, Character.001 (和骨架同名对应)
meshes = [o for o in bpy.data.objects if o.type == 'MESH' and 'Character' in o.name]
armatures = [o for o in bpy.data.objects if o.type == 'ARMATURE']

# 男性放左侧，女性放右侧
# 按导入顺序: male 先→Character, female 后→Character.001
male_mesh = meshes[0] if len(meshes) > 0 else None
female_mesh = meshes[1] if len(meshes) > 1 else None

# 匹配骨架
for a in armatures:
    mod = None
    for m in meshes:
        if m.modifiers and m.modifiers[0].object == a:
            mod = m
            break
    if mod == male_mesh:
        a.location = (-1.0, 1.5, 0)
        a.rotation_euler.z = math.pi/2  # 男性面向右(女性) — 验证正确值
        print(f"  男性骨架 {a.name} → (-1.0, 1.5, 0) rot=90°")
    elif mod == female_mesh:
        a.location = (1.0, 1.5, 0)
        a.rotation_euler.z = -math.pi/2  # 女性面向左(男性) — 验证正确值
        print(f"  女性骨架 {a.name} → (1.0, 1.5, 0) rot=-90°")
    else:
        a.location = (0, 0, 0)  # 其他骨架归位

# ============================================================
# 9. 摄像机
# ============================================================
bpy.ops.object.camera_add(location=(0, -1.5, 1.5))
cam = bpy.context.active_object
cam.name = "ShotCamera"; cam.data.lens = 24
scene.camera = cam

bpy.ops.object.empty_add(type='PLAIN_AXES', location=(0, 1.5, 1.2))
look = bpy.context.active_object
c = cam.constraints.new(type='TRACK_TO')
c.target = look; c.track_axis = 'TRACK_NEGATIVE_Z'; c.up_axis = 'UP_Y'

# ============================================================
# 10. 灯光
# ============================================================
bpy.ops.object.light_add(type='AREA', location=(0, 0, 3.5))
l = bpy.context.active_object; l.data.energy = 200; l.data.size = 5

bpy.ops.object.light_add(type='AREA', location=(0, 3, 2))
l = bpy.context.active_object; l.data.energy = 150; l.data.size = 3

# ============================================================
# 11. 保存
# ============================================================
bpy.ops.wm.save_as_mainfile(filepath=f"{OUT_DIR}/test_07.blend")
print("✅ 咖啡馆面对面场景已生成")
print(f"   男性: (-1.0, 1.5, 0) 面向 +x → 女性")
print(f"   女性: (1.0, 1.5, 0) 面向 -x → 男性")
print(f"   摄像机: (0, -1.5, 1.5) 看两人中间")
