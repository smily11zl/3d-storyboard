"""
test_05.py — 海边场景：一个人看海
- 沙滩、海面、石头、其他人
- 简单几何体：圆柱身体+球头，长方体/球体场景元素
"""
import bpy
import math
import random

# ============================================================
# 1. 清空
# ============================================================
bpy.ops.object.select_all(action='SELECT')
bpy.ops.object.delete()

# ============================================================
# 2. 场景设置
# ============================================================
scene = bpy.context.scene
scene.render.engine = 'BLENDER_EEVEE_NEXT'
scene.unit_settings.system = 'METRIC'
scene.unit_settings.length_unit = 'METERS'

# ============================================================
# 3. 包围盒验算（先算后写！）
# ============================================================
# 人物（站立）：
#   身体: z_center=0.55 depth=1.1 → [0.0, 1.1]
#   头:   z_center=1.3  r=0.22  → [1.08, 1.52]
#   总高: 1.52m
#
# 沙滩: z=0 平面
# 海面: z=-0.02 平面, y≥3
# 石头: 球体 r=0.1~0.3, z=r (坐在沙滩上)
# 其他人: 同人物比例, 散布在 y=2.5~4

# ============================================================
# 4. 材质函数
# ============================================================
def make_material(name, color, roughness=0.6):
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    mat.diffuse_color = (*color, 1.0)
    for node in mat.node_tree.nodes:
        if node.type == 'BSDF_PRINCIPLED':
            node.inputs["Base Color"].default_value = (*color, 1.0)
            node.inputs["Roughness"].default_value = roughness
            break
    return mat

MAT_SAND    = make_material("Sand",    (0.85, 0.78, 0.62))   # 沙滩色
MAT_SEA     = make_material("Sea",     (0.15, 0.40, 0.65), 0.3)  # 海水蓝
MAT_SKIN    = make_material("Skin",    (1.0, 0.85, 0.70))    # 肤色
MAT_SHIRT   = make_material("Shirt",   (0.75, 0.80, 0.85))   # 白T恤
MAT_PANTS   = make_material("Pants",   (0.25, 0.30, 0.40))   # 深蓝裤
MAT_SHIRT2  = make_material("Shirt2",  (0.85, 0.35, 0.30))   # 红T恤(其他人)
MAT_ROCK    = make_material("Rock",    (0.45, 0.42, 0.38), 0.8)  # 石头
MAT_TREE    = make_material("Tree",    (0.35, 0.25, 0.15))    # 树干
MAT_LEAF    = make_material("Leaf",    (0.25, 0.55, 0.20))    # 树叶
MAT_SKY     = make_material("Sky",     (0.55, 0.75, 0.95))    # 天空色（背景板）

# ============================================================
# 5. 沙滩
# ============================================================
bpy.ops.mesh.primitive_plane_add(size=20, location=(0, 2, 0))
sand = bpy.context.active_object
sand.name = "Sand"
sand.data.materials.append(MAT_SAND)

# ============================================================
# 6. 海面
# ============================================================
bpy.ops.mesh.primitive_plane_add(size=20, location=(0, 7, -0.02))
sea = bpy.context.active_object
sea.name = "Sea"
sea.data.materials.append(MAT_SEA)

# ============================================================
# 7. 人物创建函数
# ============================================================
def create_person(name, location, shirt_mat, facing_y=True):
    """圆柱身体 + 球头"""
    x, y, z = location

    # 腿（短圆柱）
    bpy.ops.mesh.primitive_cylinder_add(
        radius=0.18, depth=0.6,
        location=(x, y, z + 0.3)
    )
    legs = bpy.context.active_object
    legs.name = f"{name}_Legs"
    legs.data.materials.append(MAT_PANTS)

    # 身体
    bpy.ops.mesh.primitive_cylinder_add(
        radius=0.22, depth=0.8,
        location=(x, y, z + 0.9)
    )
    body = bpy.context.active_object
    body.name = f"{name}_Body"
    body.data.materials.append(shirt_mat)

    # 头
    bpy.ops.mesh.primitive_uv_sphere_add(
        radius=0.22,
        location=(x, y, z + 1.42)
    )
    head = bpy.context.active_object
    head.name = f"{name}_Head"
    head.data.materials.append(MAT_SKIN)

    print(f"  {name}: 脚底{z:.2f} 头顶{z+1.64:.2f} 身高{1.64:.2f}m")


