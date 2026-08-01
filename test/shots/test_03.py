"""
test_03.py — 咖啡馆场景：男女面对面交谈
- 人物：圆柱身体 + 球头
- 场景：长方体桌子/椅子/柜台，圆柱形的简单装饰
- 静态镜头，无动画
"""
import bpy
import math

# ============================================================
# 1. 清空场景
# ============================================================
bpy.ops.object.select_all(action='SELECT')
bpy.ops.object.delete()

# ============================================================
# 2. 场景设置
# ============================================================
scene = bpy.context.scene
scene.render.resolution_x = 1920
scene.render.resolution_y = 1080
scene.render.resolution_percentage = 100
scene.render.fps = 24
scene.frame_start = 1
scene.frame_end = 1  # 单帧
scene.render.filepath = "/Users/zengle/Documents/storyboard-3d-pipeline/render/test_03.png"
scene.render.image_settings.file_format = 'PNG'
scene.render.engine = 'BLENDER_EEVEE_NEXT'

# 环境光
world = bpy.data.worlds.new("World")
scene.world = world
world.use_nodes = True
for node in world.node_tree.nodes:
    if node.type == 'BACKGROUND':
        node.inputs["Color"].default_value = (0.08, 0.07, 0.06, 1.0)
        node.inputs["Strength"].default_value = 0.4
        break

# ============================================================
# 3. 灯光
# ============================================================
bpy.ops.object.light_add(type='SUN', location=(5, -5, 8), rotation=(math.radians(45), 0, 0))
sun = bpy.context.active_object
sun.data.energy = 2
sun.data.use_shadow = False  # 关阴影

bpy.ops.object.light_add(type='AREA', location=(0, 0, 4))
fill = bpy.context.active_object
fill.data.energy = 60
fill.data.size = 8
fill.data.use_shadow = False  # 关阴影

# EEVEE 全局关阴影
scene.eevee.use_shadows = False
scene.eevee.use_gtao = False

# ============================================================
# 4. 材质函数
# ============================================================
def make_material(name, color, roughness=0.6):
    """创建平色材质：Emission 为主，几乎无阴影"""
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    mat.diffuse_color = color
    nodes = mat.node_tree.nodes
    links = mat.node_tree.links
    
    # 找到输出节点和 Principled BSDF
    output = None
    principled = None
    for node in nodes:
        if node.type == 'OUTPUT_MATERIAL':
            output = node
        elif node.type == 'BSDF_PRINCIPLED':
            principled = node
            node.inputs["Base Color"].default_value = color
            node.inputs["Roughness"].default_value = 1.0
    
    if output and principled:
        # 添加 Emission 节点（纯色，不受光照影响）
        emission = nodes.new(type='ShaderNodeEmission')
        emission.inputs["Color"].default_value = color
        emission.inputs["Strength"].default_value = 0.8
        
        # 添加 Mix Shader（Emission 90% + Principled 10% → 几乎无阴影）
        mix = nodes.new(type='ShaderNodeMixShader')
        mix.inputs["Fac"].default_value = 0.1  # 10% Principled, 90% Emission
        
        # 重新连线: Emission → Mix(上)  Principled → Mix(下)  Mix → Output
        links.new(emission.outputs["Emission"], mix.inputs[1])
        links.new(principled.outputs["BSDF"], mix.inputs[2])
        links.new(mix.outputs["Shader"], output.inputs["Surface"])
    
    return mat

# ============================================================
# 5. 地面
# ============================================================
bpy.ops.mesh.primitive_plane_add(size=20, location=(0, 0, 0))
floor = bpy.context.active_object
floor.name = "Floor"
floor.data.materials.append(make_material("FloorMat", (0.40, 0.35, 0.30, 1.0)))

