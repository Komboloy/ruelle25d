"""
render_sprites.py — Rendu de sprites pixel art (couleur + normal map) depuis Blender.

Usage (ligne de commande) :
    blender ma_scene.blend -b -P render_sprites.py -- --out ./sprites
    # ou, avec le personnage de démo :
    blender -b -P demo_personnage.py -P render_sprites.py -- --out ./sprites

Usage (dans Blender) : onglet Scripting → ouvrir ce fichier → Run Script
(les sprites sont alors écrits dans un dossier "sprites" à côté du .blend).

Ce que fait le script :
- utilise la caméra de la scène (orthographique conseillée) ;
- rend chaque animation listée dans ANIMATIONS (ou dans la propriété de scène
  "sprite_animations", au format JSON) ;
- passe 1 : couleur à plat, sans lumière (la Base Color de chaque matériau) ;
- passe 2 : normales en espace caméra (convention OpenGL : vert = haut) ;
- assemble tout dans sprites_diffuse.png + sprites_normal.png (une ligne par
  animation) et écrit sprites.json (nom, ligne, nombre d'images).

Testé avec Blender 5.2 ; n'utilise que des nodes présents depuis Blender 3.x.
"""
import bpy, os, sys, json, tempfile, shutil
import numpy as np

# ---------------------------------------------------------------- réglages
FRAME_SIZE = 64          # taille d'une image (px), carrée
FPS_HINT = 10            # vitesse conseillée, écrite dans sprites.json
ANIMATIONS = {           # nom : (image de début, image de fin) — inclusives
    "idle": (1, 4),
    "walk": (11, 18),
    "jump": (21, 21),
    "fall": (22, 22),
}

# ---------------------------------------------------------------- arguments
def parse_out_dir():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    if "--out" in argv:
        return os.path.abspath(argv[argv.index("--out") + 1])
    base = bpy.path.abspath("//") or os.getcwd()
    return os.path.join(base, "sprites")

scene = bpy.context.scene
anims = ANIMATIONS
if "sprite_animations" in scene:
    anims = {k: tuple(v) for k, v in json.loads(scene["sprite_animations"]).items()}
if scene.camera is None:
    raise RuntimeError("La scène n'a pas de caméra active.")
out_dir = parse_out_dir()
os.makedirs(out_dir, exist_ok=True)

# ---------------------------------------------------------------- rendu
r = scene.render
r.engine = "CYCLES"
scene.cycles.device = "CPU"
scene.cycles.samples = 1                 # 1 échantillon = pixels nets
scene.cycles.use_adaptive_sampling = False
scene.cycles.use_denoising = False
scene.cycles.filter_width = 0.01         # pas d'anti-aliasing
scene.cycles.max_bounces = 0
r.film_transparent = True
r.resolution_x = r.resolution_y = FRAME_SIZE
r.resolution_percentage = 100
r.dither_intensity = 0.0
r.image_settings.file_format = "PNG"
r.image_settings.color_mode = "RGBA"
r.image_settings.color_depth = "8"
cm = scene.view_settings
cm.look = "None"
cm.exposure = 0.0
cm.gamma = 1.0

def render_range(prefix, start, end, tmp):
    paths = []
    for f in range(start, end + 1):
        scene.frame_set(f)
        r.filepath = os.path.join(tmp, f"{prefix}_{f:04d}.png")
        bpy.ops.render.render(write_still=True)
        paths.append(r.filepath)
    return paths

def render_all(prefix, tmp):
    return {name: render_range(f"{prefix}_{name}", a, b, tmp) for name, (a, b) in anims.items()}

# --- matériaux "couleur à plat" : Base Color → Emission
def flat_copy(mat):
    m = mat.copy()
    m.use_nodes = True
    nt = m.node_tree
    out = next((n for n in nt.nodes if n.type == "OUTPUT_MATERIAL"), None) or nt.nodes.new("ShaderNodeOutputMaterial")
    bsdf = next((n for n in nt.nodes if n.type == "BSDF_PRINCIPLED"), None)
    emi = nt.nodes.new("ShaderNodeEmission")
    if bsdf is not None:
        src = bsdf.inputs["Base Color"]
        if src.is_linked:
            nt.links.new(src.links[0].from_socket, emi.inputs["Color"])
        else:
            emi.inputs["Color"].default_value = src.default_value
    else:
        emi.inputs["Color"].default_value = (*mat.diffuse_color[:3], 1)
    nt.links.new(emi.outputs["Emission"], out.inputs["Surface"])
    return m

