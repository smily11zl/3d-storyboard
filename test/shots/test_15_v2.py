"""
test_15_v2.py — 别墅: 镜头从男人沿楼梯上二楼停女人
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
scene.frame_end = 110
scene.eevee.use_shadows = False

# ---- 材质 ----
def mat(name, color):
    m = bpy.data.materials.new(name); m.use_nodes = True; m.diffuse_color = (*color, 1.0)
    for n in m.node_tree.nodes:
        if n.type == 'BSDF_PRINCIPLED': n.inputs["Base Color"].default_value = (*color, 1.0); break
    return m

MW = mat('Wall',  (0.88, 0.85, 0.78))
MF = mat('Floor', (0.40, 0.30, 0.22))
MG = mat('Ground',(0.35, 0.45, 0.25))
MR = mat('Rail',  (0.50, 0.35, 0.22))
MS = mat('Stair', (0.55, 0.40, 0.28))

def box(name, loc, dims, m):
    bpy.ops.mesh.primitive_cube_add(size=1, location=loc)
    w = bpy.context.active_object; w.name = name; w.dimensions = dims
    bpy.ops.object.transform_apply(scale=True); w.data.materials.append(m)

# ---- 步骤1: 场景 ----
bpy.ops.mesh.primitive_plane_add(size=20, location=(0,0,0))
bpy.context.active_object.data.materials.append(MG)

box('BackWall',  (0, 3, 3),     (8, 0.2, 6), MW)
box('LeftWall',  (-4, 0, 3),    (0.2, 6, 6), MW)
box('RightWall', (4, 0, 3),     (0.2, 6, 6), MW)
box('Floor2',    (0, 1.5, 3),   (8, 3, 0.15), MF)
box('Railing',   (0, -0.1, 3.85),(8.5, 0.05, 1.7), MR)
box('Roof',      (0, 1.5, 6),   (8.4, 6.4, 0.1), MW)

for i in range(6):
    box(f'Step_{i}', (3.5, -1.5 + i*0.5 + 0.25, i*0.5 + 0.25), (0.8, 0.5, 0.5), MS)

# ---- 灯光 ----
bpy.ops.object.light_add(type='SUN', location=(5,-5,10))
bpy.context.active_object.data.energy=3; bpy.context.active_object.data.use_shadow=False
bpy.ops.object.light_add(type='AREA', location=(0,0,5))
l=bpy.context.active_object; l.data.energy=200; l.data.size=8; l.data.use_shadow=False

# ---- 步骤2: 人物 ----
def load_char(fbx, name, loc, rot_z):
    pre = set(bpy.data.objects.keys())
    bpy.ops.import_scene.fbx(filepath=f"{CHAR}/{fbx}")
    arm = [o for o in bpy.data.objects if o.type=='ARMATURE' and o.name not in pre][0]
    arm.location = loc; arm.rotation_euler.z = rot_z
    arm.name = name; arm.hide_viewport = True
    return arm

MAN   = (0, -1.5, 0);   MAN_R   = math.pi  # 面朝+Y(楼上)
WOMAN = (0, 1.5, 3);    WOMAN_R = 0         # 面朝-Y(楼下)

load_char("male_mixamo_stand.fbx", "Man", MAN, MAN_R)
load_char("female_mixamo_stand.fbx", "Woman", WOMAN, WOMAN_R)

# ---- 步骤3: 镜头 ----
bpy.ops.object.camera_add()
cam = bpy.context.active_object; cam.data.lens = 28; scene.camera = cam
bpy.ops.object.empty_add(type='PLAIN_AXES')
look = bpy.context.active_object; look.name = "LookTarget"
c = cam.constraints.new(type='TRACK_TO')
c.target = look; c.track_axis = 'TRACK_NEGATIVE_Z'; c.up_axis = 'UP_Y'

# 1. 男人全身(1-30)
cam.location = (0, 2.5, 1.0)
cam.keyframe_insert('location', frame=1)
cam.keyframe_insert('location', frame=30)
look.location = (0, -1.5, 0.8)    # 男人胸部
look.keyframe_insert('location', frame=1)
look.keyframe_insert('location', frame=30)

# 2. 沿楼梯上移至女人(30-80)
cam.location = (3.5, 0, 3)        # 楼梯顶附近
cam.keyframe_insert('location', frame=80)
look.location = (2, 0.5, 2.5)     # 楼梯中段
look.keyframe_insert('location', frame=50)
look.location = (0, 1.5, 3.8)     # 女人胸部
look.keyframe_insert('location', frame=80)

# 3. 女人停留(80-110)
cam.location = (0, 0, 4.7)        # cam_front(女人)结果
cam.keyframe_insert('location', frame=110)
look.keyframe_insert('location', frame=110)

for fc in cam.animation_data.action.fcurves:
    for kf in fc.keyframe_points: kf.interpolation = 'LINEAR'
for fc in look.animation_data.action.fcurves:
    for kf in fc.keyframe_points: kf.interpolation = 'LINEAR'

# ---- 步骤4: 渲染 + 自检 ----
scene.render.filepath = f"{OUT}/test_15_v2.png"
scene.render.image_settings.file_format = 'PNG'
bpy.ops.render.render(write_still=True)

for f in [1, 30, 50, 80, 110]:
    scene.frame_set(f)
    scene.render.filepath = f"{OUT}/test_15_v2_f{f:03d}.png"
    bpy.ops.render.render(write_still=True)

bpy.ops.wm.save_as_mainfile(filepath=f"{OUT}/test_15_v2.blend")

# 自检: 帧110摄像机在女人前方?
scene.frame_set(110)
dx = cam.matrix_world.translation.x - WOMAN[0]
dy = cam.matrix_world.translation.y - WOMAN[1]
face_dir = (math.sin(WOMAN_R), -math.cos(WOMAN_R))
dot = dx*face_dir[0] + dy*face_dir[1]
actual = 'front' if dot > 0 else 'behind'
print(f'帧110 女人: 预期front 实际{actual} {"✓" if actual=="front" else "✗"}')

scene.frame_set(1)
dx = cam.matrix_world.translation.x - MAN[0]
dy = cam.matrix_world.translation.y - MAN[1]
face_dir = (math.sin(MAN_R), -math.cos(MAN_R))
dot = dx*face_dir[0] + dy*face_dir[1]
actual = 'front' if dot > 0 else 'behind'
print(f'帧1 男人: 预期front 实际{actual} {"✓" if actual=="front" else "✗"}')

print("✅ test_15_v2 已生成")
