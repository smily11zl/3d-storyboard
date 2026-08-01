"""
test_14_v2.py — 摄像机相对位置公式版
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
# 摄像机位置公式
# ============================================================
def cam_behind(pos, rot_z, height=2.0, dist=1.5):
    """人物背后(拍背影) — 站位在人物面朝方向的反方向"""
    face_z = height * 0.85  # 面部高度≈身高的85%
    return (pos[0] - dist*math.sin(rot_z),
            pos[1] + dist*math.cos(rot_z),
            pos[2] + face_z)

def cam_front(pos, rot_z, height=2.0, dist=1.5):
    """人物正前方(拍正脸) — 站位在人物面朝方向"""
    face_z = height * 0.85
    return (pos[0] + dist*math.sin(rot_z),
            pos[1] - dist*math.cos(rot_z),
            pos[2] + face_z)

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

# ============================================================
# 步骤1: 场景
# ============================================================
bpy.ops.mesh.primitive_plane_add(size=30, location=(0, 0, 0))
bpy.context.active_object.data.materials.append(mat('Ground', (0.3, 0.5, 0.25)))

bpy.ops.mesh.primitive_cone_add(vertices=32, radius1=7, radius2=0, depth=5, location=(0, 0, 2.5))
bpy.context.active_object.data.materials.append(mat('Mountain', (0.40, 0.42, 0.35)))

bpy.ops.mesh.primitive_uv_sphere_add(radius=0.4, location=(0, 0, 4.8))
bpy.context.active_object.data.materials.append(mat('Snow', (0.95, 0.95, 0.92)))

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

WOMAN_POS = (0, -7, 0);   WOMAN_ROT = math.pi     # 面朝+Y(山上)
MAN_POS   = (0, -3.5, 2.5); MAN_ROT = 0            # 面朝-Y(山下)

load_char("female_mixamo_stand.fbx", "Woman", WOMAN_POS, WOMAN_ROT)
load_char("male_mixamo_stand.fbx", "Man", MAN_POS, MAN_ROT)

# ============================================================
# 灯光
# ============================================================
bpy.ops.object.light_add(type='SUN', location=(5, -5, 10))
bpy.context.active_object.data.energy = 3; bpy.context.active_object.data.use_shadow = False
bpy.ops.object.light_add(type='AREA', location=(0, 0, 6))
l = bpy.context.active_object; l.data.energy = 200; l.data.size = 8; l.data.use_shadow = False
scene.eevee.use_shadows = False

# ============================================================
# 步骤3: 镜头 — 公式驱动
# ============================================================
bpy.ops.object.camera_add()
cam = bpy.context.active_object; cam.data.lens = 28; scene.camera = cam

bpy.ops.object.empty_add(type='PLAIN_AXES')
look = bpy.context.active_object; look.name = "LookTarget"
c = cam.constraints.new(type='TRACK_TO')
c.target = look; c.track_axis = 'TRACK_NEGATIVE_Z'; c.up_axis = 'UP_Y'

# 1. 女人背后停留 (1-40)
p = cam_behind(WOMAN_POS, WOMAN_ROT, dist=1.5)
cam.location = p; cam.keyframe_insert('location', frame=1)
cam.keyframe_insert('location', frame=40)

# 2. 移动到男人正脸 (40-80)
p = cam_front(MAN_POS, MAN_ROT, dist=1.5)
cam.location = p; cam.keyframe_insert('location', frame=80)
# 3. 停留 (80-120)
cam.keyframe_insert('location', frame=120)

# 4. 后拉 (120-160)
cam.location = (0, -2, 8); cam.keyframe_insert('location', frame=160)

# 注视点: 男人面部(身高的85%) → 山心
FACE_Z = MAN_POS[2] + 1.7   # 2m身高 × 0.85
look.location = (MAN_POS[0], MAN_POS[1], FACE_Z)
look.keyframe_insert('location', frame=1)
look.keyframe_insert('location', frame=120)
look.location = (0, 0, 2.5)
look.keyframe_insert('location', frame=160)

for fc in cam.animation_data.action.fcurves:
    for kf in fc.keyframe_points: kf.interpolation = 'LINEAR'
for fc in look.animation_data.action.fcurves:
    for kf in fc.keyframe_points: kf.interpolation = 'LINEAR'

# ============================================================
# 渲染
# ============================================================
scene.render.filepath = f"{OUT}/test_14_v2.png"
scene.render.image_settings.file_format = 'PNG'
bpy.ops.render.render(write_still=True)

for f in [1, 80]:
    scene.frame_set(f)
    scene.render.filepath = f"{OUT}/test_14_v2_f{f:03d}.png"
    bpy.ops.render.render(write_still=True)

bpy.ops.wm.save_as_mainfile(filepath=f"{OUT}/test_14_v2.blend")
print("✅ test_14_v2 已生成")
