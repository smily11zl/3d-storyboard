"""
test_09.py — 男性角色招手姿势（静态，无动画）
"""
import bpy, math

CHAR = "/Users/zengle/Documents/storyboard-3d-pipeline/characters/male.blend"
OUT  = "/Users/zengle/Documents/storyboard-3d-pipeline/render/test_09.blend"

# 清空
bpy.ops.object.select_all(action='SELECT')
bpy.ops.object.delete()

# 导入男性
bpy.ops.wm.append(
    filepath=f"{CHAR}/Collection/",
    directory=f"{CHAR}/Collection/",
    filename="Collection"
)

# 招手姿势
arm = bpy.data.objects["Armature"]
bpy.context.view_layer.objects.active = arm
bpy.ops.object.mode_set(mode='POSE')
pb = arm.pose.bones

pb["UpperArm.R"].rotation_euler.z = -1.8
pb["Forearm.R"].rotation_euler.z = -1.2
pb["Palm.R"].rotation_euler.z = 0.3

bpy.ops.object.mode_set(mode='OBJECT')

bpy.ops.wm.save_as_mainfile(filepath=OUT)
print("✅ test_09.blend 已生成")
