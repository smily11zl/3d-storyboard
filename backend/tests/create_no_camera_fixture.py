"""Create a minimal fixture .blend with cube but NO camera for testing no-camera edge case."""
import bpy
import os

bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.object.select_all(action='SELECT')
bpy.ops.object.delete()

# Add cube only, no camera
bpy.ops.mesh.primitive_cube_add(size=2, location=(0, 0, 1))
bpy.context.scene.frame_start = 1
bpy.context.scene.frame_end = 1
bpy.context.scene.render.fps = 24

output_path = os.path.join(os.path.dirname(__file__), "fixture_no_camera.blend")
bpy.ops.wm.save_as_mainfile(filepath=output_path)
print(f"Fixture saved: {output_path}")
