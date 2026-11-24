"""Build and render the beach scene with Blender, from code only.

Run:
  blender -b -P scene/build.py -- --time sunset --out /path/render.png
  blender -b -P scene/build.py -- --time night  --out /path/render.png

The scene: dunes at sunset, a wooden fence, the sea, a far headland with a
small skyline, and a fogón on the sand.
"""
import argparse
import math
import random
import sys

import bpy
import bmesh
from mathutils import Vector, noise

argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
ap = argparse.ArgumentParser()
ap.add_argument("--time", choices=["sunset", "night"], default="sunset")
ap.add_argument("--out", default="/tmp/render.png")
ap.add_argument("--width", type=int, default=1600)
ap.add_argument("--height", type=int, default=900)
ap.add_argument("--samples", type=int, default=96)
args = ap.parse_args(argv)
NIGHT = args.time == "night"
random.seed(7)

# ---------------------------------------------------------------- reset
bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene


def link(obj):
    scene.collection.objects.link(obj)
    return obj


def mat(name, color, rough=0.8, emit=None, emit_strength=0.0, metallic=0.0, transmission=0.0):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    p = m.node_tree.nodes["Principled BSDF"]
    p.inputs["Base Color"].default_value = (*color, 1)
    p.inputs["Roughness"].default_value = rough
    p.inputs["Metallic"].default_value = metallic
    if transmission:
        p.inputs["Transmission Weight"].default_value = transmission
    if emit:
        p.inputs["Emission Color"].default_value = (*emit, 1)
        p.inputs["Emission Strength"].default_value = emit_strength
    return m


def add_bump(m, kind="noise", scale=5.0, strength=0.2, distance=0.1, wave=False):
    nt = m.node_tree
    p = nt.nodes["Principled BSDF"]
    tc = nt.nodes.new("ShaderNodeTexCoord")
    if wave:
        tex = nt.nodes.new("ShaderNodeTexWave")
        tex.inputs["Scale"].default_value = scale
        tex.inputs["Distortion"].default_value = 11.0
        tex.inputs["Detail"].default_value = 3.0
    else:
        tex = nt.nodes.new("ShaderNodeTexNoise")
        tex.inputs["Scale"].default_value = scale
        tex.inputs["Detail"].default_value = 6.0
    nt.links.new(tc.outputs["Object"], tex.inputs["Vector"])
    bump = nt.nodes.new("ShaderNodeBump")
    bump.inputs["Strength"].default_value = strength
    bump.inputs["Distance"].default_value = distance
    out = tex.outputs["Fac"] if "Fac" in tex.outputs else tex.outputs[0]
    nt.links.new(out, bump.inputs["Height"])
    nt.links.new(bump.outputs["Normal"], p.inputs["Normal"])
    return m


def mesh_obj(name, verts, faces, material=None):
    me = bpy.data.meshes.new(name)
    me.from_pydata(verts, [], faces)
    me.update()
    ob = bpy.data.objects.new(name, me)
    if material:
        ob.data.materials.append(material)
    return link(ob)


def grid(name, x0, x1, y0, y1, nx, ny, height, material=None, smooth=True):
    verts, faces = [], []
    for j in range(ny + 1):
        for i in range(nx + 1):
            x = x0 + (x1 - x0) * i / nx
            y = y0 + (y1 - y0) * j / ny
            verts.append((x, y, height(x, y)))
    for j in range(ny):
        for i in range(nx):
            a = j * (nx + 1) + i
            faces.append((a, a + 1, a + nx + 2, a + nx + 1))
    ob = mesh_obj(name, verts, faces, material)
    if smooth:
        for poly in ob.data.polygons:
            poly.use_smooth = True
    return ob


