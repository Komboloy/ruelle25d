"""
demo_personnage.py — Crée un petit personnage low-poly animé, vu de profil,
prêt à être rendu par render_sprites.py.

    blender -b -P demo_personnage.py -P render_sprites.py -- --out ./sprites

Animations (images) : idle 1-4, walk 11-18, jump 21, fall 22.
Le personnage regarde vers +X ; la caméra orthographique est en -Y.
"""
import bpy, math, json
from mathutils import Matrix

# ---------------------------------------------------------------- scène vide
bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene
scene.frame_start, scene.frame_end = 1, 22

def material(name, rgb):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    m.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = (*rgb, 1)
    return m

def far(rgb, k=0.62):
    return tuple(c * k for c in rgb)

TUNIC, SKIN, PANTS, BOOTS, SCARF, EYE = (
    (0.10, 0.28, 0.55), (0.90, 0.62, 0.45), (0.28, 0.18, 0.12),
    (0.10, 0.06, 0.04), (0.75, 0.10, 0.08), (0.02, 0.02, 0.03))

def finish(obj, mat, smooth=False, bevel=0.0):
    obj.data.materials.append(mat)
    if smooth:
        for p in obj.data.polygons:
            p.use_smooth = True
    if bevel:
        mod = obj.modifiers.new("Bevel", "BEVEL")
        mod.width, mod.segments = bevel, 2
        obj.modifiers.new("WN", "WEIGHTED_NORMAL")
    return obj

def apply_scale(obj):
    obj.data.transform(Matrix.Diagonal((*obj.scale, 1)))
    obj.scale = (1, 1, 1)

def box(name, size, loc, mat, parent=None, bevel=0.03):
    bpy.ops.mesh.primitive_cube_add(size=1, location=loc)
    o = bpy.context.object; o.name = name
    o.scale = size; apply_scale(o)
    o.parent = parent
    return finish(o, mat, bevel=bevel)

def limb(name, radius, length, pivot, mat, parent):
    """Cylindre dont l'origine est en haut (articulation)."""
    bpy.ops.mesh.primitive_cylinder_add(vertices=10, radius=radius, depth=length)
    o = bpy.context.object; o.name = name
    o.data.transform(Matrix.Translation((0, 0, -length / 2)))
    o.location = pivot
    o.parent = parent
    return finish(o, mat, smooth=True)

# ---------------------------------------------------------------- personnage
bpy.ops.object.empty_add(location=(0, 0, 0))
root = bpy.context.object; root.name = "Root"

legs, arms = {}, {}
for side, y, k in (("far", 0.09, 0.62), ("near", -0.09, 1.0)):
    leg = limb(f"Leg_{side}", 0.085, 0.62, (0, y, 0.78), material(f"pants_{side}", far(PANTS, k)), root)
    box(f"Boot_{side}", (0.26, 0.15, 0.16), (0.05, 0, -0.70), material(f"boots_{side}", far(BOOTS, k)), leg)
    legs[side] = leg

torso = box("Torso", (0.40, 0.30, 0.62), (0, 0, 1.08), material("tunic", TUNIC), root, bevel=0.05)
box("Belt", (0.36, 0.32, 0.07), (0, 0, -0.2), material("belt", BOOTS), torso, bevel=0.0)

for side, y, k in (("far", 0.21, 0.62), ("near", -0.21, 1.0)):
    arm = limb(f"Arm_{side}", 0.065, 0.50, (0, y, 0.25), material(f"sleeve_{side}", far(TUNIC, k)), torso)
    bpy.ops.mesh.primitive_uv_sphere_add(segments=10, ring_count=6, radius=0.08, location=(0, 0, -0.52))
    hand = bpy.context.object; hand.name = f"Hand_{side}"; hand.parent = arm
    finish(hand, material(f"skin_{side}", far(SKIN, k)), smooth=True)
    arms[side] = arm

