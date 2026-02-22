/* OpenComp — constant.frag
   Solid colour generator. No input image.
   Out: RGBA32F
*/

uniform vec4 u_color;

in  vec2 v_uv;
out vec4 out_color;

void main() {
    out_color = u_color;
}
