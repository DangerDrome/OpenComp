/* OpenComp — passthrough.frag
   Identity passthrough. Copies input to output unchanged.
   Used for testing and as a no-op node placeholder.

   Input:  u_image (RGBA32F linear scene-referred)
   Output: RGBA32F linear scene-referred (identical to input)
*/

uniform sampler2D u_image;

in  vec2 v_uv;
out vec4 out_color;

void main() {
    out_color = texture(u_image, v_uv);
}
