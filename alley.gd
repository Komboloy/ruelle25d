extends Node3D
## Ruelle 2.5D : des plans en pixel art placés en profondeur dans une scène 3D.
## Tout l'éclairage et l'atmosphère viennent du moteur 3D de Godot :
## brouillard volumétrique (faisceaux), bloom, profondeur de champ, reflets (SSR), pluie.
##
## Touches de diagnostic : 1 brouillard  2 bloom  3 profondeur de champ  4 reflets  5 pluie  F1 infos

const ENV_DIR := "res://assets/env/"
const CAM_DISTANCE := 15.75      # distance caméra → plan de jeu
const CAM_HEIGHT := 4.4
const LEVEL_MIN_X := 0.0
const LEVEL_MAX_X := 40.0

@onready var player: CharacterBody3D = $Player
@onready var info: Label = $UI/Info

var env: Environment
var cam: Camera3D
var cam_attr: CameraAttributesPractical
var rain: GPUParticles3D
var neon_lights: Array[OmniLight3D] = []
var t := 0.0

func _ready() -> void:
	var meta: Dictionary = JSON.parse_string(FileAccess.get_file_as_string(ENV_DIR + "layers.json"))
	_build_environment()
	_build_camera()
	_build_sky()
	for layer in meta["layers"]:
		_add_layer(layer)
	_build_floor()
	# lumières, portes et fenêtres décrites par le mur peint (tools/paint_wall.py)
	var wall: Dictionary = JSON.parse_string(FileAccess.get_file_as_string(ENV_DIR + "wall_lights.json"))
	for door in wall["doors"]:
		_add_door(door[0], door[1])
	for win in wall["windows"]:
		_add_window_beam(win[0], win[1])
	for l in wall["lights"]:
		_add_neon(Vector3(l["x"], l["y"], l["z"]), Color(l["color"][0], l["color"][1], l["color"][2]), l["energy"], l["range"], l["flicker"])
	_build_lights()
	_build_props()
	_build_rain()
	player.position = Vector3(3.0, 0.0, 0.0)
	_refresh_info()

# ------------------------------------------------------------------ environnement
func _build_environment() -> void:
	env = Environment.new()
	env.background_mode = Environment.BG_COLOR
	env.background_color = Color(0.02, 0.03, 0.07)
	env.ambient_light_source = Environment.AMBIENT_SOURCE_COLOR
	env.ambient_light_color = Color(0.25, 0.35, 0.6)
	env.ambient_light_energy = 0.35
	env.tonemap_mode = Environment.TONE_MAPPER_ACES
	env.tonemap_exposure = 0.95
	# bloom : les néons "bavent"
	env.glow_enabled = true
	env.glow_intensity = 0.9
	env.glow_strength = 1.1
	env.glow_bloom = 0.04
	env.glow_hdr_threshold = 0.85
	env.glow_blend_mode = Environment.GLOW_BLEND_MODE_SCREEN
	for i in 7:
		env.set_glow_level(i, i >= 2 and i <= 5)
	# brume de distance (plans lointains bleutés)
	env.fog_enabled = true
	env.fog_light_color = Color(0.16, 0.26, 0.46)
	env.fog_light_energy = 1.0
	env.fog_density = 0.014
	env.fog_sky_affect = 0.6
	# brouillard volumétrique : rend les faisceaux de lumière visibles
	env.volumetric_fog_enabled = true
	env.volumetric_fog_density = 0.035
	env.volumetric_fog_albedo = Color(0.75, 0.8, 0.95)
	env.volumetric_fog_emission = Color(0.002, 0.004, 0.01)
	env.volumetric_fog_anisotropy = 0.55
	env.volumetric_fog_length = 32.0
	env.volumetric_fog_ambient_inject = 0.0
	# reflets sur le sol mouillé
	env.ssr_enabled = true
	env.ssr_max_steps = 96
	env.ssr_depth_tolerance = 0.5
	env.ssr_fade_in = 0.15
	env.ssr_fade_out = 2.0
	# étalonnage
	env.adjustment_enabled = true
	env.adjustment_contrast = 1.12
	env.adjustment_saturation = 1.2
	var we := WorldEnvironment.new()
	we.environment = env
	add_child(we)