def box(name, center, size, material, rot_z=0.0, bevel=0.0):
    bpy.ops.mesh.primitive_cube_add(location=center)
    ob = bpy.context.active_object
    ob.name = name
    ob.scale = (size[0] / 2, size[1] / 2, size[2] / 2)
    ob.rotation_euler = (0, 0, rot_z)
    ob.data.materials.append(material)
    if bevel:
        mod = ob.modifiers.new("bevel", "BEVEL")
        mod.width = bevel
        mod.segments = 2
    return ob


# ---------------------------------------------------------------- palette
SAND = mat("sand", (0.86, 0.72, 0.54), rough=0.95)
add_bump(SAND, scale=1.7, strength=0.45, distance=0.06, wave=True)
WET = mat("wet_sand", (0.42, 0.36, 0.30), rough=0.25)
SEA = mat("sea", (0.03, 0.10, 0.13), rough=0.06)
add_bump(SEA, scale=0.8, strength=0.15, distance=0.3)
LAND = mat("headland", (0.035, 0.04, 0.025), rough=1.0)
CITY = mat("skyline", (0.06, 0.055, 0.06), rough=0.9)
WOOD = mat("fence_wood", (0.10, 0.075, 0.055), rough=0.9)
GRASS = mat("grass", (0.32, 0.33, 0.14), rough=0.9, transmission=0.0)
STONE = mat("stone", (0.18, 0.17, 0.16), rough=0.9)
add_bump(STONE, scale=6, strength=0.4)
LOG = mat("log", (0.09, 0.055, 0.035), rough=0.95)
add_bump(LOG, scale=12, strength=0.5)
ASH = mat("ash", (0.08, 0.07, 0.065), rough=1.0)

# ---------------------------------------------------------------- ground
# Camera stands on a dune at z≈0 looking +Y. Beach below, sea beyond.
def dune(x, y):
    z = 0.35 * noise.noise(Vector((x * 0.08, y * 0.08, 0.3)))
    z += 0.08 * noise.noise(Vector((x * 0.4, y * 0.4, 1.7)))
    # The dune drops toward the beach after the fence line.
    fence_y = 9.0 + 0.32 * x
    drop = max(0.0, y - fence_y)
    z -= min(1.6, drop * 0.35)
    return z


grid("dune", -40, 40, -6, 26, 160, 80, dune, SAND)
grid("beach", -400, 400, 14, 70, 60, 20, lambda x, y: -1.62 - 0.01 * (y - 14), SAND)
grid("wet", -400, 400, 58, 80, 20, 4, lambda x, y: -1.74, WET, smooth=False)
grid("sea", -3000, 3000, 70, 4000, 20, 20, lambda x, y: -1.76, SEA, smooth=False)

# ---------------------------------------------------------------- horizon
def headland(x, y):
    base = -1.7
    if y < 950:
        return base - 1
    hump = max(0.0, 1 - abs(x + 150) / 1500)
    return base + 34 * hump ** 0.5 + 4 * noise.noise(Vector((x * 0.015, 0.0, 2.0)))


grid("headland", -2000, 1400, 949, 1020, 200, 4, headland, LAND, smooth=False)

# Skyline behind the sun: one tall tower and lower blocks, as silhouettes.
SX = 60.0  # x of the tower, the sun sits right behind it
TOWER_H = 58
box("tower", (SX, 975, headland(SX, 975) - 2 + TOWER_H / 2), (15, 15, TOWER_H), CITY)
for dx, w, h in [(-140, 30, 18), (-95, 26, 14), (-40, 34, 22), (110, 30, 20), (160, 34, 19), (215, 24, 16)]:
    bx = SX + dx * 0.8
    box(f"block{dx}", (bx, 975, headland(bx, 975) - 2 + h / 2), (w * 0.8, 18, h), CITY)


