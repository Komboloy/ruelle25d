shader_type spatial;
// Dégradé de ciel crépusculaire, sans éclairage.
render_mode unshaded, cull_disabled;
uniform vec3 top : source_color = vec3(0.02, 0.05, 0.14);
uniform vec3 horizon : source_color = vec3(0.18, 0.32, 0.55);
uniform vec3 glow : source_color = vec3(0.45, 0.3, 0.45);
void fragment() {
	float t = UV.y;
	vec3 c = mix(top, horizon, smoothstep(0.0, 0.85, t));
	c = mix(c, glow, smoothstep(0.75, 1.0, t) * 0.35);
	ALBEDO = c;
}
