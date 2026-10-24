extends CharacterBody3D
## Personnage pixel art (sprite sheet Blender + normal map) se déplaçant sur le plan z = 0.

const SPEED := 3.2
const ACCEL := 30.0
const FRICTION := 36.0
const JUMP := 7.0
const GRAVITY := 18.0
const COYOTE := 0.1
const BUFFER := 0.12

@onready var body: MeshInstance3D = $Sprite
var mat: ShaderMaterial
var anims := {}
var fps := 10.0
var anim := "idle"
var anim_time := 0.0
var facing := 1
var coyote_left := 0.0
var buffer_left := 0.0

func _ready() -> void:
	mat = body.get_surface_override_material(0)
	var meta: Dictionary = JSON.parse_string(FileAccess.get_file_as_string("res://assets/player/sprites.json"))
	anims = meta["animations"]
	fps = meta["fps"]
	mat.set_shader_parameter("hframes", int(meta["columns"]))
	mat.set_shader_parameter("vframes", int(meta["rows"]))

func _physics_process(delta: float) -> void:
	velocity.y -= GRAVITY * delta
	var dir := Input.get_axis("ui_left", "ui_right")
	if dir != 0.0:
		velocity.x = move_toward(velocity.x, dir * SPEED, ACCEL * delta)
		facing = 1 if dir > 0.0 else -1
	else:
		velocity.x = move_toward(velocity.x, 0.0, FRICTION * delta)
	coyote_left = COYOTE if is_on_floor() else coyote_left - delta
	var jump_pressed := Input.is_action_just_pressed("ui_accept") or Input.is_action_just_pressed("ui_up")
	buffer_left = BUFFER if jump_pressed else buffer_left - delta
	if buffer_left > 0.0 and coyote_left > 0.0:
		velocity.y = JUMP
		buffer_left = 0.0
		coyote_left = 0.0
	if velocity.y > 0.0 and not (Input.is_action_pressed("ui_accept") or Input.is_action_pressed("ui_up")):
		velocity.y -= GRAVITY * delta * 1.5
	move_and_slide()
	position.z = 0.0
	_update_animation(delta)

func _update_animation(delta: float) -> void:
	var next := "idle"
	if not is_on_floor():
		next = "jump" if velocity.y > 0.0 else "fall"
	elif absf(velocity.x) > 0.3:
		next = "walk"
	if next != anim:
		anim = next
		anim_time = 0.0
	anim_time += delta
	var a: Dictionary = anims[anim]
	var i := int(anim_time * fps) % int(a["frames"])
	mat.set_shader_parameter("frame", int(a["row"]) * int(mat.get_shader_parameter("hframes")) + i)
	mat.set_shader_parameter("flip", facing < 0)
