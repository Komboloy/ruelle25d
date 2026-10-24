shader_type spatial;
// Sprite pixel art (sprite sheet + normal map) éclairé par les lumières 3D.
render_mode cull_disabled, depth_draw_opaque;

uniform sampler2D albedo_tex : source_color, filter_nearest;
uniform sampler2D normal_tex : hint_normal, filter_nearest;
uniform int hframes = 8;
uniform int vframes = 4;
uniform int frame = 0;
uniform bool flip = false;          // regard vers la gauche
uniform float roughness = 0.75;

void fragment() {
	vec2 uv = UV;
	if (flip) {
		uv.x = 1.0 - uv.x;
	}
	vec2 cell = vec2(float(frame % hframes), float(frame / hframes));
	vec2 suv = (cell + uv) / vec2(float(hframes), float(vframes));
	vec4 c = texture(albedo_tex, suv);
	ALBEDO = c.rgb;
	ALPHA = c.a;
	ALPHA_SCISSOR_THRESHOLD = 0.5;
	vec3 n = texture(normal_tex, suv).rgb;
	if (flip) {
		n.r = 1.0 - n.r;           // le retournement inverse aussi les normales
	}
	NORMAL_MAP = n;
	ROUGHNESS = roughness;
}
