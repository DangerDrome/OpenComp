/* OpenComp — over.frag
   Premultiplied alpha-over compositing.
   In:  u_image  RGBA32F foreground (A)
        u_bg     RGBA32F background (B)
   Out: RGBA32F  A + B * (1 - A.a)
*/

uniform sampler2D u_image;
uniform sampler2D u_bg;
uniform float     u_mix;

in  vec2 v_uv;
out vec4 out_color;

void main() {
    vec4 fg = texture(u_image, v_uv);
    vec4 bg = texture(u_bg, v_uv);

    // Premultiplied alpha over: A + B * (1 - A.a)
    vec4 result = fg + bg * (1.0 - fg.a);

    out_color = mix(bg, result, u_mix);
}