if NIGHT:
    # Lit windows: a coarse grid of cells, some of them glowing.
    cn = CITY.node_tree
    p = cn.nodes["Principled BSDF"]
    geo = cn.nodes.new("ShaderNodeNewGeometry")
    sc = cn.nodes.new("ShaderNodeVectorMath"); sc.operation = "MULTIPLY"; sc.inputs[1].default_value = (0.75, 0.75, 0.6)
    cn.links.new(geo.outputs["Position"], sc.inputs[0])
    fl = cn.nodes.new("ShaderNodeVectorMath"); fl.operation = "FLOOR"
    cn.links.new(sc.outputs["Vector"], fl.inputs[0])
    wn = cn.nodes.new("ShaderNodeTexWhiteNoise"); wn.noise_dimensions = "3D"
    cn.links.new(fl.outputs["Vector"], wn.inputs["Vector"])
    gt = cn.nodes.new("ShaderNodeMath"); gt.operation = "GREATER_THAN"; gt.inputs[1].default_value = 0.86
    cn.links.new(wn.outputs["Value"], gt.inputs[0])
    st = cn.nodes.new("ShaderNodeMath"); st.operation = "MULTIPLY"; st.inputs[1].default_value = 2.5
    cn.links.new(gt.outputs["Value"], st.inputs[0])
    p.inputs["Emission Color"].default_value = (1.0, 0.72, 0.38, 1)
    cn.links.new(st.outputs["Value"], p.inputs["Emission Strength"])

# ---------------------------------------------------------------- fence
def fence_point(t):
    x = -18 + 40 * t
    y = 9.0 + 0.32 * x
    return x, y


n_posts = 18
for i in range(n_posts + 1):
    x, y = fence_point(i / n_posts)
    z = dune(x, y)
    box(f"post{i}", (x, y, z + 0.45), (0.1, 0.1, 1.0), WOOD, rot_z=random.uniform(-0.05, 0.05))
for k, h in enumerate([0.55, 0.85]):
    for i in range(n_posts):
        x0, y0 = fence_point(i / n_posts)
        x1, y1 = fence_point((i + 1) / n_posts)
        z0, z1 = dune(x0, y0) + h, dune(x1, y1) + h
        dx, dy = x1 - x0, y1 - y0
        length = math.hypot(dx, dy)
        bpy.ops.mesh.primitive_cube_add(location=((x0 + x1) / 2, (y0 + y1) / 2, (z0 + z1) / 2))
        rail = bpy.context.active_object
        rail.scale = (length / 2, 0.025, 0.06)
        rail.rotation_euler = (0, -math.atan2(z1 - z0, length), math.atan2(dy, dx))
        rail.data.materials.append(WOOD)

# ---------------------------------------------------------------- grass
def grass_patch(cx, cy, radius, count):
    verts, faces = [], []
    for _ in range(count):
        a = random.uniform(0, 2 * math.pi)
        r = radius * math.sqrt(random.random())
        x, y = cx + r * math.cos(a), cy + r * math.sin(a)
        z = dune(x, y)
        h = random.uniform(0.25, 0.7)
        lean = Vector((random.uniform(-0.25, 0.25), random.uniform(-0.1, 0.25), 0))
        w = 0.012
        ang = random.uniform(0, math.pi)
        side = Vector((math.cos(ang) * w, math.sin(ang) * w, 0))
        base = Vector((x, y, z - 0.03))
        tip = base + Vector((0, 0, h)) + lean
        i = len(verts)
        verts += [base - side, base + side, tip]
        faces.append((i, i + 1, i + 2))
    mesh_obj("grass", verts, faces, GRASS)


for cx, cy, r, n in [(-12, 6.5, 4, 1600), (-6, 8.3, 3, 900), (4, 10.6, 3.5, 1200), (11, 12.8, 3, 900),
                     (17, 14.5, 4, 1200), (-4.5, 4.6, 1.2, 300), (6.5, 6.0, 1.5, 400)]:
    grass_patch(cx, cy, r, n)


