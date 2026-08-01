"""验证 test_02 关键帧构图"""
import bpy

scene = bpy.context.scene
scene.render.image_settings.file_format = 'PNG'
scene.render.resolution_percentage = 50

for frame in [1, 30, 60, 72]:
    scene.frame_set(frame)
    scene.render.filepath = f"/Users/zengle/Documents/storyboard-3d-pipeline/render/test02_frame_{frame:03d}.png"
    bpy.ops.render.render(write_still=True)
    print(f"帧 {frame} 已渲染")
