"""
测试镜头：两人对话 — 镜头从后方人物背后推近
- 人物A（前景）：站在前面，面朝镜头方向
- 人物B（背景）：站在A前面更远处，背对镜头
- 镜头：从B背后缓缓推近，最终定格在A的近景
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
scene.render.filepath = "/Users/zengle/Documents/storyboard-3d-pipeline/render/test_01.mp4"
scene.render.image_settings.file_format = 'FFMPEG'
scene.render.ffmpeg.format = 'MPEG4'
scene.render.ffmpeg.codec = 'H264'

# 使用 Eevee Next 渲染引擎
scene.render.engine = 'BLENDER_EEVEE_NEXT'

# 添加环境光（World），让渲染和视口预览一致
world = bpy.data.worlds.new("World")
scene.world = world
world.use_nodes = True
# 找到 Background 节点（不同版本名称可能不同）
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
# 4. 地面
# ============================================================
def make_material(name, color, roughness=0.7):
    """创建材质，同时设置视口颜色和渲染节点颜色（两者必须都设！）"""
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    # 视口显示颜色
    mat.diffuse_color = color
    # 渲染颜色：设置 Principled BSDF 的 Base Color
    for node in mat.node_tree.nodes:
        if node.type == 'BSDF_PRINCIPLED':
            node.inputs["Base Color"].default_value = color
            node.inputs["Roughness"].default_value = roughness
            break
    return mat

bpy.ops.mesh.primitive_plane_add(size=20, location=(0, 0, 0))
floor = bpy.context.active_object
floor.name = "Floor"
mat_floor = make_material("FloorMat", (0.35, 0.30, 0.25, 1.0))
floor.data.materials.append(mat_floor)


# ============================================================
# 5. 辅助函数：创建低多边形人物
# ============================================================
def create_character(name, location, body_color, head_color, facing_angle=0):
    """创建一个低多边形人物：胶囊身体 + 球头"""
    
    # 身体（拉伸立方体）
    bpy.ops.mesh.primitive_cube_add(size=0.4, location=(location[0], location[1], location[2] + 1.1))
    body = bpy.context.active_object
    body.name = f"{name}_Body"
    body.scale = (1.0, 0.7, 1.8)
    bpy.ops.object.transform_apply(scale=True)
    body.rotation_euler = (0, 0, facing_angle)
    mat_body = make_material(f"{name}BodyMat", body_color)
    body.data.materials.append(mat_body)
    
    # 头（球体）
    bpy.ops.mesh.primitive_uv_sphere_add(
        radius=0.18,
        location=(location[0], location[1], location[2] + 1.9)
    )
    head = bpy.context.active_object
    head.name = f"{name}_Head"
    mat_head = make_material(f"{name}HeadMat", head_color)
    head.data.materials.append(mat_head)
    
    # 父子关系（头跟随身体）
    head.parent = body
    
    return body


# ============================================================
# 6. 创建两个人物
# ============================================================
# 人物B（蓝衣）：面向镜头方向，画面主体
char_b = create_character(
    name="CharB",
    location=(0, 1.0, 0),  # 前方，正对镜头
    body_color=(0.2, 0.3, 0.6, 1.0),
    head_color=(0.95, 0.85, 0.70, 1.0),
    facing_angle=math.pi  # 面向镜头
)

# 人物A（红衣）：靠近镜头，偏侧边，面向蓝衣
char_a = create_character(
    name="CharA",
    location=(0.8, -1.5, 0),  # 靠近镜头，偏右侧
    body_color=(0.7, 0.2, 0.2, 1.0),
    head_color=(0.95, 0.85, 0.70, 1.0),
    facing_angle=-math.pi / 4  # 侧转面向蓝衣
)


# ============================================================
# 7. 设置镜头
# ============================================================
bpy.ops.object.camera_add()
camera = bpy.context.active_object
camera.name = "ShotCamera"
scene.camera = camera

# 使用更宽的镜头（35mm）确保能拍全人物
camera.data.lens = 35
camera.data.clip_end = 100

# 过肩镜头：从红衣（右侧）肩膀后看蓝衣（前方）
# 起始：远处，两人在画面中
cam_start = (0.8, -4.0, 1.6)
# 终点：红衣右肩上方，聚焦蓝衣面部
cam_end = (0.6, -2.2, 1.6)

camera.location = cam_start
camera.keyframe_insert("location", frame=1)

camera.location = cam_end
camera.keyframe_insert("location", frame=60)  # 60帧时到达终点

# 后12帧定格不动，让镜头"停住"
camera.location = cam_end
camera.keyframe_insert("location", frame=72)

# 设置缓入缓出（贝塞尔曲线而非线性）
for fc in camera.animation_data.action.fcurves:
    for kf in fc.keyframe_points:
        kf.interpolation = 'BEZIER'

# 注视目标：始终看向蓝衣面部
bpy.ops.object.empty_add(type='PLAIN_AXES', location=(0, 1.0, 1.5))
look_at = bpy.context.active_object
look_at.name = "LookTarget"

# 起始：看向蓝衣上半身
look_at.location = (0, 1.0, 1.4)
look_at.keyframe_insert("location", frame=1)

# 结束：聚焦蓝衣的头部（蓝衣头部 z=1.9）
look_at.location = (0, 1.0, 1.9)
look_at.keyframe_insert("location", frame=60)
look_at.keyframe_insert("location", frame=72)

# 注视目标的缓入缓出
for fc in look_at.animation_data.action.fcurves:
    for kf in fc.keyframe_points:
        kf.interpolation = 'BEZIER'

constraint = camera.constraints.new(type='TRACK_TO')
constraint.target = look_at
constraint.track_axis = 'TRACK_NEGATIVE_Z'
constraint.up_axis = 'UP_Y'


# ============================================================
# 8. 渲染
# ============================================================
print(f"开始渲染: {scene.frame_start}-{scene.frame_end} 帧")
bpy.ops.render.render(animation=True)
# 保存 .blend 文件（方便在 Blender 界面里查看）
bpy.ops.wm.save_as_mainfile(filepath="/Users/zengle/Documents/storyboard-3d-pipeline/render/test_01.blend")
print("渲染完成! .blend 已保存")
