"""
test_02.py — 过肩镜头：两人对话
- 蓝衣（CharB）：前方 y=1.0，面向镜头，画面主体
- 红衣（CharA）：靠近镜头 y=-0.5，偏右 x=0.5，过肩入画
- 镜头：从红衣右肩后方推近，定格在蓝衣面部
"""
import bpy
import math

# ============================================================
# 1. 清空场景
# ============================================================
bpy.ops.object.select_all(action='SELECT')
bpy.ops.object.delete()

# ============================================================
# 2. 场景设置
# ============================================================
scene = bpy.context.scene
scene.render.resolution_x = 1920
scene.render.resolution_y = 1080
scene.render.resolution_percentage = 100
scene.render.fps = 24
scene.frame_start = 1
scene.frame_end = 72  # 3秒
scene.render.filepath = "/Users/zengle/Documents/storyboard-3d-pipeline/render/test_02.mp4"
scene.render.image_settings.file_format = 'FFMPEG'
scene.render.ffmpeg.format = 'MPEG4'
scene.render.ffmpeg.codec = 'H264'
scene.render.engine = 'BLENDER_EEVEE_NEXT'

# 环境光
world = bpy.data.worlds.new("World")
scene.world = world
world.use_nodes = True
for node in world.node_tree.nodes:
    if node.type == 'BACKGROUND':
        node.inputs["Color"].default_value = (0.05, 0.05, 0.08, 1.0)
        node.inputs["Strength"].default_value = 0.3
        break

# ============================================================
# 3. 灯光
# ============================================================
bpy.ops.object.light_add(type='SUN', location=(5, -5, 10))
sun = bpy.context.active_object
sun.data.energy = 3

bpy.ops.object.light_add(type='AREA', location=(0, 0, 3))
fill = bpy.context.active_object
fill.data.energy = 50
fill.data.size = 5

# ============================================================
# 4. 材质函数（视口+渲染双设）
# ============================================================
def make_material(name, color, roughness=0.7):
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    mat.diffuse_color = color
    for node in mat.node_tree.nodes:
        if node.type == 'BSDF_PRINCIPLED':
            node.inputs["Base Color"].default_value = color
            node.inputs["Roughness"].default_value = roughness
            break
    return mat

# ============================================================
# 5. 地面
# ============================================================
bpy.ops.mesh.primitive_plane_add(size=20, location=(0, 0, 0))
floor = bpy.context.active_object
floor.name = "Floor"
floor.data.materials.append(make_material("FloorMat", (0.35, 0.30, 0.25, 1.0)))

# ============================================================
# 6. 人物创建函数
# ============================================================
def create_character(name, location, body_color, head_color, facing_angle=0):
    # 身体（拉伸立方体）— 更接近真人比例
    bpy.ops.mesh.primitive_cube_add(size=0.5, location=(location[0], location[1], location[2] + 1.0))
    body = bpy.context.active_object
    body.name = f"{name}_Body"
    body.scale = (1.2, 0.8, 2.0)  # 宽0.6 深0.4 高1.0 → 总身高约1.8m
    bpy.ops.object.transform_apply(scale=True)
    body.rotation_euler = (0, 0, facing_angle)
    body.data.materials.append(make_material(f"{name}BodyMat", body_color))

    # 头（球体）— 更大
    bpy.ops.mesh.primitive_uv_sphere_add(radius=0.22, location=(location[0], location[1], location[2] + 1.75))
    head = bpy.context.active_object
    head.name = f"{name}_Head"
    head.data.materials.append(make_material(f"{name}HeadMat", head_color))
    head.parent = body
    return body

# ============================================================
# 7. 创建两个人物
# ============================================================
# 蓝衣（前方主体，面向镜头）
# 镜头在 -Y 方向，蓝衣面向镜头 = facing_angle=pi（转180度面朝 -Y）
char_b = create_character(
    name="CharB",
    location=(0, 1.0, 0),       # 居中，前方
    body_color=(0.2, 0.3, 0.6, 1.0),   # 蓝色
    head_color=(0.95, 0.85, 0.70, 1.0), # 肤色
    facing_angle=math.pi        # 面向镜头（-Y方向）
)

# 红衣（靠近镜头，偏右侧，过肩入画）
# 面向蓝衣方向 = 大致面向 +Y，稍微侧转
char_a = create_character(
    name="CharA",
    location=(0.7, -0.5, 0),    # 更靠右、更靠近镜头，避免遮挡蓝衣
    body_color=(0.7, 0.2, 0.2, 1.0),   # 红色
    head_color=(0.95, 0.85, 0.70, 1.0), # 肤色
    facing_angle=math.pi / 6     # 稍微侧转面向蓝衣
)

# ============================================================
# 8. 镜头设置
# ============================================================
bpy.ops.object.camera_add()
camera = bpy.context.active_object
camera.name = "ShotCamera"
scene.camera = camera
camera.data.lens = 35
camera.data.clip_end = 100

# 过肩镜头：从红衣右肩后方 → 推近到蓝衣面部特写
# 蓝衣头部在 (0, 1.0, 1.75)，要推到约 1.2m 距离拍面部特写
cam_start = (0.7, -3.0, 1.6)   # 远处：能看到两人
cam_end   = (0.5, -0.2, 1.6)   # 近处：蓝衣面部占画面约40%

camera.location = cam_start
camera.keyframe_insert("location", frame=1)
camera.location = cam_end
camera.keyframe_insert("location", frame=60)
camera.location = cam_end
camera.keyframe_insert("location", frame=72)

# 缓入缓出
for fc in camera.animation_data.action.fcurves:
    for kf in fc.keyframe_points:
        kf.interpolation = 'BEZIER'

# 注视目标：始终看向蓝衣
bpy.ops.object.empty_add(type='PLAIN_AXES', location=(0, 1.0, 1.5))
look_at = bpy.context.active_object
look_at.name = "LookTarget"

# 起始看蓝衣上半身 → 结束聚焦蓝衣头部
look_at.location = (0, 1.0, 1.3)
look_at.keyframe_insert("location", frame=1)
look_at.location = (0, 1.0, 1.75)
look_at.keyframe_insert("location", frame=60)
look_at.keyframe_insert("location", frame=72)

for fc in look_at.animation_data.action.fcurves:
    for kf in fc.keyframe_points:
        kf.interpolation = 'BEZIER'

constraint = camera.constraints.new(type='TRACK_TO')
constraint.target = look_at
constraint.track_axis = 'TRACK_NEGATIVE_Z'
constraint.up_axis = 'UP_Y'

# ============================================================
# 9. 渲染
# ============================================================
print(f"开始渲染: {scene.frame_start}-{scene.frame_end} 帧")
bpy.ops.render.render(animation=True)
bpy.ops.wm.save_as_mainfile(filepath="/Users/zengle/Documents/storyboard-3d-pipeline/render/test_02.blend")
print("渲染完成! .blend 已保存")
