"""
test_04.py — 男人坐在驾驶位看窗外
- 人物：圆柱身体 + 球头（半身坐姿）
- 车：长方体车身 + 车顶 + 圆柱轮子 + 方向盘
- 无摄像机动画
"""
import bpy
import math

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

# ============================================================
# 3. 材质
# ============================================================
def make_material(name, color):
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    mat.diffuse_color = (*color, 1.0)
    for node in mat.node_tree.nodes:
        if node.type == 'BSDF_PRINCIPLED':
            node.inputs["Base Color"].default_value = (*color, 1.0)
            break
    return mat

MAT_BODY    = make_material("CarBody",    (0.85, 0.25, 0.20))  # 红色车身
MAT_ROOF    = make_material("CarRoof",    (0.75, 0.20, 0.15))  # 深红车顶
MAT_WHEEL   = make_material("Wheel",      (0.08, 0.08, 0.10))  # 深灰轮胎
MAT_HUB     = make_material("Hub",        (0.70, 0.70, 0.70))  # 银色轮毂
MAT_MAN     = make_material("ManShirt",   (0.20, 0.35, 0.70))  # 蓝衬衫
MAT_SKIN    = make_material("Skin",       (1.0, 0.85, 0.70))   # 肤色
MAT_SEAT    = make_material("Seat",       (0.25, 0.22, 0.20))  # 深灰座椅
MAT_WHEEL2  = make_material("Steering",   (0.15, 0.15, 0.15))  # 方向盘
MAT_GROUND  = make_material("Ground",     (0.30, 0.32, 0.35))  # 地面

# ============================================================
# 4. 地面
# ============================================================
bpy.ops.mesh.primitive_plane_add(size=20, location=(0, 0, 0))
bpy.context.active_object.data.materials.append(MAT_GROUND)

# ============================================================
# 5. 车身主体
# ============================================================
# 下半车身（只盖到窗沿以下，驾驶舱区域镂空）
bpy.ops.mesh.primitive_cube_add(size=1, location=(0, 0.5, 0.4))
body = bpy.context.active_object
body.name = "CarBody"
body.dimensions = (2.0, 4.0, 0.6)  # 宽2m 长4m 高0.6m(只到腰线)
bpy.ops.object.transform_apply(scale=True)
body.data.materials.append(MAT_BODY)

# ============================================================
# 6. 车顶（更薄）
# ============================================================
bpy.ops.mesh.primitive_cube_add(size=1, location=(0, 0.3, 1.65))
roof = bpy.context.active_object
roof.name = "CarRoof"
roof.dimensions = (1.7, 2.0, 0.12)  # 顶在1.71, 底在1.59, 人头1.56完全在下方
bpy.ops.object.transform_apply(scale=True)
roof.data.materials.append(MAT_ROOF)

# ============================================================
# 6b. 四根立柱（连接车身和车顶，镂空驾驶舱）
# ============================================================
pillar_positions = [
    (-0.7, 1.1),   # 左前
    (0.7, 1.1),    # 右前
    (-0.7, -0.3),  # 左后
    (0.7, -0.3),   # 右后
]
for i, (px, py) in enumerate(pillar_positions):
    bpy.ops.mesh.primitive_cylinder_add(
        radius=0.05, depth=0.9,
        location=(px, py, 1.15)
    )
    pillar = bpy.context.active_object
    pillar.name = f"Pillar_{i+1}"
    pillar.data.materials.append(MAT_ROOF)

# ============================================================
# 8. 轮子（4个圆柱）
# ============================================================
wheel_positions = [
    (-0.8, 1.3, 0.35),   # 左前
    (0.8, 1.3, 0.35),    # 右前
    (-0.8, -0.8, 0.35),  # 左后
    (0.8, -0.8, 0.35),   # 右后
]
for i, (wx, wy, wz) in enumerate(wheel_positions):
    # 轮胎
    bpy.ops.mesh.primitive_cylinder_add(
        radius=0.32, depth=0.25,
        location=(wx, wy, wz),
        rotation=(0, math.pi/2, 0)
    )
    tire = bpy.context.active_object
    tire.name = f"Wheel_{i+1}"
    tire.data.materials.append(MAT_WHEEL)
    # 轮毂
    bpy.ops.mesh.primitive_cylinder_add(
        radius=0.15, depth=0.27,
        location=(wx, wy, wz),
        rotation=(0, math.pi/2, 0)
    )
    hub = bpy.context.active_object
    hub.name = f"Hub_{i+1}"
    hub.data.materials.append(MAT_HUB)