# ============================================================
# 6. 人物创建函数
# ============================================================
def create_character(name, location, body_color, shirt_color, head_color, radius=0.2):
    """
    圆柱身体 + 球头
    - body: 圆柱 radius=radius, height=1.2, at z=location[2]+0.7
    - head: 球 radius=radius*0.9, at z=location[2]+1.4
    """
    # 腿（短圆柱）
    bpy.ops.mesh.primitive_cylinder_add(
        radius=radius,
        depth=0.7,
        location=(location[0], location[1], location[2] + 0.35)
    )
    legs = bpy.context.active_object
    legs.name = f"{name}_Legs"
    legs.data.materials.append(make_material(f"{name}LegsMat", (0.15, 0.15, 0.2, 1.0)))

    # 身体（圆柱）
    bpy.ops.mesh.primitive_cylinder_add(
        radius=radius,
        depth=0.8,
        location=(location[0], location[1], location[2] + 1.1)
    )
    body = bpy.context.active_object
    body.name = f"{name}_Body"
    mat_body = make_material(f"{name}BodyMat", shirt_color)
    body.data.materials.append(mat_body)

    # 头（球）
    bpy.ops.mesh.primitive_uv_sphere_add(
        radius=radius * 0.85,
        location=(location[0], location[1], location[2] + 1.6)
    )
    head = bpy.context.active_object
    head.name = f"{name}_Head"
    head.data.materials.append(make_material(f"{name}HeadMat", head_color))

    return (legs, body, head)

# ============================================================
# 7. 创建人物
# ============================================================
# 男人（左侧，面向右侧朝女人）
char_m = create_character(
    name="Man",
    location=(-1.0, 0, 0),
    body_color=(0.2, 0.2, 0.2, 1.0),    # 深色裤子
    shirt_color=(0.18, 0.40, 0.75, 1.0), # 蓝色衬衫
    head_color=(1.0, 0.85, 0.70, 1.0),   # 肤色
    radius=0.22
)

# 女人（右侧，面向左侧朝男人）
char_w = create_character(
    name="Woman",
    location=(1.0, 0, 0),
    body_color=(0.2, 0.18, 0.18, 1.0),   # 深色裙子
    shirt_color=(0.85, 0.25, 0.35, 1.0), # 红上衣
    head_color=(1.0, 0.80, 0.68, 1.0),   # 肤色
    radius=0.20
)

# ============================================================
# 8. 场景物体 — 墙壁和装饰
# ============================================================
def create_wall(name, location, scale, color=(0.85, 0.80, 0.72, 1.0)):
    """一面墙：长方体"""
    bpy.ops.mesh.primitive_cube_add(size=1, location=location)
    wall = bpy.context.active_object
    wall.name = name
    wall.scale = scale
    bpy.ops.object.transform_apply(scale=True)
    wall.data.materials.append(make_material("WallMat", color))
    return wall

# 后墙
create_wall("BackWall", (0, 3.5, 1.5), (3.5, 0.15, 1.5))

# 左墙（房间宽约7m，镜头能拍全）
create_wall("LeftWall", (-3.5, 0.5, 1.5), (0.15, 6.0, 1.5))

# 右墙
create_wall("RightWall", (3.5, 0.5, 1.5), (0.15, 6.0, 1.5))

# 天花板
create_wall("Ceiling", (0, 0.5, 3.0), (3.5, 6.0, 0.05), (0.90, 0.88, 0.83, 1.0))

# 门洞装饰（右侧墙壁上的矩形框架）
create_wall("DoorFrame_Top", (3.6, -1.5, 2.3), (0.15, 0.6, 0.3), (0.3, 0.2, 0.12, 1.0))
create_wall("DoorFrame_Left", (3.6, -1.5, 1.1), (0.15, 0.05, 1.1), (0.3, 0.2, 0.12, 1.0))
create_wall("DoorFrame_Right", (3.6, -2.4, 1.1), (0.15, 0.05, 1.1), (0.3, 0.2, 0.12, 1.0))


def create_table(loc):
    """桌子：长方体桌面 + 四根圆柱腿"""
    # 桌面
    bpy.ops.mesh.primitive_cube_add(size=1, location=(loc[0], loc[1], loc[2] + 0.9))
    top = bpy.context.active_object
    top.scale = (0.8, 0.5, 0.04)
    bpy.ops.object.transform_apply(scale=True)
    top.data.materials.append(make_material("TableTop", (0.55, 0.35, 0.15, 1.0)))
    # 腿
    for dx, dy in [(-0.6, -0.35), (0.6, -0.35), (-0.6, 0.35), (0.6, 0.35)]:
        bpy.ops.mesh.primitive_cylinder_add(
            radius=0.03, depth=0.8,
            location=(loc[0]+dx, loc[1]+dy, loc[2]+0.45)
        )
        leg = bpy.context.active_object
        leg.data.materials.append(make_material("TableLeg", (0.35, 0.25, 0.12, 1.0)))
    return top

