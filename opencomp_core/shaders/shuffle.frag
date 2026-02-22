/* OpenComp — shuffle.frag
   Channel routing — remap R/G/B/A to any source channel.
   In:  u_image  RGBA32F
   Out: RGBA32F  with channels remapped
   Channel codes: 0=R, 1=G, 2=B, 3=A, 4=black, 5=white
*/

uniform sampler2D u_image;
uniform float     u_r_source;
uniform float     u_g_source;
uniform float     u_b_source;
uniform float     u_a_source;

in  vec2 v_uv;
out vec4 out_color;

float get_channel(vec4 src, float ch) {
    if (ch < 0.5) return src.r;
    if (ch < 1.5) return src.g;
    if (ch < 2.5) return src.b;
    if (ch < 3.5) return src.a;
    if (ch < 4.5) return 0.0;
    return 1.0;
}

void main() {
    vec4 src = texture(u_image, v_uv);
    out_color = vec4(
        get_channel(src, u_r_source),
        get_channel(src, u_g_source),
        get_channel(src, u_b_source),
        get_channel(src, u_a_source)
    );
}
