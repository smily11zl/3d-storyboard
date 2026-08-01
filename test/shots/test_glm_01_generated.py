import bpy

# 清空场景
bpy.ops.object.select_all(action='SELECT')
bpy.ops.object.delete()

# 设置渲染引擎
bpy.context.scene.render.engine = 'BLENDER_EEVEE_NEXT'

# 设置渲染分辨率和帧率
bpy.context.scene.render.resolution_x = 1920
bpy.context.scene.render.resolution_y = 1080
bpy.context.scene.render.fps = 24
bpy.context.scene.frame_end = 72

# 创建地面
ground = bpy.data.meshes.new("Ground")
ground_obj = bpy.data.objects.new("Ground", ground)
bpy.context.collection.objects.link(ground_obj)
bpy.ops.object.select_all(action='DESELECT')
ground_obj.select_set(True)
bpy.context.view_layer.objects.active = ground_obj
bpy.ops.object.mode_set(mode='EDIT')
bpy.ops.mesh.primitive_plane_add(size=10, location=(0, 0, 0))
bpy.ops.object.mode_set(mode='OBJECT')

# 创建地面材质
ground_mat = bpy.data.materials.new(name="GroundMaterial")
ground_mat.use_nodes = True
ground_mat.diffuse_color = (0.7, 0.7, 0.7, 1)
bsdf = ground_mat.node_tree.nodes.get('Principled BSDF')
if bsdf:
    bsdf.inputs['Base Color'].default_value = (0.7, 0.7, 0.7, 1)
ground_obj.data.materials.append(ground_mat)

# 创建蓝衣人物 (CharB)
body_b = bpy.data.meshes.new("CharBBody")
body_b_obj = bpy.data.objects.new("CharBBody", body_b)
bpy.context.collection.objects.link(body_b_obj)
bpy.ops.object.select_all(action='DESELECT')
body_b_obj.select_set(True)
bpy.context.view_layer.objects.active = body_b_obj
bpy.ops.object.mode_set(mode='EDIT')
bpy.ops.mesh.primitive_cube_add(location=(0, 1.0, 0.8), scale=(0.5, 0.3, 1.0))
bpy.ops.object.mode_set(mode='OBJECT')

head_b = bpy.data.meshes.new("CharBHead")
head_b_obj = bpy.data.objects.new("CharBHead", head_b)
bpy.context.collection.objects.link(head_b_obj)
bpy.ops.object.select_all(action='DESELECT')
head_b_obj.select_set(True)
bpy.context.view_layer.objects.active = head_b_obj
bpy.ops.object.mode_set(mode='EDIT')
bpy.ops.mesh.primitive_uv_sphere_add(location=(0, 1.0, 1.9), radius=0.3)
bpy.ops.object.mode_set(mode='OBJECT')

# 创建蓝衣人物材质
char_b_mat = bpy.data.materials.new(name="CharBMaterial")
char_b_mat.use_nodes = True
char_b_mat.diffuse_color = (0.2, 0.4, 0.8, 1)
bsdf = char_b_mat.node_tree.nodes.get('Principled BSDF')
if bsdf:
    bsdf.inputs['Base Color'].default_value = (0.2, 0.4, 0.8, 1)
body_b_obj.data.materials.append(char_b_mat)
head_b_obj.data.materials.append(char_b_mat)

# 创建红衣人物 (CharA)
body_a = bpy.data.meshes.new("CharABody")
body_a_obj = bpy.data.objects.new("CharABody", body_a)
bpy.context.collection.objects.link(body_a_obj)
bpy.ops.object.select_all(action='DESELECT')
body_a_obj.select_set(True)
bpy.context.view_layer.objects.active = body_a_obj
bpy.ops.object.mode_set(mode='EDIT')
bpy.ops.mesh.primitive_cube_add(location=(0.8, -1.5, 0.8), scale=(0.5, 0.3, 1.0))
bpy.ops.object.mode_set(mode='OBJECT')

head_a = bpy.data.meshes.new("CharAHead")
head_a_obj = bpy.data.objects.new("CharAHead", head_a)
bpy.context.collection.objects.link(head_a_obj)
bpy.ops.object.select_all(action='DESELECT')
head_a_obj.select_set(True)
bpy.context.view_layer.objects.active = head_a_obj
bpy.ops.object.mode_set(mode='EDIT')
bpy.ops.mesh.primitive_uv_sphere_add(location=(0.8, -1.5, 1.9), radius=0.3)
bpy.ops.object.mode_set(mode='OBJECT')

