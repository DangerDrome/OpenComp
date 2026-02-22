/* OpenComp — sharpen.frag
   3x3 Laplacian unsharp mask.
   In:  u_image      RGBA32F
   Out: RGBA32F      sharpened
*/

uniform sampler2D u_image;
uniform float     u_amount;
uniform vec2      u_resolution;

in  vec2 v_uv;
out vec4 out_color;

void main() {
    vec2 texel = 1.0 / u_resolution;

    vec4 center = texture(u_image, v_uv);
    vec4 n = texture(u_image, v_uv + vec2(0.0,  texel.y));
    vec4 s = texture(u_image, v_uv + vec2(0.0, -texel.y));
    vec4 e = texture(u_image, v_uv + vec2( texel.x, 0.0));
    vec4 w = texture(u_image, v_uv + vec2(-texel.x, 0.0));

    // Laplacian edge detection
    vec4 edges = center * 4.0 - (n + s + e + w);

    vec3 result = center.rgb + edges.rgb * u_amount;
    out_color = vec4(result, center.a);
}
