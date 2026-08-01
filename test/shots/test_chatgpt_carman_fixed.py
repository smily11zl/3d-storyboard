import bpy
import math

# ============================================================
# Minimal 3D Storyboard Scene
# Scene: A man sitting in the driver's seat looking out
#        of the car window.
#
# No camera
# No lights
# No complex models
#
# Coordinate:
# X = front / back
# Y = left / right
# Z = up
#
# Unit: meter
# ============================================================

# ============================================================
# Clean Scene
# ============================================================

bpy.ops.object.select_all(action='SELECT')
bpy.ops.object.delete(use_global=False)

for datablocks in (
    bpy.data.meshes,
    bpy.data.curves,
    bpy.data.materials,
):
    for datablock in list(datablocks):
        if datablock.users == 0:
            datablocks.remove(datablock)


# ============================================================
# Materials
# ============================================================

def create_material(name, color):
    mat = bpy.data.materials.new(name)
    mat.diffuse_color = (*color, 1.0)
    return mat


MAT_CAR = create_material("Car", (0.25, 0.28, 0.32))
MAT_CAR_WINDOW = create_material("Window", (0.12, 0.18, 0.22))
MAT_MAN = create_material("Man", (0.25, 0.45, 0.8))
MAT_INTERIOR = create_material("Interior", (0.18, 0.18, 0.18))
MAT_GROUND = create_material("Ground", (0.35, 0.35, 0.35))
MAT_ROAD = create_material("Road", (0.12, 0.12, 0.12))


# ============================================================
# Helper Functions
# ============================================================

def create_cube(name, location, dimensions, material=None, rotation=None):
    bpy.ops.mesh.primitive_cube_add(size=1, location=location)

    obj = bpy.context.object
    obj.name = name
    obj.dimensions = dimensions

    if rotation:
        obj.rotation_euler = rotation

    bpy.ops.object.transform_apply(
        location=False,
        rotation=False,
        scale=True
    )

    if material:
        obj.data.materials.append(material)

    return obj


def create_cylinder(
    name,
    location,
    radius,
    depth,
    material=None,
    rotation=None
):
    bpy.ops.mesh.primitive_cylinder_add(
        vertices=16,
        radius=radius,
        depth=depth,
        location=location
    )

    obj = bpy.context.object
    obj.name = name

    if rotation:
        obj.rotation_euler = rotation

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
# Ground / Road
# ============================================================

create_cube(
    "Ground",
    location=(0, 0, -0.05),
    dimensions=(14, 14, 0.1),
    material=MAT_GROUND
)

create_cube(
    "Road",
    location=(0, 0, 0.01),
    dimensions=(14, 5, 0.05),
    material=MAT_ROAD
)


# ============================================================
# Car
# ============================================================

# Main lower body
create_cube(
    "Car_Body",
    location=(0, 0, 0.65),
    dimensions=(4.5, 2.0, 0.8),
    material=MAT_CAR
)

# Front hood
create_cube(
    "Car_Hood",
    location=(1.65, 0, 1.15),
    dimensions=(1.2, 1.9, 0.35),
    material=MAT_CAR
)

# Cabin roof
create_cube(
    "Car_Roof",
    location=(-0.4, 0, 1.9),
    dimensions=(2.5, 1.8, 0.25),
    material=MAT_CAR
)

# Interior floor: makes the driver's position unambiguously inside the car.
create_cube(
    "Car_InteriorFloor",
    location=(-0.45, -0.48, 0.95),
    dimensions=(2.3, 1.5, 0.12),
    material=MAT_INTERIOR
)

# Driver-side door sill, slightly below the window.
create_cube(
    "Driver_DoorSill",
    location=(-0.45, -0.94, 1.05),
    dimensions=(2.2, 0.12, 0.25),
    material=MAT_CAR
)


# ============================================================
# Windows
# ============================================================

create_cube(
    "Driver_Window",
    location=(-0.45, -0.91, 1.72),
    dimensions=(1.45, 0.04, 0.65),
    material=MAT_CAR_WINDOW
)

create_cube(
    "Passenger_Window",
    location=(-0.45, 0.92, 1.75),
    dimensions=(1.5, 0.05, 0.8),
    material=MAT_CAR_WINDOW
)

create_cube(
    "Windshield",
    location=(0.75, 0, 1.7),
    dimensions=(0.05, 1.65, 1.0),
    material=MAT_CAR_WINDOW
)


# ============================================================
# Seats
# ============================================================

def create_seat(name, x, y):
    create_cube(
        f"{name}_Seat",
        location=(x, y, 0.95),
        dimensions=(0.7, 0.7, 0.18),
        material=MAT_INTERIOR
    )

    create_cube(
        f"{name}_Back",
        location=(x - 0.25, y, 1.45),
        dimensions=(0.25, 0.7, 1.0),
        material=MAT_INTERIOR
    )


create_seat("DriverSeat", -0.6, -0.55)
create_seat("PassengerSeat", -0.6, 0.55)


# ============================================================
# Steering Wheel
# ============================================================

bpy.ops.mesh.primitive_torus_add(
    major_radius=0.32,
    minor_radius=0.06,
    major_segments=16,
    minor_segments=8,
    location=(0.25, -0.55, 1.45),
    rotation=(math.pi / 2, 0, 0)
)

steering_wheel = bpy.context.object
steering_wheel.name = "SteeringWheel"
steering_wheel.data.materials.append(MAT_INTERIOR)


