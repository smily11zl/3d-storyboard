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
        _rebuild_constraints(camera_obj, camera_segments)
        for segment in camera_segments:
            _rebuild_segment(camera_obj, segment)

    # 3. 按段重建 target 的 location 动画（每段独立位置，坐标转化 Y-up → Z-up）
    _rebuild_target_animations(segments)

    # 4. 时间轴帧范围拉长到最末段的结束帧。新增段会让总时长变长，若不更新
    #    scene.frame_end，保存出的 blend 播放循环范围仍停在旧 frame_end（如 216），
    #    新增段（如 217-288）在 Blender 里自动播放时根本播放不到。
    fps = bpy.context.scene.render.fps
    max_end_frame = 1
    for segment in segments:
        end_frame = round(segment["end_time"] * fps)
        if end_frame > max_end_frame:
            max_end_frame = end_frame
    bpy.context.scene.frame_end = max_end_frame

    bpy.ops.wm.save_as_mainfile(filepath=output_blend)
    return True


def _segment_target_name(segment):
    """提取段 TRACK_TO 约束的 target 名（follow 段才有），无则 None。"""
    constraint_meta = segment.get("constraint") or {}
    for entry in constraint_meta.get("rotation", []):
        if entry.get("type") == "TRACK_TO" and entry.get("target"):
            return entry["target"]
    return None


def _rebuild_target_animations(segments):
    """按段重建 target 的 location 动画（每段独立位置，段边界 CONSTANT 硬切）。

    取代旧的「全局一个 target 位置」：follow 段各自的 target_position 写到
    对应时间段的关键帧，interpolate 段不写（约束失效，位置不影响朝向）。
    """
    import bpy

    fps = bpy.context.scene.render.fps

    target_segments: dict[str, list] = {}
    for segment in segments:
        if segment.get("orientation_mode") != "follow":
            continue
        if segment.get("target_position") is None:
            continue
        target_name = _segment_target_name(segment)
        if target_name is None:
            continue
        target_segments.setdefault(target_name, []).append(segment)

    for target_name, segs in target_segments.items():
        target_obj = bpy.data.objects.get(target_name)
        if target_obj is None:
            continue
        # 清空旧 location 动画（保留其它数据），重建
        if target_obj.animation_data is None:
            target_obj.animation_data_create()
        if target_obj.animation_data.action is None:
            target_obj.animation_data.action = bpy.data.actions.new(f"{target_name}_location")
        for fcurve in list(target_obj.animation_data.action.fcurves):
            if fcurve.data_path == "location":
                target_obj.animation_data.action.fcurves.remove(fcurve)

        segs.sort(key=lambda segment: segment["start_time"])
        for segment in segs:
            start_frame = round(segment["start_time"] * fps) + 1
            end_frame = round(segment["end_time"] * fps)
            position = _gltf_to_blender_position(segment["target_position"])
            target_obj.location = position
            target_obj.keyframe_insert(data_path="location", frame=start_frame)
            target_obj.location = position
            target_obj.keyframe_insert(data_path="location", frame=end_frame)

        # 段边界 CONSTANT 硬切（不同段各自看各自的目标点，不渐变）
        if target_obj.animation_data and target_obj.animation_data.action:
            for fcurve in target_obj.animation_data.action.fcurves:
                if fcurve.data_path == "location":
                    for keyframe in fcurve.keyframe_points:
                        keyframe.interpolation = "CONSTANT"


def _clear_camera(camera_obj):
    """清空相机的 NLA 动画 + 约束 + 残留 action。"""
    import bpy

    actions_to_remove = []
    if camera_obj.animation_data is not None:
        for nla_track in list(camera_obj.animation_data.nla_tracks):
            for strip in nla_track.strips:
                if strip.action is not None:
                    actions_to_remove.append(strip.action)
            camera_obj.animation_data.nla_tracks.remove(nla_track)
        if camera_obj.animation_data.action is not None:
            actions_to_remove.append(camera_obj.animation_data.action)
        camera_obj.animation_data.action = None
    for constraint in list(camera_obj.constraints):
        camera_obj.constraints.remove(constraint)
    # 删除残留的 action（解除引用后 users 应为 0）。若不删，下次重建时
    # bpy.data.actions.new(name) 撞名会自动加 .001，导致段名漂移。
    for action in actions_to_remove:
        if action.users == 0:
            bpy.data.actions.remove(action)


