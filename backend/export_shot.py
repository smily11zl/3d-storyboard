"""Blender glTF export script — called via: blender --background --python export_shot.py -- <input.blend> <output_directory>

Exports a .blend file to .gltf (JSON + .bin + textures) with all cameras and animations.
Exits non-zero on failure with error message to stderr.
"""
import sys
import os
import json


def export_blend_to_gltf(input_filepath, output_directory):
    """Export the given .blend to .gltf format in the output directory.

    Parameters
    ----------
    input_filepath : str
        Path to the .blend file to export.
    output_directory : str
        Directory where scene.gltf and scene.bin will be written.

    Returns
    -------
    bool
        True on success, False on failure.
    """
    import bpy

    # Validate input
    if not os.path.isfile(input_filepath):
        print(f"ERROR: Input file not found: {input_filepath}", file=sys.stderr)
        return False

    # Load the .blend file
    try:
        bpy.ops.wm.open_mainfile(filepath=input_filepath)
    except Exception as error:
        print(f"ERROR: Failed to open .blend: {error}", file=sys.stderr)
        return False

    # Ensure output directory exists
    os.makedirs(output_directory, exist_ok=True)

    # Rename bones with armature prefix to avoid duplicate names in glTF.
    # Two Mixamo characters (Man/Woman) share bone names like "mixamorig:Hips".
    # In glTF, animation clips bind to bones BY NAME — duplicate names cause
    # both clips to drive the same skeleton, leaving the other character in
    # T-pose (bind pose). Prefixing makes every bone name unique.
    for armature_object in bpy.data.objects:
        if armature_object.type != 'ARMATURE':
            continue
        prefix = f"{armature_object.name}_"
        for bone in armature_object.data.bones:
            if not bone.name.startswith(prefix):
                bone.name = prefix + bone.name
        # Sync vertex groups on skinned meshes (they match bones by name)
        for child_object in armature_object.children:
            if child_object.type == 'MESH':
                for vertex_group in child_object.vertex_groups:
                    if not vertex_group.name.startswith(prefix):
                        vertex_group.name = prefix + vertex_group.name

    # Bake camera constraint rotation into explicit keyframes before export.
    # The glTF exporter omits the rotation channel for segments whose orientation
    # is constant (e.g. a straight dolly-in where the camera keeps looking at the
    # same target), falling back to the node's initial rotation — which for a
    # constraint-driven camera is the exporter's fixed camera transform (pointing
    # straight up). Sampling the constraint result at each segment's keyframes and
    # writing explicit rotation keyframes forces every segment to carry a correct
    # rotation animation. This is exporter-side, so any user-authored .blend with
    # constraint-driven cameras exports correctly — no authoring rules required.
    for camera_object in bpy.data.objects:
        if camera_object.type != 'CAMERA' or not camera_object.constraints:
            continue
        animation_data = camera_object.animation_data
        if animation_data is None:
            continue
        scene = bpy.context.scene
        depsgraph = bpy.context.evaluated_depsgraph_get()
        for track in animation_data.nla_tracks:
            for strip in track.strips:
                action = strip.action
                if action is None:
                    continue
                keyframe_frames = set()
                for fcurve in action.fcurves:
                    if fcurve.data_path == "location":
                        for keyframe_point in fcurve.keyframe_points:
                            keyframe_frames.add(int(round(keyframe_point.co[0])))
                if not keyframe_frames:
                    continue
                for frame in sorted(keyframe_frames):
                    scene.frame_set(frame)
                    depsgraph.update()
                    evaluated_camera = camera_object.evaluated_get(depsgraph)
                    rotation_euler = evaluated_camera.matrix_world.to_euler()
                    for axis_index in range(3):
                        rotation_fcurve = action.fcurves.find(
                            "rotation_euler", index=axis_index
                        )
                        if rotation_fcurve is None:
                            rotation_fcurve = action.fcurves.new(
                                data_path="rotation_euler", index=axis_index
                            )
                        rotation_fcurve.keyframe_points.insert(
                            frame, rotation_euler[axis_index]
                        )
                        rotation_fcurve.keyframe_points[-1].interpolation = "LINEAR"

    gltf_filepath = os.path.join(output_directory, "scene.gltf")

    # 解绑相机「直接 action」里的纯 influence 动画，避免 glTF 导出器把它烘焙成
    # 一条覆盖全时间轴的全局 rotation 动画（cam_01动作.001 之类），叠加污染
    # 各段已烘焙好的朝向。influence 的效果在上面的烘焙逻辑里已经写进 NLA strip
    # 的 rotation 关键帧，导出阶段不再需要它；导出后恢复原状。
    # 注意：只解绑「纯 influence」的直接 action（约束切换动画）；正常的相机
    # 动画（location/rotation）直接 action 保留，否则会丢失动画。
    saved_direct_actions = {}
    for camera_object in bpy.data.objects:
        if camera_object.type != "CAMERA":
            continue
        animation_data = camera_object.animation_data
        if animation_data is None or animation_data.action is None:
            continue
        action = animation_data.action
        is_pure_influence = bool(action.fcurves) and all(
            "influence" in fcurve.data_path for fcurve in action.fcurves
        )
        if is_pure_influence:
            saved_direct_actions[camera_object.name] = action
            animation_data.action = None

    # Export to glTF (separate JSON + .bin format)
    try:
        bpy.ops.export_scene.gltf(
            filepath=gltf_filepath,
            export_format='GLTF_SEPARATE',

            export_cameras=True,
            export_animations=True,
            export_lights=True,

            export_apply=False,

            export_force_sampling=True,
            export_nla_strips=True,
            export_def_bones=True,
        )
    except Exception as error:
        print(f"ERROR: glTF export failed: {error}", file=sys.stderr)
        for camera_name, action in saved_direct_actions.items():
            bpy.data.objects[camera_name].animation_data.action = action
        return False
    finally:
        for camera_name, action in saved_direct_actions.items():
            bpy.data.objects[camera_name].animation_data.action = action

    # Verify output files were created
    if not os.path.isfile(gltf_filepath):
        print(f"ERROR: scene.gltf was not created at {gltf_filepath}", file=sys.stderr)
        return False

    # Print summary for caller
    scene_info = get_scene_summary(gltf_filepath)

    # Camera frame aspect = render resolution ratio (Blender's actual frame
    # shape). glTF doesn't carry it, so persist it as a sidecar for the backend.
    resolution_x = bpy.context.scene.render.resolution_x
    resolution_y = bpy.context.scene.render.resolution_y
    frame_aspect = round(resolution_x / resolution_y, 4) if resolution_y else 1.0
    scene_info["frame_aspect"] = frame_aspect
    aspect_filepath = os.path.join(output_directory, "frame_aspect.txt")
    with open(aspect_filepath, "w", encoding="utf-8") as aspect_file:
        aspect_file.write(str(frame_aspect))

    # Shot segments = camera NLA strips (one strip per segment). glTF loses the
    # strip's absolute timeline offset, so persist segments as a sidecar too.
    segments = extract_segments_from_nla()
    segments_filepath = os.path.join(output_directory, "segments.json")
    with open(segments_filepath, "w", encoding="utf-8") as segments_file:
        json.dump({"segments": segments}, segments_file, indent=2, ensure_ascii=False)

    print(json.dumps(scene_info, indent=2, ensure_ascii=False))

    return True