func _build_camera() -> void:
	cam = Camera3D.new()
	cam.fov = 32.0
	cam.near = 0.1
	cam.far = 200.0
	cam_attr = CameraAttributesPractical.new()
	cam_attr.dof_blur_far_enabled = true
	cam_attr.dof_blur_far_distance = 30.0
	cam_attr.dof_blur_far_transition = 28.0
	cam_attr.dof_blur_near_enabled = true
	cam_attr.dof_blur_near_distance = 12.5
	cam_attr.dof_blur_near_transition = 2.5
	cam_attr.dof_blur_amount = 0.09
	cam.attributes = cam_attr
	cam.position = Vector3(7.5, CAM_HEIGHT, CAM_DISTANCE)
	cam.rotation_degrees.x = -5.0      # légère plongée : plus de sol mouillé visible
	add_child(cam)
	cam.make_current()

func _build_sky() -> void:
	var q := MeshInstance3D.new()
	var m := QuadMesh.new()
	m.size = Vector2(260, 80)
	q.mesh = m
	var sm := ShaderMaterial.new()
	sm.shader = load("res://sky.gdshader")
	q.material_override = sm
	q.position = Vector3(20, 22, -95)
	q.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	add_child(q)

# ------------------------------------------------------------------ plans pixel art
func _add_layer(l: Dictionary) -> void:
	var q := MeshInstance3D.new()
	var m := QuadMesh.new()
	m.size = Vector2(l["w"], l["h"])
	q.mesh = m
	var mat := StandardMaterial3D.new()
	mat.albedo_texture = load(ENV_DIR + l["name"] + ".png")
	mat.texture_filter = BaseMaterial3D.TEXTURE_FILTER_NEAREST
	mat.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA_SCISSOR
	mat.alpha_scissor_threshold = 0.5
	mat.roughness = 0.95
	if l["emissive"]:
		mat.emission_enabled = true
		mat.emission_texture = load(ENV_DIR + l["name"] + "_emit.png")
		mat.emission = Color.BLACK
		mat.emission_energy_multiplier = l["emit_energy"]
		mat.emission_operator = BaseMaterial3D.EMISSION_OP_ADD
	if l["normal"]:
		mat.normal_enabled = true
		mat.normal_texture = load(ENV_DIR + l["name"] + "_normal.png")
		mat.normal_scale = 1.5
	q.material_override = mat
	q.position = Vector3(l["x"] + l["w"] / 2.0, l["y"] + l["h"] / 2.0, l["z"])
	q.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_ON if l["cast_shadow"] else GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	add_child(q)

func _build_floor() -> void:
	var floor_body := StaticBody3D.new()
	var shape := CollisionShape3D.new()
	var box := BoxShape3D.new()
	box.size = Vector3(60, 1, 12)
	shape.shape = box
	floor_body.add_child(shape)
	var mi := MeshInstance3D.new()
	var bm := BoxMesh.new()
	bm.size = box.size
	mi.mesh = bm
	var mat := StandardMaterial3D.new()
	mat.albedo_texture = load(ENV_DIR + "floor.png")
	mat.roughness_texture = load(ENV_DIR + "floor_rough.png")
	mat.roughness = 1.0
	mat.metallic_specular = 1.0
	mat.texture_filter = BaseMaterial3D.TEXTURE_FILTER_NEAREST
	mat.uv1_triplanar = true
	mat.uv1_scale = Vector3(0.5, 0.5, 0.5)
	mi.material_override = mat
	floor_body.add_child(mi)
	floor_body.position = Vector3(18, -0.5, 2.5)
	add_child(floor_body)
	# murs invisibles aux extrémités
	for x in [LEVEL_MIN_X - 0.5, LEVEL_MAX_X + 0.5]:
		var wall := StaticBody3D.new()
		var ws := CollisionShape3D.new()
		var wb := BoxShape3D.new()
		wb.size = Vector3(1, 20, 4)
		ws.shape = wb
		wall.add_child(ws)
		wall.position = Vector3(x, 10, 0)
		add_child(wall)

