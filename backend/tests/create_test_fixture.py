"""Create a minimal fixture .blend with cube + camera for testing export."""
import bpy
import os
import math

# Clean default scene
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.object.select_all(action='SELECT')
bpy.ops.object.delete()

# Add default cube at origin
bpy.ops.mesh.primitive_cube_add(
    size=2,
    location=(0, 0, 1)
)

# Add simple material
material = bpy.data.materials.new(name="TestMaterial")
material.use_nodes = True
for node in material.node_tree.nodes:
    if node.type == 'BSDF_PRINCIPLED':
        node.inputs["Base Color"].default_value = (1.0, 0.0, 0.0, 1.0)  # Red
        break
bpy.context.active_object.data.materials.append(material)

# Add camera
bpy.ops.object.camera_add(location=(5, -5, 3))
camera = bpy.context.active_object
camera.rotation_euler = (math.radians(60), 0, math.radians(45))
camera.name = "MainCamera"
bpy.context.scene.camera = camera

# Add animation: cube moves up 2 units over 24 frames at 24fps
cube = bpy.data.objects[0]  # The cube
cube.keyframe_insert(data_path="location", frame=1)
cube.location.z = 3
cube.keyframe_insert(data_path="location", frame=24)

bpy.context.scene.frame_start = 1
bpy.context.scene.frame_end = 24
bpy.context.scene.render.fps = 24

# Save fixture
output_path = os.path.join(os.path.dirname(__file__), "fixture_minimal.blend")
bpy.ops.wm.save_as_mainfile(filepath=output_path)
print(f"Fixture saved: {output_path}")
