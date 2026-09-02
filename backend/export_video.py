"""Blender video export script — renders one chunk of one camera's shot/segment.

Called via: blender --background --python export_video.py -- <description.json>
Description: {"blend": ..., "output_dir": ..., "resolution": "1080p"|"720p",
              "chunk": {"task_name": ..., "camera_name": ..., "frame_start": ...,
                        "frame_end": ..., "frames_dir": ...}}
Renders PNG frames to <frames_dir>/frame_0000.png ... via animation render.
The host process (main.py) orchestrates chunks (restarting Blender per chunk to
avoid the per-process render accumulation hang), the manifest, and MP4 composition.
"""
import sys
import os
import json


def render_chunk(description_file):
    import bpy

    with open(description_file) as file_handle:
        desc = json.load(file_handle)

    blend = desc["blend"]
    resolution = desc.get("resolution", "1080p")
    chunk = desc["chunk"]
    task_name = chunk["task_name"]
    camera_name = chunk["camera_name"]
    frame_start = chunk["frame_start"]
    frame_end = chunk["frame_end"]
    frames_dir = chunk["frames_dir"]

    if not os.path.isfile(blend):
        print(f"ERROR: Input blend not found: {blend}", file=sys.stderr)
        return False

    try:
        bpy.ops.wm.open_mainfile(filepath=blend)
    except Exception as error:
        print(f"ERROR: Failed to open blend: {error}", file=sys.stderr)
        return False

    scene = bpy.context.scene
    scene.render.image_settings.file_format = "PNG"

    if resolution == "720p":
        scale = 1280 / scene.render.resolution_x
        scene.render.resolution_x = 1280
        scene.render.resolution_y = max(1, int(scene.render.resolution_y * scale))
        scene.render.resolution_percentage = 100

    camera_obj = bpy.data.objects.get(camera_name)
    if camera_obj is None:
        print(f"ERROR: Camera not found: {camera_name} (task {task_name})", file=sys.stderr)
        return False
    scene.camera = camera_obj

    os.makedirs(frames_dir, exist_ok=True)

    # 色彩增强：CurveRGB S 曲线压暗部 + 提亮高光（每通道独立曲线，保留色彩），避免均匀光照下输出灰蒙蒙
    scene.use_nodes = True
    node_tree = scene.node_tree
    node_tree.nodes.clear()
    rl_node = node_tree.nodes.new("CompositorNodeRLayers")
    comp_node = node_tree.nodes.new("CompositorNodeComposite")
    curve_node = node_tree.nodes.new("CompositorNodeCurveRGB")
    for channel in range(4):
        points = curve_node.mapping.curves[channel].points
        points[0].location = (0.0, 0.0)
        points[1].location = (1.0, 1.0)
        points.new(0.62, 0.42)
        points.new(0.90, 0.95)
    node_tree.links.new(rl_node.outputs["Image"], curve_node.inputs["Image"])
    node_tree.links.new(curve_node.outputs["Image"], comp_node.inputs["Image"])

    scene.frame_start = frame_start
    scene.frame_end = frame_end
    scene.render.filepath = os.path.join(frames_dir, "frame_")
    bpy.ops.render.render(animation=True)
    return True


def main():
    argv = sys.argv
    try:
        separator_index = argv.index("--")
        script_args = argv[separator_index + 1:]
    except ValueError:
        script_args = argv[argv.index(__file__) + 1:] if __file__ in argv else []
    if len(script_args) < 1:
        print("Usage: blender --background --python export_video.py -- <description.json>", file=sys.stderr)
        sys.exit(1)
    ok = render_chunk(script_args[0])
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
