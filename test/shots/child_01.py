"""
child_01.py — 低模小孩 1m 高
"""
import bpy, math

OUT = "/Users/zengle/Documents/storyboard-3d-pipeline/characters/child_01.blend"

bpy.ops.object.select_all(action='SELECT')
bpy.ops.object.delete()

bpy.context.scene.render.engine = 'BLENDER_EEVEE_NEXT'
bpy.context.scene.unit_settings.system = 'METRIC'

def make_material(name, color):
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    mat.diffuse_color = (*color, 1.0)
    for node in mat.node_tree.nodes:
        if node.type == 'BSDF_PRINCIPLED':
            node.inputs["Base Color"].default_value = (*color, 1.0)
            break
    return mat

MAT_SKIN = make_material("Skin",   (1.0, 0.82, 0.68))
MAT_SHIRT = make_material("Shirt", (0.25, 0.55, 0.85))
MAT_PANTS = make_material("Pants", (0.25, 0.28, 0.35))
MAT_SHOE = make_material("Shoe",  (0.12, 0.10, 0.10))
MAT_HAIR = make_material("Hair",  (0.15, 0.10, 0.08))

# ============================================================
# 包围盒：总高1m
# ============================================================
# 腿: z=0.15~0.45 (30cm)
# 身体: z=0.45~0.68 (23cm, 小孩身体短)
# 头: z=0.68~1.0 (32cm, 小孩头比例大)
# ============================================================

# 左腿
bpy.ops.mesh.primitive_cylinder_add(radius=0.05, depth=0.3, location=(-0.08, 0, 0.3))
l = bpy.context.active_object; l.name="Leg.L"; l.data.materials.append(MAT_PANTS)
# 右腿
bpy.ops.mesh.primitive_cylinder_add(radius=0.05, depth=0.3, location=(0.08, 0, 0.3))
r = bpy.context.active_object; r.name="Leg.R"; r.data.materials.append(MAT_PANTS)

# 左鞋
bpy.ops.mesh.primitive_cube_add(size=1, location=(-0.08, 0.04, 0.1))
s = bpy.context.active_object; s.name="Shoe.L"; s.dimensions=(0.12,0.18,0.08)
bpy.ops.object.transform_apply(scale=True); s.data.materials.append(MAT_SHOE)
# 右鞋
bpy.ops.mesh.primitive_cube_add(size=1, location=(0.08, 0.04, 0.1))
s = bpy.context.active_object; s.name="Shoe.R"; s.dimensions=(0.12,0.18,0.08)
bpy.ops.object.transform_apply(scale=True); s.data.materials.append(MAT_SHOE)

# 身体
bpy.ops.mesh.primitive_cylinder_add(radius=0.13, depth=0.23, location=(0, 0, 0.565))
body = bpy.context.active_object; body.name="Body"; body.data.materials.append(MAT_SHIRT)

# 左臂
bpy.ops.mesh.primitive_cylinder_add(radius=0.04, depth=0.25, location=(-0.16, 0, 0.6))
la = bpy.context.active_object; la.name="Arm.L"; la.data.materials.append(MAT_SHIRT)
# 右臂
bpy.ops.mesh.primitive_cylinder_add(radius=0.04, depth=0.25, location=(0.16, 0, 0.6))
ra = bpy.context.active_object; ra.name="Arm.R"; ra.data.materials.append(MAT_SHIRT)

# 头
bpy.ops.mesh.primitive_uv_sphere_add(radius=0.14, location=(0, 0, 0.82))
head = bpy.context.active_object; head.name="Head"; head.data.materials.append(MAT_SKIN)

# 头发（半球）
bpy.ops.mesh.primitive_uv_sphere_add(radius=0.145, location=(0, 0, 0.90))
hair = bpy.context.active_object; hair.name="Hair"
hair.scale = (1, 1, 0.6); bpy.ops.object.transform_apply(scale=True)
# 删除下半球顶点
bpy.ops.object.mode_set(mode='EDIT')
bpy.ops.mesh.select_all(action='SELECT')
bpy.ops.mesh.bisect(plane_co=(0,0,0.88), plane_no=(0,0,-1), clear_inner=True)
bpy.ops.object.mode_set(mode='OBJECT')
hair.data.materials.append(MAT_HAIR)

# 眼睛
for ex in [-0.05, 0.05]:
    bpy.ops.mesh.primitive_uv_sphere_add(radius=0.018, location=(ex, 0.12, 0.85))
    eye = bpy.context.active_object
    eye.data.materials.append(make_material("Eye", (0.05, 0.05, 0.10)))

bpy.ops.wm.save_as_mainfile(filepath=OUT)
print("✅ child_01.blend 已生成 (1m 小孩)")