objs = [o for o in scene.objects if o.type in {"MESH", "CURVE", "SURFACE", "META", "FONT"} and o.visible_get()]
saved, copies = [], {}
for o in objs:
    for i, slot in enumerate(o.material_slots):
        mat = slot.material
        if mat:
            saved.append((o, i, mat, slot.link))
            if mat not in copies:
                copies[mat] = flat_copy(mat)
            slot.link = "OBJECT"                 # n'altère pas le mesh partagé
            slot.material = copies[mat]

# --- matériau "normales caméra"
nmat = bpy.data.materials.new("SPRITE_NORMAL")
nmat.use_nodes = True
nt = nmat.node_tree
nt.nodes.clear()
geo = nt.nodes.new("ShaderNodeNewGeometry")
vt = nt.nodes.new("ShaderNodeVectorTransform")
vt.vector_type, vt.convert_from, vt.convert_to = "NORMAL", "WORLD", "CAMERA"
mul = nt.nodes.new("ShaderNodeVectorMath"); mul.operation = "MULTIPLY_ADD"
mul.inputs[1].default_value = (0.5, 0.5, -0.5)   # Z caméra Blender = vers l'avant → inversé
mul.inputs[2].default_value = (0.5, 0.5, 0.5)
emi = nt.nodes.new("ShaderNodeEmission")
outn = nt.nodes.new("ShaderNodeOutputMaterial")
nt.links.new(geo.outputs["Normal"], vt.inputs[0])
nt.links.new(vt.outputs[0], mul.inputs[0])
nt.links.new(mul.outputs[0], emi.inputs["Color"])
nt.links.new(emi.outputs[0], outn.inputs["Surface"])

tmp = tempfile.mkdtemp(prefix="sprites_")
view_layer = bpy.context.view_layer
old_vt = cm.view_transform
try:
    cm.view_transform = "Standard"           # couleurs telles que peintes
    diffuse = render_all("diffuse", tmp)
    view_layer.material_override = nmat
    cm.view_transform = "Raw"                # valeurs brutes : indispensable pour une normal map
    normal = render_all("normal", tmp)
finally:
    view_layer.material_override = None
    cm.view_transform = old_vt
    for o, i, m, link in saved:
        o.material_slots[i].material = None
        o.material_slots[i].link = link
        o.material_slots[i].material = m
    for c in copies.values():
        bpy.data.materials.remove(c)
    bpy.data.materials.remove(nmat)

# ---------------------------------------------------------------- assemblage
def load_px(path):
    img = bpy.data.images.load(path)
    w, h = img.size
    a = np.empty(w * h * 4, np.float32)
    img.pixels.foreach_get(a)
    bpy.data.images.remove(img)
    return a.reshape(h, w, 4)[::-1]          # Blender stocke de bas en haut

def build_sheet(frames_by_anim, name):
    cols = max(len(v) for v in frames_by_anim.values())
    rows = len(frames_by_anim)
    S = FRAME_SIZE
    sheet = np.zeros((rows * S, cols * S, 4), np.float32)
    for row, paths in enumerate(frames_by_anim.values()):
        for col, p in enumerate(paths):
            sheet[row * S:(row + 1) * S, col * S:(col + 1) * S] = load_px(p)
    img = bpy.data.images.new(name, cols * S, rows * S, alpha=True)
    img.colorspace_settings.name = "Non-Color"   # pas de conversion à l'écriture
    img.pixels.foreach_set(sheet[::-1].ravel())
    img.filepath_raw = os.path.join(out_dir, f"{name}.png")
    img.file_format = "PNG"
    img.save()
    bpy.data.images.remove(img)
    return cols, rows

cols, rows = build_sheet(diffuse, "sprites_diffuse")
build_sheet(normal, "sprites_normal")
meta = {
    "frame_size": FRAME_SIZE, "columns": cols, "rows": rows, "fps": FPS_HINT,
    "animations": {name: {"row": i, "frames": len(v)} for i, (name, v) in enumerate(diffuse.items())},
}
with open(os.path.join(out_dir, "sprites.json"), "w") as f:
    json.dump(meta, f, indent=2)
shutil.rmtree(tmp, ignore_errors=True)
print(f"[render_sprites] {cols}x{rows} images → {out_dir}")
