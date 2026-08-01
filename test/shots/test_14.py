"""
test_14.py — 山景：男人半山腰看山下女人
三步法：场景→人物→镜头
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
scene.frame_end = 160

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

M_GROUND  = mat("Ground",  (0.30, 0.50, 0.25))
M_MOUNT   = mat("Mountain",(0.40, 0.42, 0.35))
M_SNOW    = mat("Snow",    (0.95, 0.95, 0.92))
M_BARK    = mat("Bark",    (0.30, 0.20, 0.12))
M_LEAF    = mat("Leaf",    (0.18, 0.40, 0.15))

# ============================================================
# 步骤1: 场景
# ============================================================
bpy.ops.mesh.primitive_plane_add(size=30, location=(0, 0, 0))
bpy.context.active_object.data.materials.append(M_GROUND)

bpy.ops.mesh.primitive_cone_add(vertices=32, radius1=7, radius2=0, depth=5, location=(0, 0, 2.5))
bpy.context.active_object.data.materials.append(M_MOUNT)

bpy.ops.mesh.primitive_uv_sphere_add(radius=0.4, location=(0, 0, 4.8))
bpy.context.active_object.data.materials.append(M_SNOW)

# 树
import random; random.seed(42)
for _ in range(20):
    angle = random.uniform(0, 2*math.pi)
    dist = random.uniform(1, 6.5)
    tx = dist*math.cos(angle); ty = dist*math.sin(angle)
    surf = 5*(1-dist/7)
    if surf < 0.3 or (abs(tx)<1 and -6<ty<0): continue
    bpy.ops.mesh.primitive_cylinder_add(radius=0.06, depth=1, location=(tx, ty, surf+0.5))
    bpy.context.active_object.data.materials.append(M_BARK)
    bpy.ops.mesh.primitive_uv_sphere_add(radius=0.35, location=(tx, ty, surf+1.3))
    bpy.context.active_object.data.materials.append(M_LEAF)

# ============================================================
# 步骤2: 人物
# ============================================================
def load_char(fbx, name, loc, rot_z):
    pre = set(bpy.data.objects.keys())
    bpy.ops.import_scene.fbx(filepath=f"{CHAR}/{fbx}")
    arm = [o for o in bpy.data.objects if o.type=='ARMATURE' and o.name not in pre][0]
    arm.location = loc; arm.rotation_euler.z = rot_z
    arm.name = name; arm.hide_viewport = True
    return arm

# 女人: y=-7 山脚, rot=180°=面朝+Y(山上) → 看男人
load_char("female_mixamo_stand.fbx", "Woman", (0, -7, 0), math.pi)

# 男人: y=-3.5 南坡 z=2.5, rot=0°=面朝-Y(山下) → 看女人
MAN_Z = 2.5
load_char("male_mixamo_stand.fbx", "Man", (0, -3.5, MAN_Z), 0)

# ============================================================
# 灯光
# ============================================================
bpy.ops.object.light_add(type='SUN', location=(5, -5, 10))
bpy.context.active_object.data.energy = 3
bpy.context.active_object.data.use_shadow = False
bpy.ops.object.light_add(type='AREA', location=(0, 0, 6))
l = bpy.context.active_object; l.data.energy = 200; l.data.size = 8
l.data.use_shadow = False
scene.eevee.use_shadows = False

# ============================================================
# 步骤3: 镜头
# ============================================================
bpy.ops.object.camera_add()
cam = bpy.context.active_object; cam.data.lens = 28; scene.camera = cam

bpy.ops.object.empty_add(type='PLAIN_AXES')
look = bpy.context.active_object; look.name = "LookTarget"
c = cam.constraints.new(type='TRACK_TO')
c.target = look; c.track_axis = 'TRACK_NEGATIVE_Z'; c.up_axis = 'UP_Y'

# 1. 女人背后停留 (1-40)
cam.location = (0, -8.5, 1.2); cam.keyframe_insert('location', frame=1)
cam.location = (0, -8.5, 1.2); cam.keyframe_insert('location', frame=40)
# 2. 移动到男人面部 (40-80)
cam.location = (0, -4, MAN_Z + 1.3); cam.keyframe_insert('location', frame=80)
# 3. 停留男人面部 (80-120)
cam.location = (0, -4, MAN_Z + 1.3); cam.keyframe_insert('location', frame=120)
# 4. 后拉全山 (120-160)
cam.location = (0, -3, 8); cam.keyframe_insert('location', frame=160)

# 注视点: 男人面部(1-120) → 山心(160)
look.location = (0, -3.5, MAN_Z + 1.3); look.keyframe_insert('location', frame=1)
look.location = (0, -3.5, MAN_Z + 1.3); look.keyframe_insert('location', frame=120)
look.location = (0, 0, 2.5); look.keyframe_insert('location', frame=160)

for fc in cam.animation_data.action.fcurves:
    for kf in fc.keyframe_points:
        kf.interpolation = 'LINEAR'  # 避免Bezier过冲
for fc in look.animation_data.action.fcurves:
    for kf in fc.keyframe_points:
        kf.interpolation = 'LINEAR'

# ============================================================
# 渲染
# ============================================================
# 全帧
scene.render.filepath = f"{OUT}/test_14.png"
scene.render.image_settings.file_format = 'PNG'
bpy.ops.render.render(write_still=True)

# 关键帧
for f in [1, 40, 80, 120, 160]:
    scene.frame_set(f)
    scene.render.filepath = f"{OUT}/test_14_f{f:03d}.png"
    bpy.ops.render.render(write_still=True)

bpy.ops.wm.save_as_mainfile(filepath=f"{OUT}/test_14.blend")
print("✅ test_14 已生成")
