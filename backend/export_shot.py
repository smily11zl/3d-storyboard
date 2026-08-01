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
    print(json.dumps(scene_info, indent=2, ensure_ascii=False))

    return True


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
                    camera_names.append(gltf_data["cameras"][camera_index].get("name", f"Camera_{camera_index}"))

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