def _rebuild_segment(camera_obj, segment):
    """重建单个段：写 location 关键帧；interpolate 段写 rotation，follow 段写约束。"""
    import bpy

    fps = bpy.context.scene.render.fps
    start_frame = round(segment["start_time"] * fps) + 1
    end_frame = round(segment["end_time"] * fps)
    segment_name = segment["segment_name"]

    action = bpy.data.actions.new(name=segment_name)

    position_keyframes = segment.get("position_keyframes")
    rotation_keyframes = segment.get("rotation_keyframes")

    if position_keyframes is not None and rotation_keyframes is not None:
        # C 段：逐帧复刻 glTF 采样点（每帧位置 + 朝向，Y-up → Z-up）
        _write_keyframe_series(
            action, "location", position_keyframes, fps,
            lambda keyframe: _gltf_to_blender_position(keyframe["position"]),
        )
        _write_keyframe_series(
            action, "rotation_euler", rotation_keyframes, fps,
            lambda keyframe: _gltf_to_blender_rotation(keyframe["rotation"]),
        )
    else:
        # S 段：首尾关键帧 + 朝向
        interpolation = segment.get("interpolation") or {}
        position_interpolation = interpolation.get("position", "LINEAR")
        rotation_interpolation = interpolation.get("rotation", "LINEAR")
        orientation_mode = segment.get("orientation_mode", "interpolate")

        start_position = _gltf_to_blender_position(segment["start_pose"]["position"])
        end_position = _gltf_to_blender_position(segment["end_pose"]["position"])
        _write_keyframes(
            action, "location", start_frame, start_position, end_frame, end_position,
            position_interpolation,
        )

        if orientation_mode != "follow":
            # interpolate：写 rotation 关键帧（Y-up → Z-up）
            start_rotation = _gltf_to_blender_rotation(segment["start_pose"]["rotation"])
            end_rotation = _gltf_to_blender_rotation(segment["end_pose"]["rotation"])
            _write_keyframes(
                action, "rotation_euler", start_frame, start_rotation, end_frame, end_rotation,
                rotation_interpolation,
            )
        # follow 段：朝向由 TRACK_TO 约束驱动（约束在 _rebuild_constraints 相机级重建）

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
    """写首尾两个关键帧到 action，并设置插值类型。

    注意：`keyframe_points.insert()` 返回的关键帧引用在多次插入后可能失效，
    导致只设置到最后一个关键帧的插值（首帧残留默认 BEZIER）。故插入后统一遍历设置。
    """
    for index in range(3):
        fcurve = action.fcurves.find(data_path, index=index)
        if fcurve is None:
            fcurve = action.fcurves.new(data_path=data_path, index=index)
        fcurve.keyframe_points.insert(start_frame, start_values[index])
        fcurve.keyframe_points.insert(end_frame, end_values[index])
        for keyframe in fcurve.keyframe_points:
            keyframe.interpolation = interpolation


def _write_keyframe_series(action, data_path, keyframes, fps, value_of):
    """逐帧复刻：对 keyframes（[{time, position/rotation}]）写所有采样点关键帧。

    value_of(keyframe) 返回转化后的 (x, y, z)。插值统一 LINEAR（逐帧采样本身就是线性轨迹）。
    """
    for keyframe in keyframes:
        frame = round(keyframe["time"] * fps)
        value = value_of(keyframe)
        for index in range(3):
            fcurve = action.fcurves.find(data_path, index=index)
            if fcurve is None:
                fcurve = action.fcurves.new(data_path=data_path, index=index)
            fcurve.keyframe_points.insert(frame, value[index])
    for fcurve in action.fcurves:
        if fcurve.data_path == data_path:
            for keyframe in fcurve.keyframe_points:
                keyframe.interpolation = "LINEAR"


def _find_camera(camera_name):
    import bpy

    for obj in bpy.data.objects:
        if obj.name == camera_name and obj.type == "CAMERA":
            return obj
    return None


def _rebuild_constraints(camera_obj, camera_segments):
    """相机级重建约束：收集 follow 段的唯一 TRACK_TO target，每个建一个（去重，避免堆叠）。

    约束 influence 动画化：追踪该 target 的 follow 段 influence=1（约束生效），
    其余段（interpolate / 追别的 target）influence=0（约束失效，用 rotation 关键帧）。
    这样同一相机可混用「一段追踪、一段线性」。
    C 段（带 position_keyframes）逐帧复刻：朝向已烘焙成 rotation 关键帧，跳过不建约束。
    """
    import bpy

    fps = bpy.context.scene.render.fps

    # 收集 follow 段的唯一 TRACK_TO target（去重）
    track_to_entries: dict[str, dict] = {}
    for segment in camera_segments:
        if segment.get("orientation_mode") != "follow":
            continue
        if segment.get("position_keyframes") is not None:
            continue  # C 段逐帧复刻：朝向由 rotation 关键帧驱动，不再建 TRACK_TO 约束
        constraint_meta = segment.get("constraint") or {}
        for entry in constraint_meta.get("rotation", []):
            if entry.get("type") != "TRACK_TO" or not entry.get("target"):
                continue
            track_to_entries.setdefault(entry["target"], entry)

    if not track_to_entries:
        return

    sorted_segments = sorted(camera_segments, key=lambda segment: segment["start_time"])
    for target_name, entry in track_to_entries.items():
        constraint = _apply_track_to(camera_obj, entry)
        # 给 influence 写关键帧：追踪该 target 的 follow 段=1，其余段=0
        for segment in sorted_segments:
            start_frame = round(segment["start_time"] * fps) + 1
            end_frame = round(segment["end_time"] * fps)
            influence = 1.0 if _segment_tracks_target(segment, target_name) else 0.0
            constraint.influence = influence
            constraint.keyframe_insert(data_path="influence", frame=start_frame)
            constraint.influence = influence
            constraint.keyframe_insert(data_path="influence", frame=end_frame)

        # influence 段边界跳变（不渐变）
        owner = constraint.id_data
        animation_data = owner.animation_data
        if animation_data is not None and animation_data.action is not None:
            fcurve = animation_data.action.fcurves.find(
                f'constraints["{constraint.name}"].influence'
            )
            if fcurve is not None:
                for keyframe in fcurve.keyframe_points:
                    keyframe.interpolation = "CONSTANT"


