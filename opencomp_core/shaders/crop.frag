/* OpenComp — crop.frag
   Crop — blacks out pixels outside the crop region.
   Crop values are normalised 0-1 UV coordinates.
   In:  u_image  RGBA32F
   Out: RGBA32F  (black outside crop)
*/

uniform sampler2D u_image;
uniform vec4      u_crop;   /* x=left, y=bottom, z=right, w=top */

in  vec2 v_uv;
out vec4 out_color;

void main() {
    if (v_uv.x < u_crop.x || v_uv.x > u_crop.z ||
        v_uv.y < u_crop.y || v_uv.y > u_crop.w) {
        out_color = vec4(0.0);
    } else {
        out_color = texture(u_image, v_uv);
    }
}