bpy.ops.mesh.primitive_torus_add(major_radius=0.13, minor_radius=0.05, location=(0, 0, 0.33))
scarf = bpy.context.object; scarf.name = "Scarf"; scarf.parent = torso
finish(scarf, material("scarf", SCARF), smooth=True)
box("ScarfTail", (0.16, 0.05, 0.08), (-0.2, -0.13, 0.31), material("scarf2", SCARF), torso, bevel=0.0)

bpy.ops.mesh.primitive_uv_sphere_add(segments=16, ring_count=10, radius=0.24, location=(0.02, 0, 0.62))
head = bpy.context.object; head.name = "Head"; head.parent = torso
finish(head, material("skin", SKIN), smooth=True)
bpy.ops.mesh.primitive_uv_sphere_add(segments=16, ring_count=10, radius=0.26, location=(-0.10, 0, 0.10))
hair = bpy.context.object; hair.name = "Hair"; hair.parent = head
hair.scale = (0.90, 1.05, 0.80); apply_scale(hair)
finish(hair, material("hair", (0.18, 0.08, 0.04)), smooth=True)
box("Eye", (0.05, 0.05, 0.07), (0.15, -0.18, 0.01), material("eye", EYE), head, bevel=0.0)

# ---------------------------------------------------------------- animation
def key(f, root_z=0.0, leg_n=0.0, leg_f=0.0, arm_n=0.0, arm_f=0.0, lean=0.0):
    root.location = (0, 0, root_z); root.keyframe_insert("location", frame=f)
    torso.rotation_euler = (0, lean, 0); torso.keyframe_insert("rotation_euler", frame=f)
    for o, a in ((legs["near"], leg_n), (legs["far"], leg_f), (arms["near"], arm_n), (arms["far"], arm_f)):
        o.rotation_euler = (0, a, 0)
        o.keyframe_insert("rotation_euler", frame=f)

for i in range(4):                       # idle : respiration
    s = math.sin(2 * math.pi * i / 4)
    key(1 + i, root_z=0.015 * s, arm_n=0.06 * s, arm_f=-0.06 * s)
for i in range(8):                       # marche
    p = 2 * math.pi * i / 8
    s = math.sin(p)
    key(11 + i, root_z=0.05 * (1 - abs(s)) - 0.02, leg_n=-0.55 * s, leg_f=0.55 * s,
        arm_n=0.45 * s, arm_f=-0.45 * s, lean=0.08)
key(21, root_z=0.06, leg_n=-0.6, leg_f=0.35, arm_n=2.4, arm_f=-0.6, lean=0.05)   # saut
key(22, leg_n=-0.25, leg_f=0.25, arm_n=1.3, arm_f=1.0, lean=-0.05)               # chute

for o in bpy.data.objects:               # pas d'interpolation entre les poses
    if o.animation_data and o.animation_data.action:
        act = o.animation_data.action
        curves = getattr(act, "fcurves", None)
        if curves is None:               # Blender 5 : actions en couches
            curves = [fc for l in act.layers for s in l.strips for cb in s.channelbags for fc in cb.fcurves]
        for fc in curves:
            for kp in fc.keyframe_points:
                kp.interpolation = "CONSTANT"

# ---------------------------------------------------------------- caméra
cam_data = bpy.data.cameras.new("SpriteCam")
cam_data.type = "ORTHO"
cam_data.ortho_scale = 2.2               # 64 px / 2,2 unités ≈ 29 px par mètre
cam = bpy.data.objects.new("SpriteCam", cam_data)
scene.collection.objects.link(cam)
cam.location = (0, -10, 1.0)
cam.rotation_euler = (math.pi / 2, 0, 0)
scene.camera = cam

scene["sprite_animations"] = json.dumps({"idle": [1, 4], "walk": [11, 18], "jump": [21, 21], "fall": [22, 22]})
print("[demo_personnage] personnage prêt")
