"""V5 回存脚本 — 读原 blend，整体重建相机动画，另存新 blend。

用法:
    blender --background --python apply_edit.py -- <input.blend> <payload.json> <output.blend>

payload.json 是 {segments, target_positions}（edit_operations.parse_full_edit 解析后的格式）。
整体重建：清空相机旧动画 + 约束，按 segments 重写关键帧/插值/约束，坐标 Y-up → Z-up。
"""
import json
import math
import sys


def apply_full_segments(input_blend, segments, target_positions, output_blend):
    """读原 blend，整体重建相机动画，另存新 blend。返回 True 成功。"""
    import bpy

    bpy.ops.wm.open_mainfile(filepath=input_blend)

    # 1. 清空所有相机的动画 + 约束（整体重建，避免旧数据残留）
    for obj in bpy.data.objects:
        if obj.type == "CAMERA":
            _clear_camera(obj)

    # 2. 按相机分组重建段（按 start_time 排序）
    cameras: dict[str, list] = {}
    for segment in segments:
        cameras.setdefault(segment["camera_name"], []).append(segment)

    for camera_name, camera_segments in cameras.items():
        camera_obj = _find_camera(camera_name)
        if camera_obj is None:
            continue
        camera_segments.sort(key=lambda segment: segment["start_time"])
        for segment in camera_segments:
            _rebuild_segment(camera_obj, segment)

    # 3. 统一设置 target 位置（坐标转化 Y-up → Z-up）
    for target_name, position in target_positions.items():
        target_obj = bpy.data.objects.get(target_name)
        if target_obj is not None:
            target_obj.location = _gltf_to_blender_position(position)

    bpy.ops.wm.save_as_mainfile(filepath=output_blend)
    return True


def _clear_camera(camera_obj):
    """清空相机的 NLA 动画 + 约束。"""
    import bpy

    if camera_obj.animation_data is not None:
        for nla_track in list(camera_obj.animation_data.nla_tracks):
            camera_obj.animation_data.nla_tracks.remove(nla_track)
        camera_obj.animation_data.action = None
    for constraint in list(camera_obj.constraints):
        camera_obj.constraints.remove(constraint)


def _rebuild_segment(camera_obj, segment):
    """重建单个段：写 location 关键帧；interpolate 段写 rotation，follow 段写约束。"""
    import bpy

    fps = bpy.context.scene.render.fps
    start_frame = round(segment["start_time"] * fps) + 1
    end_frame = round(segment["end_time"] * fps)
    segment_name = segment["segment_name"]

    interpolation = segment.get("interpolation") or {}
    position_interpolation = interpolation.get("position", "LINEAR")
    rotation_interpolation = interpolation.get("rotation", "LINEAR")
    orientation_mode = segment.get("orientation_mode", "interpolate")

    action = bpy.data.actions.new(name=segment_name)

    # 位置关键帧（Y-up → Z-up）
    start_position = _gltf_to_blender_position(segment["start_pose"]["position"])
    end_position = _gltf_to_blender_position(segment["end_pose"]["position"])
    _write_keyframes(
        action, "location", start_frame, start_position, end_frame, end_position,
        position_interpolation,
    )

    # 朝向
    if orientation_mode == "follow":
        # follow：朝向由约束驱动，写约束（target 位置在第 3 步统一设置）
        constraint_meta = segment.get("constraint")
        if constraint_meta:
            _apply_constraint(camera_obj, constraint_meta)
    else:
        # interpolate：写 rotation 关键帧（Y-up → Z-up）
        start_rotation = _gltf_to_blender_rotation(segment["start_pose"]["rotation"])
        end_rotation = _gltf_to_blender_rotation(segment["end_pose"]["rotation"])
        _write_keyframes(
            action, "rotation_euler", start_frame, start_rotation, end_frame, end_rotation,
            rotation_interpolation,
        )

    # NLA strip
    animation_data = camera_obj.animation_data
    if animation_data is None:
        animation_data = camera_obj.animation_data_create()
    nla_track = animation_data.nla_tracks.new()
    nla_track.name = segment_name
    strip = nla_track.strips.new(name=segment_name, start=start_frame, action=action)
    strip.frame_end = end_frame
    strip.extrapolation = "NOTHING"


def _write_keyframes(action, data_path, start_frame, start_values, end_frame, end_values, interpolation):
    """写首尾两个关键帧到 action，并设置插值类型。"""
    for index in range(3):
        fcurve = action.fcurves.find(data_path, index=index)
        if fcurve is None:
            fcurve = action.fcurves.new(data_path=data_path, index=index)
        start_keyframe = fcurve.keyframe_points.insert(start_frame, start_values[index])
        end_keyframe = fcurve.keyframe_points.insert(end_frame, end_values[index])
        start_keyframe.interpolation = interpolation
        end_keyframe.interpolation = interpolation


def _find_camera(camera_name):
    import bpy

    for obj in bpy.data.objects:
        if obj.name == camera_name and obj.type == "CAMERA":
            return obj
    return None


def _apply_constraint(camera_obj, constraint_meta):
    """新建约束（rotation 的 TRACK_TO 等）。"""
    import bpy

    for entry in constraint_meta.get("rotation", []):
        if entry.get("type") == "TRACK_TO" and entry.get("target"):
            constraint = camera_obj.constraints.new(type="TRACK_TO")
            target = bpy.data.objects.get(entry["target"])
            if target is not None:
                constraint.target = target
            if entry.get("track_axis"):
                constraint.track_axis = entry["track_axis"]
            if entry.get("up_axis"):
                constraint.up_axis = entry["up_axis"]


def _gltf_to_blender_position(position):
    """glTF Y-up → Blender Z-up 位置：M = Rx(+90°)，(x, y, z) → (x, -z, y)。"""
    x, y, z = position
    return (x, -z, y)


def _gltf_to_blender_rotation(rotation):
    """glTF Y-up → Blender Z-up 朝向（XYZ 欧拉角）：q_blender = Rx(+90°) · q_gltf。"""
    import mathutils

    euler_gltf = mathutils.Euler((rotation[0], rotation[1], rotation[2]), "XYZ")
    quat_gltf = euler_gltf.to_quaternion()
    coordinate_rotation = mathutils.Euler((math.pi / 2, 0, 0), "XYZ").to_quaternion()
    quat_blender = coordinate_rotation @ quat_gltf
    euler_blender = quat_blender.to_euler("XYZ")
    return (euler_blender.x, euler_blender.y, euler_blender.z)


def main():
    """CLI 入口：blender --background --python apply_edit.py -- <input> <payload.json> <output>"""
    argv = sys.argv
    try:
        separator_index = argv.index("--")
        script_args = argv[separator_index + 1:]
    except ValueError:
        script_args = argv[argv.index(__file__) + 1:] if __file__ in argv else []

    if len(script_args) < 3:
        print(
            "Usage: blender --background --python apply_edit.py -- "
            "<input.blend> <payload.json> <output.blend>",
            file=sys.stderr,
        )
        sys.exit(1)

    input_blend = script_args[0]
    payload_file = script_args[1]
    output_blend = script_args[2]

    with open(payload_file) as file_handle:
        payload = json.load(file_handle)

    success = apply_full_segments(
        input_blend, payload["segments"], payload["target_positions"], output_blend
    )
    if not success:
        sys.exit(1)
    sys.exit(0)


if __name__ == "__main__":
    main()