# ------------------------------------------------------------------ lumières
func _add_door(x: float, h: float) -> void:
	# intérieur chaud derrière l'ouverture
	var q := MeshInstance3D.new()
	var m := QuadMesh.new()
	m.size = Vector2(2.2, h + 0.6)
	q.mesh = m
	var mat := StandardMaterial3D.new()
	mat.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
	mat.albedo_color = Color(1.0, 0.55, 0.22) * 0.9
	q.material_override = mat
	q.position = Vector3(x, (h + 0.6) / 2.0, -3.4)
	add_child(q)
	# faisceau qui sort de la porte
	var s := SpotLight3D.new()
	s.light_color = Color(1.0, 0.66, 0.32)
	s.light_energy = 4.0
	s.spot_range = 13.0
	s.spot_angle = 42.0
	s.spot_attenuation = 0.8
	s.light_volumetric_fog_energy = 1.1
	s.shadow_enabled = true
	add_child(s)
	s.position = Vector3(x, h * 0.85, -3.3)
	s.look_at(Vector3(x + 1.2, 0.0, 0.8), Vector3.UP)

## Faisceau sortant d'une fenêtre éclairée : un projecteur "barreaux" découpe la lumière
## dans le brouillard (technique du gobo, comme au théâtre).
func _add_window_beam(x: float, y: float) -> void:
	var s := SpotLight3D.new()
	s.light_color = Color(1.0, 0.72, 0.42)
	s.light_energy = 5.0
	s.spot_range = 9.0
	s.spot_angle = 28.0
	s.light_projector = load(ENV_DIR + "window_gobo.png")
	s.light_volumetric_fog_energy = 5.0
	add_child(s)
	s.position = Vector3(x, y + 0.2, -2.45)
	s.look_at(Vector3(x + 1.2, 0.0, 2.0), Vector3.UP)

func _build_lights() -> void:
	# lune : lumière froide et faible
	var moon := DirectionalLight3D.new()
	moon.light_color = Color(0.45, 0.6, 1.0)
	moon.light_energy = 0.18
	moon.light_volumetric_fog_energy = 0.6
	moon.rotation_degrees = Vector3(-35, 30, 0)
	add_child(moon)
	# réverbère : cône blanc-jaune vers le sol
	for x in [20.5, 38.0]:
		var lamp := SpotLight3D.new()
		lamp.light_color = Color(1.0, 0.9, 0.7)
		lamp.light_energy = 9.0
		lamp.spot_range = 10.0
		lamp.spot_angle = 32.0
		lamp.light_volumetric_fog_energy = 4.0
		lamp.shadow_enabled = true
		add_child(lamp)
		lamp.position = Vector3(x, 4.2, -1.6)
		lamp.look_at(Vector3(x + 0.3, 0, 0.5), Vector3.UP)
		var bulb := MeshInstance3D.new()
		var bm := BoxMesh.new()
		bm.size = Vector3(0.5, 0.12, 0.3)
		bulb.mesh = bm
		var mat := StandardMaterial3D.new()
		mat.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
		mat.albedo_color = Color(1.0, 0.95, 0.8) * 3.0
		bulb.material_override = mat
		bulb.position = Vector3(x, 4.35, -1.6)
		add_child(bulb)

func _add_neon(p: Vector3, c: Color, energy: float, rng: float, flicker := false) -> void:
	var o := OmniLight3D.new()
	o.light_color = c
	o.light_energy = energy
	o.omni_range = rng
	o.light_volumetric_fog_energy = 0.6
	o.position = p
	add_child(o)
	o.set_meta("base", energy)
	if flicker:
		neon_lights.append(o)

