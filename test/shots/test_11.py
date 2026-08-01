"""
test_11.py — 男人、女人、小孩站一排
"""
import bpy

OUT = "/Users/zengle/Documents/storyboard-3d-pipeline/render/test_11.blend"
RENDER = "/Users/zengle/Documents/storyboard-3d-pipeline/render/test_11.png"
CHARS = "/Users/zengle/Documents/storyboard-3d-pipeline/characters"

bpy.ops.object.select_all(action='SELECT')
bpy.ops.object.delete()

# ============================================================
OBJECTS = "/Users/zengle/Documents/storyboard-3d-pipeline/characters"

# 男人
pre = set(bpy.data.objects.keys())
bpy.ops.import_scene.fbx(filepath=f"{OBJECTS}/male_mixamo_stand.fbx")
man = (set(bpy.data.objects.keys()) - pre).pop()
bpy.data.objects[man].location = (-1.2, 0, 0)
bpy.data.objects[man].name = "Man"

# 女人
pre = set(bpy.data.objects.keys())
bpy.ops.import_scene.fbx(filepath=f"{OBJECTS}/female_mixamo_stand.fbx")
woman = (set(bpy.data.objects.keys()) - pre).pop()
bpy.data.objects[woman].location = (1.2, 0, 0)
bpy.data.objects[woman].name = "Woman"

# 小孩
pre = set(bpy.data.objects.keys())
bpy.ops.import_scene.fbx(filepath=f"{OBJECTS}/child_mixamo_stand.fbx")
child = (set(bpy.data.objects.keys()) - pre).pop()
bpy.data.objects[child].location = (0, 0, 0)
bpy.data.objects[child].name = "Child"

# ============================================================
# 地面
# ============================================================
bpy.ops.mesh.primitive_plane_add(size=10, location=(0, 0, 0))
floor = bpy.context.active_object
floor.name = "Floor"
mat = bpy.data.materials.new("Floor")
mat.diffuse_color = (0.35, 0.30, 0.25, 1.0)
floor.data.materials.append(mat)

# ============================================================
# 灯光
# ============================================================
bpy.ops.object.light_add(type='SUN', location=(5, -5, 10))
bpy.context.active_object.data.energy = 3
bpy.ops.object.light_add(type='AREA', location=(0, 0, 4))
bpy.context.active_object.data.energy = 200
bpy.context.active_object.data.size = 6

# ============================================================
# 摄像机
# ============================================================
bpy.context.scene.render.engine = 'BLENDER_EEVEE_NEXT'
bpy.context.scene.render.resolution_x = 1920
bpy.context.scene.render.resolution_y = 1080

bpy.ops.object.camera_add(location=(0, -3.5, 0.8))
cam = bpy.context.active_object
cam.data.lens = 28
bpy.context.scene.camera = cam

bpy.ops.object.empty_add(type='PLAIN_AXES', location=(0, 0, 0.6))
look = bpy.context.active_object
c = cam.constraints.new(type='TRACK_TO')
c.target = look; c.track_axis = 'TRACK_NEGATIVE_Z'; c.up_axis = 'UP_Y'

# ============================================================
# 渲染
# ============================================================
bpy.context.scene.render.filepath = RENDER
bpy.context.scene.render.image_settings.file_format = 'PNG'
bpy.ops.render.render(write_still=True)
bpy.ops.wm.save_as_mainfile(filepath=OUT)
print("✅ test_11 已生成")
