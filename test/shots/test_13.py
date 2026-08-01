"""
test_13.py — 山景：女人山下，男人半山腰看山下
镜头：女人背后 → 男人面前停留 → 后退展示整座山
"""
import bpy, math

CHAR = "/Users/zengle/Documents/storyboard-3d-pipeline/characters"
OUT  = "/Users/zengle/Documents/storyboard-3d-pipeline/render"

bpy.ops.object.select_all(action='SELECT')
bpy.ops.object.delete()

scene = bpy.context.scene
scene.render.engine = 'BLENDER_EEVEE_NEXT'
scene.render.resolution_x = 1920
scene.render.resolution_y = 1080
scene.render.fps = 24
scene.frame_start = 1
scene.frame_end = 120  # 5秒

# ============================================================
# 包围盒
# ============================================================
# 山: cone center=(0,0,2.5) r=7 h=5
# 女人: (0,-7,0) dist=7 → 山脚南边缘
# 男人: (0,-3,2.86) dist=3 → 南坡, 比女人高
# 两人都在山体南侧，视线不穿山 ✓
MAN_Z = 2.86

# ============================================================
# 材质
# ============================================================
def mat(name, color):
    m = bpy.data.materials.new(name)
    m.use_nodes = True; m.diffuse_color = (*color, 1.0)
    for n in m.node_tree.nodes:
        if n.type == 'BSDF_PRINCIPLED':
            n.inputs["Base Color"].default_value = (*color, 1.0); break
    return m

M_GROUND  = mat("Ground",  (0.35, 0.45, 0.25))
M_MOUNT   = mat("Mountain",(0.40, 0.42, 0.35))
M_SNOW    = mat("Snow",    (0.95, 0.95, 0.92))

# ============================================================
# 地面 + 山
# ============================================================
bpy.ops.mesh.primitive_plane_add(size=30, location=(0, 1, 0))
bpy.context.active_object.data.materials.append(M_GROUND)

bpy.ops.mesh.primitive_cone_add(vertices=32, radius1=7, radius2=0, depth=5, location=(0, 0, 2.5))
mountain = bpy.context.active_object; mountain.name = "Mountain"
mountain.data.materials.append(M_MOUNT)

bpy.ops.mesh.primitive_uv_sphere_add(radius=0.4, location=(0, 0, 4.8))
bpy.context.active_object.data.materials.append(M_SNOW)

# ============================================================
# 导入角色
# ============================================================
def load_char(fbx, name, loc, rot_z):
    pre = set(bpy.data.objects.keys())
    bpy.ops.import_scene.fbx(filepath=f"{CHAR}/{fbx}")
    arm = [o for o in bpy.data.objects if o.type=='ARMATURE' and o.name not in pre][0]
    arm.location = loc; arm.rotation_euler.z = rot_z
    arm.name = name; arm.hide_viewport = True
    return arm

# 女人山脚边缘，面朝山上(男人方向)
woman = load_char("female_mixamo_stand.fbx", "Woman", (0, -7, 0), math.pi)

# 男人南坡中部，面朝山下
man = load_char("male_mixamo_stand.fbx", "Man", (0, -3, MAN_Z), 0)

# ============================================================
# 树木(山坡上)
# ============================================================
import random; random.seed(42)
for _ in range(20):
    angle = random.uniform(0, 2*math.pi)
    dist = random.uniform(1, 6.5)
    tx = dist*math.cos(angle); ty = dist*math.sin(angle)
    surf = 5*(1-dist/7)
    if surf < 0.3 or (abs(tx)<1 and -7<ty<0): continue
    bpy.ops.mesh.primitive_cylinder_add(radius=0.06, depth=1.0, location=(tx, ty, surf+0.5))
    bpy.context.active_object.data.materials.append(mat("Bark", (0.3, 0.2, 0.12)))
    bpy.ops.mesh.primitive_uv_sphere_add(radius=0.35, location=(tx, ty, surf+1.3))
    bpy.context.active_object.data.materials.append(mat("Leaf", (0.18, 0.4, 0.15)))

# ============================================================
# 灯光
# ============================================================
bpy.ops.object.light_add(type='SUN', location=(5, -5, 10))
bpy.context.active_object.data.energy = 3
bpy.context.active_object.data.use_shadow = False
bpy.ops.object.light_add(type='AREA', location=(0, 0, 6))
l = bpy.context.active_object; l.data.energy = 200; l.data.size = 8; l.data.use_shadow = False
scene.eevee.use_shadows = False

# ============================================================
# 镜头动画
# ============================================================
bpy.ops.object.camera_add()
cam = bpy.context.active_object; cam.name = "ShotCamera"; cam.data.lens = 28
scene.camera = cam

bpy.ops.object.empty_add(type='PLAIN_AXES', location=(0, 4, 2))
look = bpy.context.active_object; look.name = "LookTarget"
c = cam.constraints.new(type='TRACK_TO')
c.target = look; c.track_axis = 'TRACK_NEGATIVE_Z'; c.up_axis = 'UP_Y'

# 三阶段:
# 1. 帧1-40: 女人背后→男人面前
# 2. 帧40-80: 停在男人面前
# 3. 帧80-120: 后退俯拍整座山

cam.location = (0, -8.5, 1.2)
cam.keyframe_insert('location', frame=1)
cam.location = (0.3, -3.5, MAN_Z + 1.3)
cam.keyframe_insert('location', frame=40)
cam.location = (0.3, -3.5, MAN_Z + 1.3)
cam.keyframe_insert('location', frame=80)
cam.location = (0, -3, 8)
cam.keyframe_insert('location', frame=120)

for fc in cam.animation_data.action.fcurves:
    for kf in fc.keyframe_points: kf.interpolation = 'BEZIER'

# 注视目标
bpy.ops.object.empty_add(type='PLAIN_AXES', location=(0, 3, 2))
look = bpy.context.active_object; look.name = "LookTarget"
c = cam.constraints.new(type='TRACK_TO')
c.target = look; c.track_axis = 'TRACK_NEGATIVE_Z'; c.up_axis = 'UP_Y'

look.location = (0, -3, MAN_Z + 1.3)
look.keyframe_insert('location', frame=1)
look.location = (0, -3, MAN_Z + 1.3)
look.keyframe_insert('location', frame=80)
look.location = (0, 0, 2.5)
look.keyframe_insert('location', frame=120)

for fc in look.animation_data.action.fcurves:
    for kf in fc.keyframe_points: kf.interpolation = 'BEZIER'

# ============================================================
# 渲染 + 保存
# ============================================================
scene.render.filepath = f"{OUT}/test_13.png"
scene.render.image_settings.file_format = 'PNG'
bpy.ops.render.render(write_still=True)
bpy.ops.wm.save_as_mainfile(filepath=f"{OUT}/test_13.blend")

# 渲染关键帧预览
for f in [1, 40, 80, 120]:
    scene.frame_set(f)
    scene.render.filepath = f"{OUT}/test_13_f{f:03d}.png"
    bpy.ops.render.render(write_still=True)

print("✅ test_13 已生成")
