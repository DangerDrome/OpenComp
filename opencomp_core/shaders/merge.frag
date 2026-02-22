/* OpenComp — merge.frag
   Arithmetic blend modes: plus, multiply, screen.
   In:  u_image  RGBA32F input A
        u_bg     RGBA32F input B
   Out: RGBA32F  blended result
*/

uniform sampler2D u_image;
uniform sampler2D u_bg;
uniform float     u_mode;
uniform float     u_mix;

in  vec2 v_uv;
out vec4 out_color;

void main() {
    vec4 a = texture(u_image, v_uv);
    vec4 b = texture(u_bg, v_uv);
    vec4 result;

    if (u_mode < 0.5) {
        // Plus (add)
        result = a + b;
    } else if (u_mode < 1.5) {
        // Multiply
        result = a * b;
    } else {
        // Screen: 1 - (1-a)(1-b)
        result = vec4(1.0) - (vec4(1.0) - a) * (vec4(1.0) - b);
    }

    // Standard alpha composite for the alpha channel
    result.a = a.a + b.a * (1.0 - a.a);

    out_color = mix(b, result, u_mix);
}
