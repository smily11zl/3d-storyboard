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
                        rotation_fcurve = None
                        for fcurve in action.fcurves:
                            if (
                                fcurve.data_path == "rotation_euler"
                                and fcurve.array_index == axis_index
                            ):
                                rotation_fcurve = fcurve
                                break
                        if rotation_fcurve is None:
                            rotation_fcurve = action.fcurves.new(
                                data_path="rotation_euler", index=axis_index
                            )
                        rotation_fcurve.keyframe_points.insert(
                            frame, rotation_euler[axis_index]
                        )
                        rotation_fcurve.keyframe_points[-1].interpolation = "LINEAR"

    gltf_filepath = os.path.join(output_directory, "scene.gltf")

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
        return False

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


def _action_pose_at(action, time):
    """读 action 在某个时刻的 position + rotation（用 F-Curve evaluate 求值）。"""
    position = [0.0, 0.0, 0.0]
    rotation = [0.0, 0.0, 0.0]
    for fcurve in action.fcurves:
        if fcurve.data_path == "location" and 0 <= fcurve.array_index < 3:
            position[fcurve.array_index] = round(fcurve.evaluate(time), 4)
        elif fcurve.data_path == "rotation_euler" and 0 <= fcurve.array_index < 3:
            rotation[fcurve.array_index] = round(fcurve.evaluate(time), 4)
    return {"position": position, "rotation": rotation}


def _count_distinct_poses(action):
    """数 action 里去重后的 pose 数（position + rotation 组合）。"""
    poses = set()
    for time in _action_keyframe_times(action):
        pose = _action_pose_at(action, time)
        poses.add((tuple(pose["position"]), tuple(pose["rotation"])))
    return len(poses)


def extract_segments_from_nla():
    """读相机动画，提取镜头段（相机名 / 绝对起止时间 / S-C / 起终点 pose）。

    优先读 NLA strips（约定：一个 track 一个 strip）。
    无 NLA track 但直接挂了 Action 的相机，把 Action 的关键帧范围当成一个段。
    S（简单）= 去重后 pose 数 ≤ 2；C（复杂）= > 2。
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
            pose_count = _count_distinct_poses(action)
            segment_type = "S" if pose_count <= 2 else "C"
            start_pose = _action_pose_at(action, keyframe_times[0])
            end_pose = _action_pose_at(action, keyframe_times[-1])
            segments.append({
                "camera_name": camera_object.name,
                "segment_name": action.name,
                "start_time": round((keyframe_times[0] - 1) / frames_per_second, 3),
                "end_time": round(keyframe_times[-1] / frames_per_second, 3),
                "start_pose": start_pose,
                "end_pose": end_pose,
                "segment_type": segment_type,
            })
            continue

        for nla_track in animation_data.nla_tracks:
            for strip in nla_track.strips:
                action = strip.action
                if action is None:
                    continue
                pose_count = _count_distinct_poses(action)
                segment_type = "S" if pose_count <= 2 else "C"
                keyframe_times = _action_keyframe_times(action)
                if not keyframe_times:
                    continue
                start_pose = _action_pose_at(action, keyframe_times[0])
                end_pose = _action_pose_at(action, keyframe_times[-1])
                segments.append({
                    "camera_name": camera_object.name,
                    "segment_name": strip.name,
                    "start_time": round((strip.frame_start - 1) / frames_per_second, 3),
                    "end_time": round(strip.frame_end / frames_per_second, 3),
                    "start_pose": start_pose,
                    "end_pose": end_pose,
                    "segment_type": segment_type,
                })
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