def create_chair(loc):
    """椅子：立方体座面 + 靠背 + 四根腿"""
    # 座面
    bpy.ops.mesh.primitive_cube_add(size=1, location=(loc[0], loc[1], loc[2] + 0.55))
    seat = bpy.context.active_object
    seat.scale = (0.22, 0.22, 0.03)
    bpy.ops.object.transform_apply(scale=True)
    seat.data.materials.append(make_material("ChairSeat", (0.25, 0.20, 0.18, 1.0)))
    # 靠背
    bpy.ops.mesh.primitive_cube_add(size=1, location=(loc[0], loc[1]-0.18, loc[2]+0.85))
    back = bpy.context.active_object
    back.scale = (0.18, 0.02, 0.20)
    bpy.ops.object.transform_apply(scale=True)
    back.data.materials.append(make_material("ChairBack", (0.25, 0.20, 0.18, 1.0)))
    # 腿
    for dx, dy in [(-0.15, -0.15), (0.15, -0.15), (-0.15, 0.15), (0.15, 0.15)]:
        bpy.ops.mesh.primitive_cylinder_add(
            radius=0.02, depth=0.5,
            location=(loc[0]+dx, loc[1]+dy, loc[2]+0.25)
        )
        bpy.context.active_object.data.materials.append(
            make_material("ChairLeg", (0.2, 0.18, 0.15, 1.0))
        )
    return seat

def create_counter(loc):
    """柜台：长立方体"""
    bpy.ops.mesh.primitive_cube_add(size=1, location=(loc[0], loc[1], loc[2] + 0.55))
    counter = bpy.context.active_object
    counter.scale = (3.0, 0.4, 0.55)
    bpy.ops.object.transform_apply(scale=True)
    counter.data.materials.append(make_material("Counter", (0.50, 0.42, 0.35, 1.0)))
    # 台面上放几个杯子（小圆柱）
    for dx in [-1.0, -0.3, 0.5, 1.2]:
        bpy.ops.mesh.primitive_cylinder_add(
            radius=0.04, depth=0.12,
            location=(loc[0]+dx, loc[1]+0.2, loc[2]+1.05)
        )
        cup = bpy.context.active_object
        cup.data.materials.append(make_material("Cup", (0.9, 0.9, 0.85, 1.0)))
    return counter

# 背景摆放桌子（两排）
for i in range(3):
    create_table((-2.0 + i * 1.6, 2.5, 0))
    create_chair((-2.3 + i * 1.6, 2.8, 0))
    create_chair((-1.7 + i * 1.6, 2.2, 0))

# 另一排桌子
for i in range(2):
    create_table((-1.0 + i * 2.0, 3.0, 0))
    create_chair((-1.3 + i * 2.0, 3.3, 0))

# 柜台（后墙前方）
create_counter((0, 2.8, 0))

# ============================================================
# 9. 镜头 — 中景，正对两人
# ============================================================
bpy.ops.object.camera_add(location=(0, -2.5, 1.5))
camera = bpy.context.active_object
camera.name = "ShotCamera"
scene.camera = camera
camera.data.lens = 18  # 广角拍下封闭室内全貌

# 看向两人中间
bpy.ops.object.empty_add(type='PLAIN_AXES', location=(0, 0, 1.2))
look_at = bpy.context.active_object
constraint = camera.constraints.new(type='TRACK_TO')
constraint.target = look_at
constraint.track_axis = 'TRACK_NEGATIVE_Z'
constraint.up_axis = 'UP_Y'

# ============================================================
# 10. 渲染单帧
# ============================================================
print("开始渲染...")
bpy.ops.render.render(write_still=True)
bpy.ops.wm.save_as_mainfile(filepath="/Users/zengle/Documents/storyboard-3d-pipeline/render/test_03.blend")
print("渲染完成! .blend 已保存")
