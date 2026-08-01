"""
验证脚本：渲染关键帧静帧，检查镜头构图
- 帧1：起始位置
- 帧30：推近中途
- 帧60：推近完成（定格开始）
- 帧72：最终定格
"""
import bpy

# 加载现有的 test_01.blend
scene = bpy.context.scene
scene.render.image_settings.file_format = 'PNG'
scene.render.resolution_percentage = 50  # 半分辨率加快预览

for frame in [1, 30, 60, 72]:
    scene.frame_set(frame)
    scene.render.filepath = f"/Users/zengle/Documents/storyboard-3d-pipeline/render/preview_frame_{frame:03d}.png"
    bpy.ops.render.render(write_still=True)
    print(f"帧 {frame} 已渲染")
