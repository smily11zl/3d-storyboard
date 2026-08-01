"""
test_10.py — 男性指向前方
"""
import bpy

CHAR = "/Users/zengle/Documents/storyboard-3d-pipeline/characters/male.blend"
OUT  = "/Users/zengle/Documents/storyboard-3d-pipeline/render/test_10.blend"

bpy.ops.object.select_all(action='SELECT')
bpy.ops.object.delete()

bpy.ops.wm.append(
    filepath=f"{CHAR}/Collection/",
    directory=f"{CHAR}/Collection/",
    filename="Collection"
)

arm = [o for o in bpy.data.objects if o.type == 'ARMATURE'][0]
bpy.context.view_layer.objects.active = arm
bpy.ops.object.mode_set(mode='POSE')
pb = arm.pose.bones

# 右手指向前方(+Y)
pb['HandIK.R'].location = (0.3, 0.8, 1.6)

# 食指伸直
pb['Index1.R'].rotation_euler.z = 0
pb['Index2.R'].rotation_euler.z = 0
pb['Index3.R'].rotation_euler.z = 0

# 其他手指弯曲
for f in ['Middle','Ring','Pinky']:
    pb[f'{f}1.R'].rotation_euler.z = 0.8
    pb[f'{f}2.R'].rotation_euler.z = 0.6
    pb[f'{f}3.R'].rotation_euler.z = 0.4

# 拇指内收
pb['Thumb1.R'].rotation_euler.z = 0.5
pb['Thumb2.R'].rotation_euler.z = 0.4

bpy.ops.object.mode_set(mode='OBJECT')
bpy.ops.wm.save_as_mainfile(filepath=OUT)
print("✅ test_10.blend 已生成（男性指向前方）")