def _segment_tracks_target(segment, target_name):
    """判断段的朝向是否由 target_name 的 TRACK_TO 约束驱动。"""
    if segment.get("orientation_mode") != "follow":
        return False
    if segment.get("position_keyframes") is not None:
        return False
    constraint_meta = segment.get("constraint") or {}
    return any(
        entry.get("type") == "TRACK_TO" and entry.get("target") == target_name
        for entry in constraint_meta.get("rotation", [])
    )


def _apply_track_to(camera_obj, entry):
    """新建单个 TRACK_TO 约束，返回约束对象。"""
    import bpy

    constraint = camera_obj.constraints.new(type="TRACK_TO")
    target = bpy.data.objects.get(entry["target"])
    if target is not None:
        constraint.target = target
    if entry.get("track_axis"):
        constraint.track_axis = entry["track_axis"]
    if entry.get("up_axis"):
        constraint.up_axis = entry["up_axis"]
    return constraint


def _gltf_to_blender_position(position):
    """glTF Y-up → Blender Z-up 位置：M = Rx(+90°)，(x, y, z) → (x, -z, y)。"""
    x, y, z = position
    return (x, -z, y)


def _euler_intrinsic_to_quat(rx, ry, rz):
    """intrinsic XYZ 欧拉 → 四元数：q = qx(rx)·qy(ry)·qz(rz)。

    用于解读前端 THREE.Euler(rx, ry, rz, 'XYZ')（intrinsic，绕自身轴 X→Y→Z）。
    注意：Blender rotation_euler（rotation_mode='XYZ'）是 extrinsic
    （mathutils.Euler('XYZ')，q = qz·qy·qx），两者不同，勿混淆。
    """
    import mathutils

    return (
        mathutils.Quaternion((1, 0, 0), rx)
        @ mathutils.Quaternion((0, 1, 0), ry)
        @ mathutils.Quaternion((0, 0, 1), rz)
    )


def _quat_to_euler_intrinsic(quat):
    """四元数 → intrinsic XYZ 欧拉（旋转矩阵 R = Rx·Ry·Rz 反解）。"""
    import math

    w, x, y, z = quat.w, quat.x, quat.y, quat.z
    r00 = 1 - 2 * (y * y + z * z)
    r01 = 2 * (x * y - w * z)
    r02 = 2 * (x * z + w * y)
    r10 = 2 * (x * y + w * z)
    r11 = 1 - 2 * (x * x + z * z)
    r12 = 2 * (y * z - w * x)
    r20 = 2 * (x * z - w * y)
    r21 = 2 * (y * z + w * x)
    r22 = 1 - 2 * (x * x + y * y)
    pitch = math.asin(max(-1.0, min(1.0, r02)))
    cos_pitch = math.cos(pitch)
    if abs(cos_pitch) > 1e-6:
        roll = math.atan2(-r12 / cos_pitch, r22 / cos_pitch)
        yaw = math.atan2(-r01 / cos_pitch, r00 / cos_pitch)
    else:
        roll = 0.0
        yaw = math.atan2(r10, r11)
    return (roll, pitch, yaw)


def _gltf_to_blender_rotation(rotation):
    """glTF Y-up → Blender Z-up 朝向（extrinsic XYZ 欧拉）。

    前端 THREE.Euler(rx, ry, rz, 'XYZ') 是 intrinsic（q = qx·qy·qz）；而 Blender
    rotation_euler（rotation_mode='XYZ'）是 extrinsic（mathutils.Euler('XYZ')，
    q = qz·qy·qx）。坐标变换 = 左乘 Rx(+90°)，输出 extrinsic 欧拉（与 Blender 求值一致）。

    注意：这里刻意用「左乘」而非「共轭」，因为 glTF 导出器把 Z-up → Y-up 也做
    「左乘 Rx(-90°)」的等价逆变换，两者互为逆，往返自洽。
    """
    import math
    import mathutils

    quat_gltf = _euler_intrinsic_to_quat(rotation[0], rotation[1], rotation[2])
    coordinate_rotation = mathutils.Quaternion((1, 0, 0), math.pi / 2)  # Rx(+90°)
    quat_blender = coordinate_rotation @ quat_gltf
    return quat_blender.to_euler('XYZ')


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
