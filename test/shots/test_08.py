"""
test_08.py — 静态姿势：女性招手 + 男性跑步（单帧，无动画）
"""
import bpy, math

BLEND = "/Users/zengle/Documents/storyboard-3d-pipeline/render/test_07.blend"
OUT  = "/Users/zengle/Documents/storyboard-3d-pipeline/render/test_08.blend"

bpy.ops.wm.open_mainfile(filepath=BLEND)

male_arm   = bpy.data.objects["Armature"]
female_arm = bpy.data.objects["Armature.001"]

# ============================================================
# 女性招手姿势
# ============================================================
bpy.context.view_layer.objects.active = female_arm
bpy.ops.object.mode_set(mode='POSE')
pb = female_arm.pose.bones

pb["UpperArm.R"].rotation_euler.z = -1.8
pb["Forearm.R"].rotation_euler.z = -1.2
pb["Palm.R"].rotation_euler.z = 0.3

bpy.ops.object.mode_set(mode='OBJECT')

# ============================================================
# 男性跑步姿势（单帧定格：左腿前右腿后）
# ============================================================
bpy.context.view_layer.objects.active = male_arm
bpy.ops.object.mode_set(mode='POSE')
pb = male_arm.pose.bones

# 左腿前迈
pb["Hip.L"].rotation_euler.x = 0.6
pb["Shin.L"].rotation_euler.x = -0.8

# 右腿后蹬
pb["Hip.R"].rotation_euler.x = -0.5
pb["Shin.R"].rotation_euler.x = 0.5

# 手臂（与腿反向摆动）
pb["UpperArm.R"].rotation_euler.x = 0.6
pb["Forearm.R"].rotation_euler.x = -0.3
pb["UpperArm.L"].rotation_euler.x = -0.5
pb["Forearm.L"].rotation_euler.x = 0.4

bpy.ops.object.mode_set(mode='OBJECT')

bpy.ops.wm.save_as_mainfile(filepath=OUT)
print("✅ test_08.blend 已生成（女性招手 男性跑步 静态姿势）")