def build_fire(fx, fy, fz):
    """A fire made of glowing volume, plus coals and sparks."""
    m = bpy.data.materials.new("fire_volume")
    m.use_nodes = True
    nt = m.node_tree
    nt.nodes.clear()
    N = nt.nodes.new
    L = nt.links.new
    out = N("ShaderNodeOutputMaterial")
    tc = N("ShaderNodeTexCoord")
    # Turbulence: bend the coordinates with noise, more at the top.
    stretch = N("ShaderNodeVectorMath"); stretch.operation = "MULTIPLY"
    stretch.inputs[1].default_value = (1.0, 1.0, 0.45)
    L(tc.outputs["Object"], stretch.inputs[0])
    n1 = N("ShaderNodeTexNoise"); n1.inputs["Scale"].default_value = 2.2; n1.inputs["Detail"].default_value = 4
    L(stretch.outputs["Vector"], n1.inputs["Vector"])
    centered = N("ShaderNodeVectorMath"); centered.operation = "SUBTRACT"
    centered.inputs[1].default_value = (0.5, 0.5, 0.5)
    L(n1.outputs["Color"], centered.inputs[0])
    amount = N("ShaderNodeVectorMath"); amount.operation = "SCALE"
    amount.inputs["Scale"].default_value = 0.9
    L(centered.outputs["Vector"], amount.inputs[0])
    warped = N("ShaderNodeVectorMath"); warped.operation = "ADD"
    L(tc.outputs["Object"], warped.inputs[0]); L(amount.outputs["Vector"], warped.inputs[1])
    sep = N("ShaderNodeSeparateXYZ"); L(warped.outputs["Vector"], sep.inputs[0])
    sep0 = N("ShaderNodeSeparateXYZ"); L(tc.outputs["Object"], sep0.inputs[0])
    h = N("ShaderNodeMapRange"); h.inputs["From Min"].default_value = -1; h.inputs["From Max"].default_value = 1
    L(sep0.outputs["Z"], h.inputs["Value"])
    xy = N("ShaderNodeCombineXYZ"); L(sep.outputs["X"], xy.inputs["X"]); L(sep.outputs["Y"], xy.inputs["Y"])
    r = N("ShaderNodeVectorMath"); r.operation = "LENGTH"; L(xy.outputs["Vector"], r.inputs[0])
    inv_h = N("ShaderNodeMath"); inv_h.operation = "SUBTRACT"; inv_h.inputs[0].default_value = 1.0
    L(h.outputs["Result"], inv_h.inputs[1])
    width = N("ShaderNodeMath"); width.operation = "POWER"; width.inputs[1].default_value = 0.85
    L(inv_h.outputs["Value"], width.inputs[0])
    ratio = N("ShaderNodeMath"); ratio.operation = "DIVIDE"
    L(r.outputs["Value"], ratio.inputs[0]); L(width.outputs["Value"], ratio.inputs[1])
    mask = N("ShaderNodeMath"); mask.operation = "SUBTRACT"; mask.use_clamp = True
    mask.inputs[0].default_value = 1.0; L(ratio.outputs["Value"], mask.inputs[1])
    mask2 = N("ShaderNodeMath"); mask2.operation = "POWER"; mask2.inputs[1].default_value = 1.6
    L(mask.outputs["Value"], mask2.inputs[0])
    n2 = N("ShaderNodeTexNoise"); n2.inputs["Scale"].default_value = 4.0; n2.inputs["Detail"].default_value = 6
    L(stretch.outputs["Vector"], n2.inputs["Vector"])
    lick = N("ShaderNodeMapRange"); lick.inputs["From Min"].default_value = 0.35; lick.inputs["From Max"].default_value = 0.68
    L(n2.outputs["Fac"], lick.inputs["Value"])
    flame = N("ShaderNodeMath"); flame.operation = "MULTIPLY"
    L(mask2.outputs["Value"], flame.inputs[0]); L(lick.outputs["Result"], flame.inputs[1])
    ramp = N("ShaderNodeValToRGB")
    cr = ramp.color_ramp
    cr.elements[0].position, cr.elements[0].color = 0.0, (0.25, 0.02, 0.0, 1)
    cr.elements[1].position, cr.elements[1].color = 1.0, (1.0, 0.86, 0.55, 1)
    for pos, col in [(0.25, (0.9, 0.18, 0.02)), (0.55, (1.0, 0.45, 0.06)), (0.8, (1.0, 0.68, 0.22))]:
        e = cr.elements.new(pos); e.color = (*col, 1)
    L(flame.outputs["Value"], ramp.inputs["Fac"])
    strength = N("ShaderNodeMath"); strength.operation = "MULTIPLY"; strength.inputs[1].default_value = 60.0
    L(flame.outputs["Value"], strength.inputs[0])
    em = N("ShaderNodeEmission")
    L(ramp.outputs["Color"], em.inputs["Color"]); L(strength.outputs["Value"], em.inputs["Strength"])
    L(em.outputs["Emission"], out.inputs["Volume"])

    bpy.ops.mesh.primitive_cube_add(location=(fx, fy, fz + 0.74))
    dom = bpy.context.active_object
    dom.name = "fire"
    dom.scale = (0.38, 0.38, 0.72)
    dom.data.materials.append(m)

    # Glowing coals in the ash bed.
    coal = bpy.data.materials.new("coals")
    coal.use_nodes = True
    cn = coal.node_tree
    p = cn.nodes["Principled BSDF"]
    p.inputs["Base Color"].default_value = (0.05, 0.04, 0.035, 1)
    p.inputs["Roughness"].default_value = 1
    nz = cn.nodes.new("ShaderNodeTexNoise"); nz.inputs["Scale"].default_value = 18; nz.inputs["Detail"].default_value = 3
    mr = cn.nodes.new("ShaderNodeMapRange"); mr.inputs["From Min"].default_value = 0.5; mr.inputs["From Max"].default_value = 0.68
    cn.links.new(nz.outputs["Fac"], mr.inputs["Value"])
    p.inputs["Emission Color"].default_value = (1.0, 0.25, 0.03, 1)
    sm = cn.nodes.new("ShaderNodeMath"); sm.operation = "MULTIPLY"; sm.inputs[1].default_value = 8
    cn.links.new(mr.outputs["Result"], sm.inputs[0])
    cn.links.new(sm.outputs["Value"], p.inputs["Emission Strength"])
    bpy.ops.mesh.primitive_cylinder_add(radius=0.42, depth=0.06, location=(fx, fy, fz + 0.02))
    bpy.context.active_object.data.materials.append(coal)

    # Sparks drifting up.
    spark = mat("spark", (1, 0.6, 0.2), rough=1, emit=(1.0, 0.45, 0.12), emit_strength=18)
    rng = random.Random(3)
    for _ in range(11):
        z = fz + 1.1 + rng.random() ** 1.8 * 1.8
        drift = (z - fz) * 0.18
        bpy.ops.mesh.primitive_uv_sphere_add(segments=6, ring_count=4, radius=rng.uniform(0.004, 0.008),
                                             location=(fx + rng.uniform(-drift, drift) + drift * 0.5,
                                                       fy + rng.uniform(-drift, drift), z))
        bpy.context.active_object.data.materials.append(spark)