# ------------------------------------------------------------------ décor jouable
func _build_props() -> void:
	var crate_mat := StandardMaterial3D.new()
	crate_mat.albedo_texture = load(ENV_DIR + "crate.png")
	crate_mat.normal_enabled = true
	crate_mat.normal_texture = load(ENV_DIR + "crate_normal.png")
	crate_mat.texture_filter = BaseMaterial3D.TEXTURE_FILTER_NEAREST
	crate_mat.roughness = 0.85
	# (x, y, taille) — empilements à escalader
	for c in [[15.6, 0.0, 1.0], [16.6, 0.0, 1.0], [16.1, 1.0, 1.0], [22.6, 0.0, 1.2], [23.8, 0.0, 1.2], [34.6, 0.0, 1.0]]:
		var body := StaticBody3D.new()
		var s := CollisionShape3D.new()
		var b := BoxShape3D.new()
		b.size = Vector3(c[2], c[2], 1.2)
		s.shape = b
		body.add_child(s)
		var mi := MeshInstance3D.new()
		var bm := BoxMesh.new()
		bm.size = b.size
		mi.mesh = bm
		mi.material_override = crate_mat
		body.add_child(mi)
		body.position = Vector3(c[0], c[1] + c[2] / 2.0, -0.3)   # traverse le plan z = 0 : collision avec le joueur
		add_child(body)

func _build_rain() -> void:
	rain = GPUParticles3D.new()
	rain.amount = 1200
	rain.lifetime = 0.9
	rain.visibility_aabb = AABB(Vector3(-14, -14, -8), Vector3(28, 18, 16))
	var pm := ParticleProcessMaterial.new()
	pm.emission_shape = ParticleProcessMaterial.EMISSION_SHAPE_BOX
	pm.emission_box_extents = Vector3(13, 0.5, 7)
	pm.direction = Vector3(0.12, -1, 0)
	pm.spread = 2.0
	pm.initial_velocity_min = 15.0
	pm.initial_velocity_max = 19.0
	pm.gravity = Vector3.ZERO
	rain.process_material = pm
	var drop := QuadMesh.new()
	drop.size = Vector2(0.015, 0.4)
	var dm := StandardMaterial3D.new()
	dm.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
	dm.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA
	dm.albedo_color = Color(0.75, 0.85, 1.0, 0.14)
	dm.billboard_mode = BaseMaterial3D.BILLBOARD_FIXED_Y
	drop.material = dm
	rain.draw_pass_1 = drop
	rain.position = Vector3(7.5, 10, 1.5)
	add_child(rain)

# ------------------------------------------------------------------ boucle
func _process(delta: float) -> void:
	t += delta
	var target_x := clampf(player.position.x, 7.5, LEVEL_MAX_X - 7.5)
	cam.position.x = lerpf(cam.position.x, target_x, 1.0 - exp(-delta * 4.0))
	rain.position.x = cam.position.x
	# grésillement des néons
	for i in neon_lights.size():
		var n := neon_lights[i]
		var base: float = n.get_meta("base")
		var flick := 1.0
		if fmod(t * (1.3 + i * 0.7), 7.0) < 0.12:
			flick = 0.25
		n.light_energy = base * flick
	if Engine.get_process_frames() % 20 == 0:
		_refresh_info()

func _unhandled_input(event: InputEvent) -> void:
	if not (event is InputEventKey and event.pressed and not event.echo):
		return
	match event.keycode:
		KEY_1: env.volumetric_fog_enabled = not env.volumetric_fog_enabled
		KEY_2: env.glow_enabled = not env.glow_enabled
		KEY_3:
			var on := not cam_attr.dof_blur_far_enabled
			cam_attr.dof_blur_far_enabled = on
			cam_attr.dof_blur_near_enabled = on
		KEY_4: env.ssr_enabled = not env.ssr_enabled
		KEY_5: rain.emitting = not rain.emitting
		KEY_F1: info.visible = not info.visible
	_refresh_info()

func _refresh_info() -> void:
	info.text = "%d FPS   1 brouillard:%s  2 bloom:%s  3 DOF:%s  4 reflets:%s  5 pluie:%s" % [
		Engine.get_frames_per_second(),
		_on(env.volumetric_fog_enabled), _on(env.glow_enabled), _on(cam_attr.dof_blur_far_enabled),
		_on(env.ssr_enabled), _on(rain.emitting)]

func _on(b: bool) -> String:
	return "on" if b else "off"