def _action_keyframe_times(action):
    """收集 action 里所有 F-Curve 的关键帧时刻（去重、排序）。"""
    times = set()
    for fcurve in action.fcurves:
        for keyframe in fcurve.keyframe_points:
            times.add(round(keyframe.co.x, 2))
    return sorted(times)


def _euler_intrinsic_to_quat(rx, ry, rz):
    """intrinsic XYZ 欧拉 → 四元数：q = qx(rx)·qy(ry)·qz(rz)。

    用于解读前端 THREE.Euler（intrinsic）。注意：Blender rotation_euler
    （rotation_mode='XYZ'）是 extrinsic（mathutils.Euler('XYZ')，q = qz·qy·qx），
    两者不同，勿混淆。
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


def _blender_to_gltf_pose(position, rotation):
    """Blender Z-up → glTF Y-up 逆映射（保存端 _gltf_to_*_blender 的逆）。

    position：左乘 Rx(-90°)，(x, y, z) → (x, z, -y)。
    rotation：Blender rotation_euler（extrinsic XYZ，mathutils.Euler('XYZ') 约定）。
    q_gltf = Rx(-90°) · q_blender，输出 intrinsic 欧拉（前端 THREE 约定）。
    """
    import math
    import mathutils

    x, y, z = position
    gltf_position = (x, z, -y)

    quat_blender = mathutils.Euler((rotation[0], rotation[1], rotation[2]), 'XYZ').to_quaternion()
    coordinate_rotation = mathutils.Quaternion((1, 0, 0), -math.pi / 2)  # Rx(-90°)
    quat_gltf = coordinate_rotation @ quat_blender
    euler_gltf = _quat_to_euler_intrinsic(quat_gltf)
    return gltf_position, euler_gltf


def _action_pose_at(action, time):
    """读 action 在某个时刻的 position + rotation（用 F-Curve evaluate 求值），
    并把 Blender Z-up 坐标逆映射回 glTF Y-up（与前端编辑态一致）。"""
    position = [0.0, 0.0, 0.0]
    rotation = [0.0, 0.0, 0.0]
    for fcurve in action.fcurves:
        if fcurve.data_path == "location" and 0 <= fcurve.array_index < 3:
            position[fcurve.array_index] = round(fcurve.evaluate(time), 4)
        elif fcurve.data_path == "rotation_euler" and 0 <= fcurve.array_index < 3:
            rotation[fcurve.array_index] = round(fcurve.evaluate(time), 4)
    gltf_position, euler_gltf = _blender_to_gltf_pose(position, rotation)
    return {"position": list(gltf_position), "rotation": list(euler_gltf)}


# glTF 原生支持的插值（Blender 名）：LINEAR / CONSTANT(=STEP) / BEZIER(=CUBICSPLINE)
SIMPLE_INTERPOLATIONS = {"LINEAR", "CONSTANT"}

# 约束按作用通道分类：位置约束 vs 朝向约束
POSITION_CONSTRAINT_TYPES = {"FOLLOW_PATH", "COPY_LOCATION", "LIMIT_LOCATION"}
ROTATION_CONSTRAINT_TYPES = {
    "TRACK_TO", "LOCKED_TRACK", "DAMPED_TRACK", "COPY_ROTATION", "LIMIT_ROTATION",
}

# 难前端重演的约束（路径/限制类）：归入复杂。
# 不在其中的（TRACK_TO / LOCKED_TRACK / DAMPED_TRACK / COPY_*）可前端重演，归入简单。
COMPLEX_CONSTRAINT_TYPES = {"FOLLOW_PATH", "LIMIT_LOCATION", "LIMIT_ROTATION"}


def _channel_keyframe_times(action, data_path):
    """收集某个通道（location / rotation_euler）自己的关键帧时刻。"""
    times = set()
    for fcurve in action.fcurves:
        if fcurve.data_path != data_path:
            continue
        for keyframe in fcurve.keyframe_points:
            times.add(round(keyframe.co.x, 2))
    return sorted(times)


def _channel_values(action, data_path):
    """读某个通道在「该通道自己的关键帧时刻」的值列表。"""
    values = []
    for time in _channel_keyframe_times(action, data_path):
        value = [0.0, 0.0, 0.0]
        for fcurve in action.fcurves:
            if fcurve.data_path == data_path and 0 <= fcurve.array_index < 3:
                value[fcurve.array_index] = round(fcurve.evaluate(time), 4)
        values.append(tuple(value))
    return values


def _channel_is_simple(action, data_path):
    """判定某个通道是否「简单」：插值 ∈ {LINEAR/CONSTANT} 且去重值 ≤2。"""
    for fcurve in action.fcurves:
        if fcurve.data_path != data_path:
            continue
        for keyframe in fcurve.keyframe_points:
            if keyframe.interpolation not in SIMPLE_INTERPOLATIONS:
                return False
    return len(set(_channel_values(action, data_path))) <= 2


def _channel_interpolation(action, data_path):
    """读某通道的插值方式（简单段：LINEAR/CONSTANT，LINEAR 优先）。"""
    interpolations = set()
    for fcurve in action.fcurves:
        if fcurve.data_path != data_path:
            continue
        for keyframe in fcurve.keyframe_points:
            interpolations.add(keyframe.interpolation)
    if "LINEAR" in interpolations:
        return "LINEAR"
    if "CONSTANT" in interpolations:
        return "CONSTANT"
    return sorted(interpolations)[0] if interpolations else "LINEAR"


def _constraint_summary(camera_object):
    """读相机的约束，按作用通道分类，返回 (位置约束列表, 朝向约束列表)。"""
    position_constraints = []
    rotation_constraints = []
    for constraint in camera_object.constraints:
        target = constraint.target.name if constraint.target else None
        entry = {"type": constraint.type, "target": target}
        if constraint.type == "TRACK_TO":
            entry["track_axis"] = constraint.track_axis
            entry["up_axis"] = constraint.up_axis
        if constraint.type in POSITION_CONSTRAINT_TYPES:
            position_constraints.append(entry)
        elif constraint.type in ROTATION_CONSTRAINT_TYPES:
            rotation_constraints.append(entry)
    return position_constraints, rotation_constraints


def _classify_segment(camera_object, action):
    """分通道判定一个段，返回 (segment_type, constraint_meta)。

    segment_type：S（简单，可无损重演）/ C（复杂，难重演）。
    简单 = 无「难重演约束」且插值简单；TRACK_TO 等 lookAt 系约束可前端重演，归入简单。
    """
    position_constraints, rotation_constraints = _constraint_summary(camera_object)

    position_complex = (
        any(entry["type"] in COMPLEX_CONSTRAINT_TYPES for entry in position_constraints)
        or not _channel_is_simple(action, "location")
    )
    rotation_complex = (
        any(entry["type"] in COMPLEX_CONSTRAINT_TYPES for entry in rotation_constraints)
        or not _channel_is_simple(action, "rotation_euler")
    )

    segment_type = "C" if (position_complex or rotation_complex) else "S"

    constraint_meta = {}
    if position_constraints:
        constraint_meta["position"] = position_constraints
    if rotation_constraints:
        constraint_meta["rotation"] = rotation_constraints
    return segment_type, constraint_meta


def _orientation_mode(camera_object, start_frame, end_frame, constraint_meta):
    """朝向驱动方式：读相机 TRACK_TO 约束在该段范围内的 influence。

    influence > 0.5 → follow（约束 lookAt 驱动）；否则 interpolate（关键帧插值）。
    旧数据（无 influence 动画、约束恒定生效）退化为：有 TRACK_TO 约束 → follow。
    """
    rotation_constraints = constraint_meta.get("rotation", [])
    if not any(entry.get("type") == "TRACK_TO" for entry in rotation_constraints):
        return "interpolate"

    mid_frame = (start_frame + end_frame) / 2
    for constraint in camera_object.constraints:
        if constraint.type != "TRACK_TO":
            continue
        if _constraint_influence_at(constraint, mid_frame) > 0.5:
            return "follow"
    return "interpolate"


def _constraint_influence_at(constraint, frame):
    """读约束 influence 在指定帧的值（有动画读 fcurve，无动画读常量）。

    约束 influence 的动画存在约束所属对象（相机）的 animation_data 里，
    data_path 形如 `constraints["约束名"].influence`。
    """
    owner = constraint.id_data
    animation_data = owner.animation_data
    if animation_data is not None and animation_data.action is not None:
        fcurve = animation_data.action.fcurves.find(
            f'constraints["{constraint.name}"].influence'
        )
        if fcurve is not None:
            return fcurve.evaluate(frame)
    return constraint.influence


def _filter_inactive_constraints(constraint_meta, orientation_mode):
    """interpolate 段的朝向由关键帧驱动，TRACK_TO 约束（influence=0）不生效，从元数据里去掉。

    follow 段保留原样。去掉后若 constraint_meta 为空，返回 None。
    """
    if not constraint_meta or orientation_mode != "interpolate":
        return constraint_meta
    rotation = constraint_meta.get("rotation", [])
    remaining_rotation = [entry for entry in rotation if entry.get("type") != "TRACK_TO"]
    filtered = dict(constraint_meta)
    if remaining_rotation:
        filtered["rotation"] = remaining_rotation
    else:
        filtered.pop("rotation", None)
    return filtered if filtered else None


def _build_segment(camera_object, action, segment_name, start_frame, end_frame, frames_per_second):
    """构造一个段的 sidecar 数据。"""
    keyframe_times = _action_keyframe_times(action)
    if not keyframe_times:
        return None
    start_pose = _action_pose_at(action, keyframe_times[0])
    end_pose = _action_pose_at(action, keyframe_times[-1])
    segment_type, constraint_meta = _classify_segment(camera_object, action)
    orientation_mode = _orientation_mode(camera_object, start_frame, end_frame, constraint_meta)
    constraint_meta = _filter_inactive_constraints(constraint_meta, orientation_mode)
    segment = {
        "camera_name": camera_object.name,
        "segment_name": segment_name,
        # 首段 strip 可能从 frame 0（而非约定的 frame 1）开始，导致 (0-1)/fps 为负。
        # clamp 到 0，让时间轴从 0 开始，使用者视角「第一段从 0 开始」最直觉。
        "start_time": max(0.0, round((start_frame - 1) / frames_per_second, 3)),
        "end_time": round(end_frame / frames_per_second, 3),
        "start_pose": start_pose,
        "end_pose": end_pose,
        "segment_type": segment_type,
        "orientation_mode": orientation_mode,
        "interpolation": {
            "position": _channel_interpolation(action, "location"),
            "rotation": _channel_interpolation(action, "rotation_euler"),
        },
    }
    if constraint_meta:
        segment["constraint"] = constraint_meta
    return segment


def extract_segments_from_nla():
    """读相机动画，提取镜头段（相机名 / 绝对起止时间 / 类型 / 约束元数据 / 起终点 pose）。

    优先读 NLA strips（约定：一个 track 一个 strip）。
    无 NLA track 但直接挂了 Action 的相机，把 Action 的关键帧范围当成一个段。
    类型分通道判定（位置/朝向）：简单=无约束+glTF插值+≤2 pose；复杂=3+ pose/特殊缓动；约束=有约束。
    """
    import bpy
    segments = []
    frames_per_second = bpy.context.scene.render.fps
    for camera_object in bpy.data.objects:
        if camera_object.type != "CAMERA":
            continue
        animation_data = camera_object.animation_data
        if animation_data is None:
            continue

        # 无 NLA track 但直接挂了 Action：把 Action 的关键帧范围当成一个段
        # （旧项目常见格式：一个相机直接挂 `cam_01动作`，没用 NLA）。
        if not animation_data.nla_tracks and animation_data.action is not None:
            action = animation_data.action
            keyframe_times = _action_keyframe_times(action)
            if not keyframe_times:
                continue
            segment = _build_segment(
                camera_object, action, action.name,
                keyframe_times[0], keyframe_times[-1], frames_per_second,
            )
            if segment is not None:
                segments.append(segment)
            continue

        # 有 NLA track：每个 strip 一个段
        for nla_track in animation_data.nla_tracks:
            for strip in nla_track.strips:
                action = strip.action
                if action is None:
                    continue
                segment = _build_segment(
                    camera_object, action, strip.name,
                    strip.frame_start, strip.frame_end, frames_per_second,
                )
                if segment is not None:
                    segments.append(segment)
    return segments


def get_scene_summary(gltf_filepath):
    """Extract summary info from the exported glTF file.

    Returns a dict with camera names, animation names, mesh count.
    """
    with open(gltf_filepath) as file_handle:
        gltf_data = json.load(file_handle)

    camera_names = []
    if "cameras" in gltf_data:
        for camera_node in gltf_data.get("nodes", []):
            if "camera" in camera_node:
                camera_index = camera_node["camera"]
                if camera_index < len(gltf_data.get("cameras", [])):
                    # 用节点名（= object 名）而非相机数据块名——与 glTF 节点一致
                    camera_names.append(camera_node.get("name", f"Camera_{camera_index}"))

    animation_names = []
    for animation in gltf_data.get("animations", []):
        animation_names.append(animation.get("name", "Unnamed"))

    return {
        "camera_count": len(camera_names),
        "camera_names": camera_names,
        "animation_count": len(animation_names),
        "animation_names": animation_names,
        "mesh_count": len(gltf_data.get("meshes", [])),
    }


def main():
    """Parse CLI arguments and run export."""
    # Blender passes "--" before script args
    argv = sys.argv
    # Find the "--" separator and take everything after it
    try:
        separator_index = argv.index("--")
        script_args = argv[separator_index + 1:]
    except ValueError:
        script_args = argv[argv.index(__file__) + 1:] if __file__ in argv else []

    if len(script_args) < 2:
        print(
            "Usage: blender --background --python export_shot.py -- <input.blend> <output_directory>",
            file=sys.stderr,
        )
        sys.exit(1)

    input_filepath = script_args[0]
    output_directory = script_args[1]

    success = export_blend_to_gltf(input_filepath, output_directory)
    if not success:
        sys.exit(1)

    sys.exit(0)


if __name__ == "__main__":
    main()
