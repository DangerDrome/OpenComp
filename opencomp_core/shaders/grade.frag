/* OpenComp — grade.frag
   Lift / Gamma / Gain colour grade.
   In:  u_image  RGBA32F linear scene-referred
   Out: RGBA32F  linear scene-referred
*/

uniform sampler2D u_image;
uniform vec3      u_lift;
uniform vec3      u_gamma;
uniform vec3      u_gain;
uniform float     u_mix;

in  vec2 v_uv;
out vec4 out_color;

void main() {
    vec4 src = texture(u_image, v_uv);
    vec3 col = src.rgb;

    col = col + u_lift;
    col = pow(max(col, vec3(0.0)), 1.0 / max(u_gamma, vec3(0.0001)));
    col = col * u_gain;
    col = mix(src.rgb, col, u_mix);

    out_color = vec4(col, src.a);
}