# ============================================================
# 8. 主角（面向海面，站沙滩上）
# ============================================================
print("人物包围盒：")
create_person("Main", (0, 2.5, 0), MAT_SHIRT)

# ============================================================
# 9. 其他人物（散布在背景中）
# ============================================================
others = [
    (-1.5, 3.5, 0),   # 左后方
    (1.8, 3.2, 0),     # 右后方
    (-0.8, 4.0, 0),    # 远处左
    (2.2, 4.5, 0),     # 远处右
]
for i, pos in enumerate(others):
    create_person(f"Other_{i+1}", pos, MAT_SHIRT2)

# ============================================================
# 10. 石头（散布沙滩上）
# ============================================================
# 用固定种子保证一致性
random.seed(42)
rock_positions = []
for _ in range(15):
    rx = random.uniform(-4, 4)
    ry = random.uniform(0.5, 2.0)
    rr = random.uniform(0.08, 0.25)
    # 避免和人重叠
    if abs(rx) < 0.6 and ry < 3.0:
        continue
    rock_positions.append((rx, ry, rr))

for i, (rx, ry, rr) in enumerate(rock_positions):
    bpy.ops.mesh.primitive_uv_sphere_add(
        radius=rr,
        location=(rx, ry, rr)  # 坐沙上,球心=半径
    )
    rock = bpy.context.active_object
    rock.name = f"Rock_{i+1}"
    rock.data.materials.append(MAT_ROCK)

# ============================================================
# 11. 简易椰子树（圆柱干 + 球冠）
# ============================================================
tree_x, tree_y = (-3.5, 2.0)
# 树干
bpy.ops.mesh.primitive_cylinder_add(
    radius=0.12, depth=2.5,
    location=(tree_x, tree_y, 1.25)
)
trunk = bpy.context.active_object
trunk.name = "Tree_Trunk"
trunk.data.materials.append(MAT_TREE)

# 树冠（几个球）
for angle in [0, 2*math.pi/5, 4*math.pi/5, 6*math.pi/5, 8*math.pi/5]:
    bx = tree_x + 0.6 * math.cos(angle)
    by = tree_y + 0.5 * math.sin(angle)
    bpy.ops.mesh.primitive_uv_sphere_add(
        radius=0.4,
        location=(bx, by, 2.4)
    )
    leaf = bpy.context.active_object
    leaf.name = "Tree_Leaf"
    leaf.data.materials.append(MAT_LEAF)

# 第二棵小树
tree2_x, tree2_y = (4.0, 2.5)
bpy.ops.mesh.primitive_cylinder_add(
    radius=0.08, depth=1.5,
    location=(tree2_x, tree2_y, 0.75)
)
bpy.context.active_object.name = "Tree2_Trunk"
bpy.context.active_object.data.materials.append(MAT_TREE)

bpy.ops.mesh.primitive_uv_sphere_add(
    radius=0.3,
    location=(tree2_x, tree2_y, 1.6)
)
bpy.context.active_object.name = "Tree2_Leaf"
bpy.context.active_object.data.materials.append(MAT_LEAF)

# ============================================================
# 12. 简易海鸥（远处天空的小V字形，用三角面模拟）
# 略 — 太复杂，保持极简
# ============================================================

# ============================================================
# 13. 背景天空板（远处竖立）
# ============================================================
bpy.ops.mesh.primitive_cube_add(size=1, location=(0, 8, 2.5))
sky = bpy.context.active_object
sky.name = "SkyBoard"
sky.dimensions = (12, 0.1, 5)
bpy.ops.object.transform_apply(scale=True)
sky.data.materials.append(MAT_SKY)

print("\n✅ 海边场景已生成")
print("   主角: (0, 2.5, 0) 面向海面")
print("   海面: y≥3 ")
print("   其他人: 4人散布在背景")
print("   石头: 15块")
print("   椰子树: 2棵")