# ============================================================
# 9. 车的细节
# ============================================================
# 前保险杠
bpy.ops.mesh.primitive_cube_add(size=1, location=(0, 2.0, 0.35))
bumper = bpy.context.active_object
bumper.name = "FrontBumper"
bumper.dimensions = (1.6, 0.15, 0.25)
bpy.ops.object.transform_apply(scale=True)
bumper.data.materials.append(make_material("Bumper", (0.35, 0.35, 0.35)))

# 后保险杠
bpy.ops.mesh.primitive_cube_add(size=1, location=(0, -1.0, 0.35))
bumper_r = bpy.context.active_object
bumper_r.name = "RearBumper"
bumper_r.dimensions = (1.6, 0.15, 0.25)
bpy.ops.object.transform_apply(scale=True)
bumper_r.data.materials.append(make_material("BumperR", (0.35, 0.35, 0.35)))

# 车灯（前）
bpy.ops.mesh.primitive_cube_add(size=1, location=(-0.5, 2.05, 0.55))
light_l = bpy.context.active_object
light_l.name = "Headlight_L"
light_l.dimensions = (0.3, 0.05, 0.2)
bpy.ops.object.transform_apply(scale=True)
light_l.data.materials.append(make_material("Light", (1.0, 0.95, 0.75)))

bpy.ops.mesh.primitive_cube_add(size=1, location=(0.5, 2.05, 0.55))
light_r = bpy.context.active_object
light_r.name = "Headlight_R"
light_r.dimensions = (0.3, 0.05, 0.2)
bpy.ops.object.transform_apply(scale=True)
light_r.data.materials.append(make_material("Light", (1.0, 0.95, 0.75)))

# 尾灯
bpy.ops.mesh.primitive_cube_add(size=1, location=(-0.5, -1.05, 0.55))
bpy.context.active_object.name = "Taillight_L"
bpy.context.active_object.dimensions = (0.3, 0.05, 0.2)
bpy.ops.object.transform_apply(scale=True)
bpy.context.active_object.data.materials.append(make_material("TailLight", (1.0, 0.15, 0.10)))

bpy.ops.mesh.primitive_cube_add(size=1, location=(0.5, -1.05, 0.55))
bpy.context.active_object.name = "Taillight_R"
bpy.context.active_object.dimensions = (0.3, 0.05, 0.2)
bpy.ops.object.transform_apply(scale=True)
bpy.context.active_object.data.materials.append(make_material("TailLight", (1.0, 0.15, 0.10)))

# ============================================================
# 10. 驾驶座椅
# ============================================================
bpy.ops.mesh.primitive_cube_add(size=1, location=(-0.5, 0.2, 0.65))
seat = bpy.context.active_object
seat.name = "DriverSeat"
seat.dimensions = (0.5, 0.5, 0.8)
bpy.ops.object.transform_apply(scale=True)
seat.data.materials.append(MAT_SEAT)

# ============================================================
# 11. 方向盘
# ============================================================
bpy.ops.mesh.primitive_cylinder_add(
    radius=0.18, depth=0.04,
    location=(-0.5, 0.9, 1.05),
    rotation=(math.pi/4, 0, 0)  # 倾斜像真实方向盘
)
wheel = bpy.context.active_object
wheel.name = "SteeringWheel"
wheel.data.materials.append(MAT_WHEEL2)

# 方向盘柱
bpy.ops.mesh.primitive_cylinder_add(
    radius=0.03, depth=0.4,
    location=(-0.5, 0.95, 0.8),
    rotation=(math.pi/3, 0, 0)
)
bpy.context.active_object.name = "SteeringColumn"
bpy.context.active_object.data.materials.append(MAT_WHEEL2)

# ============================================================
# 12. 男人（坐姿）
# ============================================================
# 身体 - 较短，模拟坐姿
bpy.ops.mesh.primitive_cylinder_add(
    radius=0.2, depth=0.6,
    location=(-0.5, 0.25, 0.95)  # 降低0.2m
)
man_body = bpy.context.active_object
man_body.name = "Man_Body"
man_body.data.materials.append(MAT_MAN)

# 头
bpy.ops.mesh.primitive_uv_sphere_add(
    radius=0.18,
    location=(-0.5, 0.25, 1.38)  # 降低0.2m
)
man_head = bpy.context.active_object
man_head.name = "Man_Head"
man_head.data.materials.append(MAT_SKIN)

print("车+司机场景已生成")