# ============================================================
# Dashboard
# ============================================================

create_cube(
    "Dashboard",
    location=(0.55, 0, 1.25),
    dimensions=(0.7, 1.8, 0.35),
    material=MAT_INTERIOR
)


# ============================================================
# Man
# Body = cylinder
# Head = sphere
# Sitting in driver's seat
# Head turned toward driver's window
# ============================================================

def create_man_driver():
    # Driver is physically INSIDE the car cabin.
    # Driver seat center: X=-0.6, Y=-0.55
    # Driver-side window: Y=-0.92
    #
    # The body is positioned between the seat and the window,
    # not outside the car.

    body = create_cylinder(
        "Man_Body",
        location=(-0.60, -0.55, 1.48),
        radius=0.28,
        depth=0.90,
        material=MAT_MAN
    )

    # Head remains inside the cabin, slightly turned toward
    # the driver's side window.
    head = create_sphere(
        "Man_Head",
        location=(-0.48, -0.70, 2.08),
        radius=0.30,
        material=MAT_MAN
    )

    # Simple arms reaching toward the steering wheel.
    arm_1 = create_cylinder(
        "Man_Arm_Left",
        location=(-0.12, -0.55, 1.55),
        radius=0.09,
        depth=0.60,
        material=MAT_MAN,
        rotation=(0, math.radians(65), 0)
    )

    arm_2 = create_cylinder(
        "Man_Arm_Right",
        location=(-0.12, -0.45, 1.55),
        radius=0.09,
        depth=0.60,
        material=MAT_MAN,
        rotation=(0, math.radians(65), 0)
    )

    # Simple legs extending toward the dashboard.
    leg_1 = create_cylinder(
        "Man_Leg_Left",
        location=(-0.05, -0.62, 1.05),
        radius=0.11,
        depth=0.85,
        material=MAT_MAN,
        rotation=(0, math.radians(72), 0)
    )

    leg_2 = create_cylinder(
        "Man_Leg_Right",
        location=(-0.05, -0.48, 1.05),
        radius=0.11,
        depth=0.85,
        material=MAT_MAN,
        rotation=(0, math.radians(72), 0)
    )

    bpy.ops.object.empty_add(
        type='PLAIN_AXES',
        location=(-0.60, -0.55, 1.0)
    )

    root = bpy.context.object
    root.name = "Man_Driver"

    for obj in [
        body,
        head,
        arm_1,
        arm_2,
        leg_1,
        leg_2
    ]:
        obj.parent = root

    return root



create_man_driver()


# ============================================================
# Outside Environment
# Simple cylinders + spheres as trees
# ============================================================

def create_tree(name, x, y, height=3):
    create_cylinder(
        f"{name}_Trunk",
        location=(x, y, height / 2),
        radius=0.15,
        depth=height,
        material=MAT_CAR
    )

    create_sphere(
        f"{name}_Crown",
        location=(x, y, height + 0.7),
        radius=0.7,
        material=MAT_GROUND
    )


create_tree("Tree_01", -2.5, -2.5, 3)
create_tree("Tree_02", 0.0, -3.0, 4)
create_tree("Tree_03", 2.5, -2.5, 3.5)


# ============================================================
# Collections
# ============================================================

def create_collection(name):
    collection = bpy.data.collections.get(name)

    if not collection:
        collection = bpy.data.collections.new(name)
        bpy.context.scene.collection.children.link(collection)

    return collection


characters_collection = create_collection("CHARACTERS")
vehicle_collection = create_collection("VEHICLE")
environment_collection = create_collection("ENVIRONMENT")


# ============================================================
# Organize objects
# ============================================================

for obj in list(bpy.context.scene.objects):

    if obj.name.startswith("Man"):
        for collection in list(obj.users_collection):
            collection.objects.unlink(obj)
        characters_collection.objects.link(obj)

    elif (
        obj.name.startswith("Car")
        or obj.name.startswith("DriverSeat")
        or obj.name.startswith("PassengerSeat")
        or obj.name.startswith("SteeringWheel")
        or obj.name.startswith("Dashboard")
    ):
        for collection in list(obj.users_collection):
            collection.objects.unlink(obj)
        vehicle_collection.objects.link(obj)

    elif (
        obj.name.startswith("Tree")
        or obj.name == "Ground"
        or obj.name == "Road"
    ):
        for collection in list(obj.users_collection):
            collection.objects.unlink(obj)
        environment_collection.objects.link(obj)


# ============================================================
# Scene Settings
# ============================================================

scene = bpy.context.scene

scene.unit_settings.system = 'METRIC'
scene.unit_settings.length_unit = 'METERS'

scene.world.color = (0.05, 0.05, 0.05)


# ============================================================
# Finish
# ============================================================

bpy.ops.object.select_all(action='SELECT')

print("============================================")
print("Minimal Car Driver Scene Generated")
print("============================================")
print("Character:")
print("  - Cylinder body")
print("  - Sphere head")
print("  - Sitting in driver's seat")
print("  - Head turned toward driver's window")
print("")
print("Scene:")
print("  - Simplified car")
print("  - Driver seat")
print("  - Passenger seat")
print("  - Steering wheel")
print("  - Dashboard")
print("  - Driver-side window")
print("  - Road / ground")
print("  - Simple trees")
print("")
print("No camera")
print("No lights")
print("No complex models")
print("============================================")
