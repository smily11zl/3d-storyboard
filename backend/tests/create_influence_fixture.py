"""创建用于测试「export 跳过纯 influence 直接 action」的 fixture .blend。

构造：相机 + TRACK_TO 约束（target = Empty）+ 纯 influence 直接 action（约束切换动画）
+ 一个 NLA strip（位置动画）。

export 时「纯 influence 直接 action」应被解绑跳过，glTF 里不应出现它的烘焙动画。
"""
import bpy
import os

# 清空默认场景
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.object.select_all(action='SELECT')
bpy.ops.object.delete()

# Empty 作为追踪目标
bpy.ops.object.empty_add(location=(0, 0, 0))
target = bpy.context.active_object
target.name = "AimTarget"

# 相机
bpy.ops.object.camera_add(location=(5, -5, 3))
camera = bpy.context.active_object
camera.name = "MainCamera"
bpy.context.scene.camera = camera

# TRACK_TO 约束 + 纯 influence 直接 action（约束切换动画）
constraint = camera.constraints.new(type="TRACK_TO")
constraint.target = target
constraint.influence = 1.0
constraint.keyframe_insert(data_path="influence", frame=1)
constraint.influence = 0.0
constraint.keyframe_insert(data_path="influence", frame=24)
camera.animation_data.action.name = "CameraInfluenceAction"

# 一个 NLA strip（位置动画）
move_action = bpy.data.actions.new(name="CameraMove")
fcurve = move_action.fcurves.new(data_path="location", index=0)
fcurve.keyframe_points.insert(1, 0.0)
fcurve.keyframe_points.insert(24, 10.0)
nla_track = camera.animation_data.nla_tracks.new()
nla_track.name = "seg_01"
strip = nla_track.strips.new(name="seg_01", start=1, action=move_action)
strip.frame_end = 24
strip.extrapolation = "NOTHING"

bpy.context.scene.frame_start = 1
bpy.context.scene.frame_end = 24
bpy.context.scene.render.fps = 24

output_path = os.path.join(os.path.dirname(__file__), "fixture_influence.blend")
bpy.ops.wm.save_as_mainfile(filepath=output_path)
print(f"Fixture saved: {output_path}")
