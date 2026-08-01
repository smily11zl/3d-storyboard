import bpy
import math
from mathutils import Vector

# ============================================================
# Minimal 3D Storyboard Scene
# Coffee Shop - Two People Talking
#
# Coordinate:
# X = left / right
# Y = front / back
# Z = up
#
# Unit: meter
# ============================================================


# ============================================================
# Scene Cleanup
# ============================================================

bpy.ops.object.select_all(action='SELECT')
bpy.ops.object.delete(use_global=False)

# Remove unused data
for datablocks in (
    bpy.data.meshes,
    bpy.data.curves,
    bpy.data.materials,
    bpy.data.cameras,
    bpy.data.lights,
):
    for datablock in list(datablocks):
        if datablock.users == 0:
            datablocks.remove(datablock)


# ============================================================
# Materials
# Simple viewport-friendly materials
# ============================================================

def create_material(name, color):
    mat = bpy.data.materials.new(name)
    mat.diffuse_color = (*color, 1.0)
    return mat


MAT_FLOOR = create_material("Floor", (0.35, 0.35, 0.35))
MAT_WALL = create_material("Wall", (0.65, 0.65, 0.65))
MAT_MAN = create_material("Man", (0.2, 0.4, 0.8))
MAT_WOMAN = create_material("Woman", (0.8, 0.35, 0.45))
MAT_FURNITURE = create_material("Furniture", (0.45, 0.30, 0.18))
MAT_COUNTER = create_material("Counter", (0.25, 0.25, 0.25))


# ============================================================
# Helper Functions
# ============================================================

def create_cube(name, location, scale, material=None):
    """
    Create a cube.

    scale = (width, depth, height)
    """

    bpy.ops.mesh.primitive_cube_add(
        size=1,
        location=location
    )

    obj = bpy.context.object
    obj.name = name

    obj.dimensions = scale

    # Apply scale so dimensions become actual geometry
    bpy.ops.object.transform_apply(
        location=False,
        rotation=False,
        scale=True
    )

    if material:
        obj.data.materials.append(material)

    return obj


def create_cylinder(name, location, radius, depth, material=None):
    bpy.ops.mesh.primitive_cylinder_add(
        vertices=16,
        radius=radius,
        depth=depth,
        location=location
    )

    obj = bpy.context.object
    obj.name = name

    if material:
        obj.data.materials.append(material)

    return obj


def create_sphere(name, location, radius, material=None):
    bpy.ops.mesh.primitive_uv_sphere_add(
        segments=16,
        ring_count=8,
        radius=radius,
        location=location
    )

    obj = bpy.context.object
    obj.name = name

    if material:
        obj.data.materials.append(material)

    return obj


# ============================================================
# Floor
# ============================================================

create_cube(
    "Floor",
    location=(0, 0, -0.05),
    scale=(14, 12, 0.1),
    material=MAT_FLOOR
)


# ============================================================
# Walls
# Simple open coffee shop
# ============================================================

# Back wall
create_cube(
    "BackWall",
    location=(0, 5.8, 2.0),
    scale=(14, 0.2, 4),
    material=MAT_WALL
)

# Left wall
create_cube(
    "LeftWall",
    location=(-6.9, 0, 2.0),
    scale=(0.2, 12, 4),
    material=MAT_WALL
)

# Right wall
create_cube(
    "RightWall",
    location=(6.9, 0, 2.0),
    scale=(0.2, 12, 4),
    material=MAT_WALL
)


# ============================================================
# Character
# Minimal character:
# body = cylinder
# head = sphere
# ============================================================

def create_character(
    name,
    position,
    body_material,
    facing_angle=0
):
    x, y, z = position

    # Body
    body_height = 1.1
    body_radius = 0.28

    body = create_cylinder(
        name=f"{name}_Body",
        location=(x, y, z + body_height / 2),
        radius=body_radius,
        depth=body_height,
        material=body_material
    )

    # Head
    head_radius = 0.32

    head = create_sphere(
        name=f"{name}_Head",
        location=(
            x,
            y,
            z + body_height + head_radius
        ),
        radius=head_radius,
        material=body_material
    )

    # Create parent empty so character can be rotated together
    bpy.ops.object.empty_add(
        type='PLAIN_AXES',
        location=(x, y, z)
    )

    root = bpy.context.object
    root.name = name

    body.parent = root
    head.parent = root

    root.rotation_euler[2] = facing_angle

    return root


# ============================================================
# Main Characters
# ============================================================

# Man on the left
man = create_character(
    name="Man",
    position=(-1.0, 0.0, 0),
    body_material=MAT_MAN,
    facing_angle=0
)

# Woman on the right
woman = create_character(
    name="Woman",
    position=(1.0, 0.0, 0),
    body_material=MAT_WOMAN,
    facing_angle=math.pi
)


# ============================================================
# Tables
# ============================================================

def create_table(name, location):
    x, y, z = location

    # Table top
    create_cube(
        f"{name}_Top",
        location=(x, y, z + 0.75),
        scale=(1.6, 0.8, 0.12),
        material=MAT_FURNITURE
    )

    # Legs
    leg_positions = [
        (-0.65, -0.3),
        (0.65, -0.3),
        (-0.65, 0.3),
        (0.65, 0.3),
    ]

    for i, (lx, ly) in enumerate(leg_positions):
        create_cube(
            f"{name}_Leg_{i+1}",
            location=(x + lx, y + ly, z + 0.35),
            scale=(0.12, 0.12, 0.7),
            material=MAT_FURNITURE
        )