# ---------------------------------------------------------------- fogón
FX, FY = -0.9, 4.3
fz = dune(FX, FY)
for k in range(11):
    a = k / 11 * 2 * math.pi
    bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=2, radius=0.16,
                                          location=(FX + 0.62 * math.cos(a), FY + 0.62 * math.sin(a), fz + 0.03))
    s = bpy.context.active_object
    s.scale = (random.uniform(0.9, 1.3), random.uniform(0.8, 1.1), random.uniform(0.55, 0.75))
    s.rotation_euler = (0, 0, random.uniform(0, 3))
    s.data.materials.append(STONE)
    bpy.ops.object.shade_smooth()
bpy.ops.mesh.primitive_cylinder_add(radius=0.5, depth=0.02, location=(FX, FY, fz + 0.0))
bpy.context.active_object.data.materials.append(ASH)
for k in range(5):
    a = k / 5 * 2 * math.pi + 0.3
    bpy.ops.mesh.primitive_cylinder_add(radius=0.065, depth=0.9,
                                        location=(FX + 0.18 * math.cos(a), FY + 0.18 * math.sin(a), fz + 0.25))
    lg = bpy.context.active_object
    lg.rotation_euler = (0.9 * math.cos(a + math.pi / 2), 0.9 * math.sin(a + math.pi / 2) * -1, 0)
    lg.rotation_euler = (math.radians(55), 0, a + math.pi / 2)
    lg.data.materials.append(LOG)