# 创建红衣人物材质
char_a_mat = bpy.data.materials.new(name="CharAMaterial")
char_a_mat.use_nodes = True
char_a_mat.diffuse_color = (0.8, 0.2, 0.2, 1)
bsdf = char_a_mat.node_tree.nodes.get('Principled BSDF')
if bsdf:
    bsdf.inputs['Base Color'].default_value = (0.8, 0.2, 0.2, 1)
body_a_obj.data.materials.append(char_a_mat)
head_a_obj.data.materials.append(char_a_mat)

# 旋转蓝衣人物面向镜头
body_b_obj.rotation_euler = (0, 3.14159, 0)
head_b_obj.rotation_euler = (0, 3.14159, 0)

# 旋转红衣人物侧向蓝衣
body_a_obj.rotation_euler = (0, 0.5, 0)
head_a_obj.rotation_euler = (0, 0.5, 0)

# 创建相机
camera = bpy.data.cameras.new("Camera")
camera_obj = bpy.data.objects.new("Camera", camera)
bpy.context.collection.objects.link(camera_obj)
camera_obj.location = (0.8, -4.0, 1.6)
camera_obj.rotation_euler = (0, 0, 0)
camera.lens = 35
bpy.context.scene.camera = camera_obj

# 创建相机动画
bpy.context.scene.frame_set(1)
camera_obj.location = (0.8, -4.0, 1.6)
camera_obj.keyframe_insert(data_path="location", frame=1)

bpy.context.scene.frame_set(60)
camera_obj.location = (0.6, -2.2, 1.6)
camera_obj.keyframe_insert(data_path="location", frame=60)

bpy.context.scene.frame_set(72)
camera_obj.location = (0.6, -2.2, 1.6)
camera_obj.keyframe_insert(data_path="location", frame=72)

# 设置相机动画缓入缓出
for fcurve in camera_obj.animation_data.action.fcurves:
    for keyframe in fcurve.keyframe_points:
        keyframe.interpolation = 'BEZIER'
        keyframe.handle_left_type = 'AUTO_CLAMPED'
        keyframe.handle_right_type = 'AUTO_CLAMPED'

# 设置相机注视目标
constraint = camera_obj.constraints.new('TRACK_TO')
constraint.target = head_b_obj
constraint.track_axis = 'TRACK_NEGATIVE_Z'
constraint.up_axis = 'UP_Y'

# 创建灯光
# 主光源
sun = bpy.data.lights.new(name="Sun", type='SUN')
sun_obj = bpy.data.objects.new("Sun", sun)
bpy.context.collection.objects.link(sun_obj)
sun_obj.location = (5, 5, 10)
sun.energy = 5
sun.shadow_soft_size = 0.5

# 补光
fill = bpy.data.lights.new(name="Fill", type='AREA')
fill_obj = bpy.data.objects.new("Fill", fill)
bpy.context.collection.objects.link(fill_obj)
fill_obj.location = (-3, -2, 3)
fill.energy = 2
fill.size = 2

# 设置环境光
world = bpy.context.scene.world
world.use_nodes = True
bg_node = world.node_tree.nodes.get('Background')
if bg_node:
    bg_node.inputs['Strength'].default_value = 0.1
    bg_node.inputs['Color'].default_value = (0.8, 0.8, 0.9, 1)

# 设置输出路径
output_path = "/Users/zengle/Documents/storyboard-3d-pipeline/render/test_glm_01.mp4"
blend_path = "/Users/zengle/Documents/storyboard-3d-pipeline/render/test_glm_01.blend"

bpy.context.scene.render.filepath = output_path
bpy.context.scene.render.image_settings.file_format = 'FFMPEG'
bpy.context.scene.render.ffmpeg.format = 'MPEG4'
bpy.context.scene.render.ffmpeg.constant_rate_factor = 'MEDIUM'

# 渲染动画
bpy.ops.render.render(animation=True)

# 保存.blend文件
bpy.ops.wm.save_as_mainfile(filepath=blend_path)