# Back tables
create_table(
    "Table_01",
    (-3.5, 3.0, 0)
)

create_table(
    "Table_02",
    (0.0, 3.0, 0)
)

create_table(
    "Table_03",
    (3.5, 3.0, 0)
)


# ============================================================
# Chairs
# ============================================================

def create_chair(name, location, rotation=0):
    x, y, z = location

    # Seat
    seat = create_cube(
        f"{name}_Seat",
        location=(x, y, z + 0.45),
        scale=(0.6, 0.6, 0.12),
        material=MAT_FURNITURE
    )

    # Four legs simplified to four cubes
    for i, (lx, ly) in enumerate([
        (-0.22, -0.22),
        (0.22, -0.22),
        (-0.22, 0.22),
        (0.22, 0.22),
    ]):
        create_cube(
            f"{name}_Leg_{i+1}",
            location=(x + lx, y + ly, z + 0.2),
            scale=(0.08, 0.08, 0.4),
            material=MAT_FURNITURE
        )

    # Backrest
    create_cube(
        f"{name}_Back",
        location=(x, y + 0.27, z + 0.85),
        scale=(0.6, 0.1, 0.8),
        material=MAT_FURNITURE
    )


# Chairs around tables

chair_positions = [
    (-3.5, 2.2),
    (-3.5, 3.8),
    (0.0, 2.2),
    (0.0, 3.8),
    (3.5, 2.2),
    (3.5, 3.8),
]

for i, (x, y) in enumerate(chair_positions):
    create_chair(
        f"Chair_{i+1}",
        (x, y, 0)
    )


# ============================================================
# Coffee Counter
# ============================================================

create_cube(
    "CoffeeCounter",
    location=(3.8, 5.0, 1.0),
    scale=(4.5, 0.8, 2.0),
    material=MAT_COUNTER
)

# Counter top
create_cube(
    "CoffeeCounter_Top",
    location=(3.8, 5.0, 2.05),
    scale=(4.7, 0.9, 0.15),
    material=MAT_FURNITURE
)


# ============================================================
# Simple coffee machines / objects
# Everything remains primitive geometry
# ============================================================

create_cube(
    "CoffeeMachine",
    location=(2.8, 4.8, 2.45),
    scale=(0.5, 0.4, 0.5),
    material=MAT_WALL
)

create_cube(
    "CoffeeMachine_02",
    location=(3.7, 4.8, 2.35),
    scale=(0.4, 0.4, 0.4),
    material=MAT_WALL
)


# ============================================================
# Simple decorative objects
# ============================================================

# Small plant
create_cylinder(
    "PlantPot",
    location=(-5.5, 4.5, 0.35),
    radius=0.3,
    depth=0.7,
    material=MAT_FURNITURE
)

create_cylinder(
    "Plant",
    location=(-5.5, 4.5, 1.4),
    radius=0.15,
    depth=2.0,
    material=MAT_WALL
)


# ============================================================
# Organize objects into collections
# ============================================================

def create_collection(name):
    collection = bpy.data.collections.get(name)

    if not collection:
        collection = bpy.data.collections.new(name)
        bpy.context.scene.collection.children.link(collection)

    return collection


characters_collection = create_collection("CHARACTERS")
environment_collection = create_collection("ENVIRONMENT")
furniture_collection = create_collection("FURNITURE")


# ============================================================
# Move objects into collections
# ============================================================

for obj in list(bpy.context.scene.objects):

    if obj.name.startswith("Man") or obj.name.startswith("Woman"):
        for collection in list(obj.users_collection):
            collection.objects.unlink(obj)

        characters_collection.objects.link(obj)

    elif (
        "Table" in obj.name
        or "Chair" in obj.name
        or "Counter" in obj.name
        or "CoffeeMachine" in obj.name
    ):
        for collection in list(obj.users_collection):
            collection.objects.unlink(obj)

        furniture_collection.objects.link(obj)

    elif obj.name in [
        "Floor",
        "BackWall",
        "LeftWall",
        "RightWall",
        "PlantPot",
        "Plant"
    ]:
        for collection in list(obj.users_collection):
            collection.objects.unlink(obj)

        environment_collection.objects.link(obj)


# ============================================================
# Scene Settings
# ============================================================

scene = bpy.context.scene

# Metric units
scene.unit_settings.system = 'METRIC'
scene.unit_settings.length_unit = 'METERS'

# World background
scene.world.color = (0.05, 0.05, 0.05)


# ============================================================
# Select all scene objects
# ============================================================

bpy.ops.object.select_all(action='SELECT')


print("========================================")
print("Minimal Coffee Shop Scene Generated")
print("========================================")
print("Characters:")
print("  Man   -> left")
print("  Woman -> right")
print("  Distance -> approximately 2 meters")
print("")
print("Environment:")
print("  Floor")
print("  Walls")
print("  Tables")
print("  Chairs")
print("  Coffee Counter")
print("")
print("No camera")
print("No lights")
print("No complex models")
print("========================================")