if NIGHT:
    build_fire(FX, FY, fz)
    bpy.ops.object.light_add(type="POINT", location=(FX, FY, fz + 0.7))
    fire = bpy.context.active_object.data
    fire.energy = 380
    fire.color = (1.0, 0.5, 0.2)
    fire.shadow_soft_size = 0.35

# ---------------------------------------------------------------- sky and sun
SUN_ELEV = math.radians(4.3 if not NIGHT else -12)
SUN_AZ = math.atan2(SX, 975)
MOON_DIR = Vector((math.sin(math.radians(30)) * math.cos(math.radians(8)), math.cos(math.radians(30)) * math.cos(math.radians(8)), math.sin(math.radians(8))))
sun_dir = Vector((math.sin(SUN_AZ) * math.cos(SUN_ELEV), math.cos(SUN_AZ) * math.cos(SUN_ELEV), math.sin(SUN_ELEV)))

bpy.ops.object.light_add(type="SUN")
sun = bpy.context.active_object
sun.rotation_euler = sun_dir.to_track_quat("Z", "Y").to_euler()
if NIGHT:
    # A low moon over the sea, right of the skyline.
    moon = MOON_DIR
    sun.rotation_euler = moon.to_track_quat("Z", "Y").to_euler()
    sun.data.energy = 0.12
    sun.data.color = (0.6, 0.7, 1.0)
else:
    sun.data.energy = 9.0
    sun.data.color = (1.0, 0.62, 0.32)
    sun.data.angle = math.radians(1.5)

world = bpy.data.worlds.new("sky")
scene.world = world
world.use_nodes = True
nt = world.node_tree
nt.nodes.clear()
out = nt.nodes.new("ShaderNodeOutputWorld")
bg = nt.nodes.new("ShaderNodeBackground")
tc = nt.nodes.new("ShaderNodeTexCoord")
norm = nt.nodes.new("ShaderNodeVectorMath")
norm.operation = "NORMALIZE"
nt.links.new(tc.outputs["Generated"], norm.inputs[0])
sep = nt.nodes.new("ShaderNodeSeparateXYZ")
nt.links.new(norm.outputs["Vector"], sep.inputs[0])
ramp = nt.nodes.new("ShaderNodeValToRGB")
mr = nt.nodes.new("ShaderNodeMapRange")
mr.inputs["From Min"].default_value = -0.02
mr.inputs["From Max"].default_value = 0.7
nt.links.new(sep.outputs["Z"], mr.inputs["Value"])
nt.links.new(mr.outputs["Result"], ramp.inputs["Fac"])
cr = ramp.color_ramp
if NIGHT:
    stops = [(0.0, (0.05, 0.05, 0.09)), (0.06, (0.025, 0.03, 0.06)), (0.4, (0.008, 0.012, 0.03)), (1.0, (0.003, 0.005, 0.014))]
else:
    stops = [(0.0, (1.0, 0.42, 0.10)), (0.06, (1.0, 0.62, 0.22)), (0.2, (1.0, 0.80, 0.45)),
             (0.45, (0.45, 0.62, 0.85)), (1.0, (0.12, 0.30, 0.70))]
cr.elements[0].position, cr.elements[0].color = stops[0][0], (*stops[0][1], 1)
cr.elements[1].position, cr.elements[1].color = stops[-1][0], (*stops[-1][1], 1)
for pos, col in stops[1:-1]:
    e = cr.elements.new(pos)
    e.color = (*col, 1)

