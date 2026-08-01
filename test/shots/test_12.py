"""
test_12.py — 咖啡馆门口：女人带小孩在外，男人在内看向他们
"""
import bpy, math

CHARS = "/Users/zengle/Documents/storyboard-3d-pipeline/characters"
OUT   = "/Users/zengle/Documents/storyboard-3d-pipeline/render/test_12"

bpy.ops.object.select_all(action='SELECT')
bpy.ops.object.delete()

scene = bpy.context.scene
scene.render.engine = 'BLENDER_EEVEE_NEXT'
scene.render.resolution_x = 1920
scene.render.resolution_y = 1080

# ============================================================
# 材质
# ============================================================
def mat(name, color):
    m = bpy.data.materials.new(name)
    m.use_nodes = True; m.diffuse_color = (*color, 1.0)
    for n in m.node_tree.nodes:
        if n.type == 'BSDF_PRINCIPLED': n.inputs["Base Color"].default_value = (*color, 1.0); break
    return m

M_WALL    = mat("Wall",    (0.82, 0.78, 0.70))
M_FLOOR   = mat("Floor",   (0.38, 0.34, 0.30))
M_ROOF    = mat("Roof",    (0.55, 0.30, 0.18))

# ============================================================
# 导入角色
# ============================================================
def import_fbx(path, name, loc, rot_z=0):
    pre = set(bpy.data.objects.keys())
    bpy.ops.import_scene.fbx(filepath=path)
    new_objs = set(bpy.data.objects.keys()) - pre
    # 找 armature 对象
    arm = None
    for n in new_objs:
        o = bpy.data.objects[n]
        if o.type == 'ARMATURE':
            arm = o
            break
    arm.name = name
    arm.location = loc
    arm.rotation_euler.z = rot_z
    return arm

man_arm  = import_fbx(f"{CHARS}/male_mixamo_stand.fbx", "Man", (0, 1.5, 0), 0)
woman_arm = import_fbx(f"{CHARS}/female_mixamo_stand.fbx", "Woman", (-0.7, -1.5, 0), math.pi)
child_arm = import_fbx(f"{CHARS}/child_mixamo_stand.fbx", "Child", (0.5, -1.6, 0), math.pi)

# 隐藏所有骨架
for o in bpy.data.objects:
    if o.type == 'ARMATURE':
        o.hide_viewport = True

# ============================================================
# 咖啡馆建筑
# ============================================================
def wall(name, loc, dims):
    bpy.ops.mesh.primitive_cube_add(size=1, location=loc)
    w = bpy.context.active_object; w.name = name
    w.dimensions = dims; bpy.ops.object.transform_apply(scale=True)
    w.data.materials.append(M_WALL)

# 后墙
wall("BackWall",  (0, 3.0, 1.5), (5, 0.2, 3))
# 左墙
wall("LeftWall",  (-2.5, 1.2, 1.5), (0.2, 3.6, 3))
# 右墙
wall("RightWall", (2.5, 1.2, 1.5), (0.2, 3.6, 3))

# 前墙：大门洞（高2.4m），男人2m可通行
# 左门柱（加高）
wall("DoorL", (-1.4, -0.5, 1.2), (0.3, 0.3, 2.4))
# 右门柱
wall("DoorR", (1.4, -0.5, 1.2), (0.3, 0.3, 2.4))
# 门上方横梁
wall("DoorTop", (0, -0.5, 2.5), (3.0, 0.3, 0.15))
# 门上方墙体（缩到屋顶之间）
wall("FrontTop", (0, -0.5, 2.75), (5, 0.2, 0.5))

# 地面
bpy.ops.mesh.primitive_plane_add(size=12, location=(0, 0.8, 0))
bpy.context.active_object.name = "Floor"
bpy.context.active_object.data.materials.append(M_FLOOR)

# 屋顶
wall("Roof", (0, 1.2, 3.0), (5.2, 4.0, 0.1))
bpy.data.objects["Roof"].data.materials.clear()
bpy.data.objects["Roof"].data.materials.append(M_ROOF)

# ============================================================
# 灯光
# ============================================================
bpy.ops.object.light_add(type='SUN', location=(5, -5, 10))
bpy.context.active_object.data.energy = 3
bpy.ops.object.light_add(type='AREA', location=(0, -1, 3))
bpy.context.active_object.data.energy = 150; bpy.context.active_object.data.size = 4

# ============================================================
# 摄像机
# ============================================================
bpy.ops.object.camera_add(location=(0, -3.5, 1.5))
cam = bpy.context.active_object; cam.data.lens = 24; scene.camera = cam
bpy.ops.object.empty_add(type='PLAIN_AXES', location=(0, 0.3, 1.2))
look = bpy.context.active_object
c = cam.constraints.new(type='TRACK_TO')
c.target = look; c.track_axis = 'TRACK_NEGATIVE_Z'; c.up_axis = 'UP_Y'

# ============================================================
# 渲染
# ============================================================
scene.render.filepath = f"{OUT}.png"
scene.render.image_settings.file_format = 'PNG'
bpy.ops.render.render(write_still=True)
bpy.ops.wm.save_as_mainfile(filepath=f"{OUT}.blend")
print("✅ test_12 已生成")