sky = ramp.outputs["Color"]
if not NIGHT:
    # Glow around the sun and the sun disk itself.
    dot = nt.nodes.new("ShaderNodeVectorMath")
    dot.operation = "DOT_PRODUCT"
    nt.links.new(norm.outputs["Vector"], dot.inputs[0])
    dot.inputs[1].default_value = sun_dir
    glow = nt.nodes.new("ShaderNodeMath")
    glow.operation = "POWER"
    clamp = nt.nodes.new("ShaderNodeMath")
    clamp.operation = "MAXIMUM"
    clamp.inputs[1].default_value = 0.0
    nt.links.new(dot.outputs["Value"], clamp.inputs[0])
    nt.links.new(clamp.outputs["Value"], glow.inputs[0])
    glow.inputs[1].default_value = 22.0
    disk = nt.nodes.new("ShaderNodeMath")
    disk.operation = "GREATER_THAN"
    nt.links.new(dot.outputs["Value"], disk.inputs[0])
    disk.inputs[1].default_value = 0.99985
    total = nt.nodes.new("ShaderNodeMath")
    total.operation = "MULTIPLY_ADD"
    nt.links.new(disk.outputs["Value"], total.inputs[0])
    total.inputs[1].default_value = 30.0
    halo = nt.nodes.new("ShaderNodeMath")
    halo.operation = "POWER"
    nt.links.new(clamp.outputs["Value"], halo.inputs[0])
    halo.inputs[1].default_value = 4.0
    halo_s = nt.nodes.new("ShaderNodeMath")
    halo_s.operation = "MULTIPLY_ADD"
    nt.links.new(halo.outputs["Value"], halo_s.inputs[0])
    halo_s.inputs[1].default_value = 0.55
    nt.links.new(glow.outputs["Value"], halo_s.inputs[2])
    nt.links.new(halo_s.outputs["Value"], total.inputs[2])
    tint = nt.nodes.new("ShaderNodeMix")
    tint.data_type = "RGBA"
    tint.blend_type = "ADD"
    tint.clamp_factor = False
    nt.links.new(total.outputs["Value"], tint.inputs["Factor"])
    nt.links.new(sky, tint.inputs["A"])
    tint.inputs["B"].default_value = (1.0, 0.62, 0.22, 1)
    sky = tint.outputs["Result"]
else:
    # The moon: a disk and a soft halo.
    mdot = nt.nodes.new("ShaderNodeVectorMath")
    mdot.operation = "DOT_PRODUCT"
    nt.links.new(norm.outputs["Vector"], mdot.inputs[0])
    mdot.inputs[1].default_value = MOON_DIR
    mclamp = nt.nodes.new("ShaderNodeMath"); mclamp.operation = "MAXIMUM"; mclamp.inputs[1].default_value = 0
    nt.links.new(mdot.outputs["Value"], mclamp.inputs[0])
    mdisk = nt.nodes.new("ShaderNodeMath"); mdisk.operation = "GREATER_THAN"; mdisk.inputs[1].default_value = 0.99993
    nt.links.new(mdot.outputs["Value"], mdisk.inputs[0])
    mhalo = nt.nodes.new("ShaderNodeMath"); mhalo.operation = "POWER"; mhalo.inputs[1].default_value = 400
    nt.links.new(mclamp.outputs["Value"], mhalo.inputs[0])
    mtot = nt.nodes.new("ShaderNodeMath"); mtot.operation = "MULTIPLY_ADD"; mtot.inputs[1].default_value = 14
    nt.links.new(mdisk.outputs["Value"], mtot.inputs[0])
    mh2 = nt.nodes.new("ShaderNodeMath"); mh2.operation = "MULTIPLY"; mh2.inputs[1].default_value = 0.06
    nt.links.new(mhalo.outputs["Value"], mh2.inputs[0])
    nt.links.new(mh2.outputs["Value"], mtot.inputs[2])
    madd = nt.nodes.new("ShaderNodeMix"); madd.data_type = "RGBA"; madd.blend_type = "ADD"; madd.clamp_factor = False
    nt.links.new(mtot.outputs["Value"], madd.inputs["Factor"])
    nt.links.new(sky, madd.inputs["A"])
    madd.inputs["B"].default_value = (0.85, 0.88, 1.0, 1)
    sky = madd.outputs["Result"]
    # Stars.
    vor = nt.nodes.new("ShaderNodeTexVoronoi")
    vor.inputs["Scale"].default_value = 260
    nt.links.new(norm.outputs["Vector"], vor.inputs["Vector"])
    st = nt.nodes.new("ShaderNodeMapRange")
    st.inputs["From Min"].default_value = 0.0
    st.inputs["From Max"].default_value = 0.07
    st.inputs["To Min"].default_value = 1.0
    st.inputs["To Max"].default_value = 0.0
    nt.links.new(vor.outputs["Distance"], st.inputs["Value"])
    above = nt.nodes.new("ShaderNodeMath")
    above.operation = "GREATER_THAN"
    above.inputs[1].default_value = 0.05
    nt.links.new(sep.outputs["Z"], above.inputs[0])
    mul = nt.nodes.new("ShaderNodeMath")
    mul.operation = "MULTIPLY"
    nt.links.new(st.outputs["Result"], mul.inputs[0])
    nt.links.new(above.outputs["Value"], mul.inputs[1])
    pw = nt.nodes.new("ShaderNodeMath")
    pw.operation = "MULTIPLY"
    pw.inputs[1].default_value = 1.2
    nt.links.new(mul.outputs["Value"], pw.inputs[0])
    add = nt.nodes.new("ShaderNodeMix")
    add.data_type = "RGBA"
    add.blend_type = "ADD"
    add.clamp_factor = False
    nt.links.new(pw.outputs["Value"], add.inputs["Factor"])
    nt.links.new(sky, add.inputs["A"])
    add.inputs["B"].default_value = (0.9, 0.9, 1.0, 1)
    sky = add.outputs["Result"]

nt.links.new(sky, bg.inputs["Color"])
bg.inputs["Strength"].default_value = 0.8 if not NIGHT else 1.0
nt.links.new(bg.outputs["Background"], out.inputs["Surface"])

# ---------------------------------------------------------------- camera
bpy.ops.object.camera_add(location=(0.6, -3.0, dune(0.6, -3.0) + 1.45))
cam = bpy.context.active_object
scene.camera = cam
cam.data.lens = 26
cam.data.clip_end = 20000
target = Vector((0.4, 20, 1.0))
cam.rotation_euler = (target - cam.location).to_track_quat("-Z", "Y").to_euler()

# ---------------------------------------------------------------- render
scene.render.engine = "CYCLES"
prefs = bpy.context.preferences.addons["cycles"].preferences
try:
    prefs.compute_device_type = "METAL"
    prefs.get_devices()
    for d in prefs.devices:
        d.use = True
    scene.cycles.device = "GPU"
except Exception as e:  # CPU is fine too, just slower.
    print("GPU not available:", e)
scene.cycles.samples = args.samples
scene.cycles.use_denoising = True
scene.render.resolution_x = args.width
scene.render.resolution_y = args.height
scene.render.resolution_percentage = 100
scene.view_settings.view_transform = "AgX"
VT = scene.view_settings
try:
    scene.view_settings.look = "AgX - Punchy" if not NIGHT else "AgX - Medium High Contrast"
except TypeError as e:
    print("look:", e)
scene.view_settings.exposure = 0.0 if not NIGHT else 0.6
scene.render.filepath = args.out
scene.render.image_settings.file_format = "PNG"
bpy.ops.render.render(write_still=True)
print("WROTE", args.out)
