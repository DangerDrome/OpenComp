/* OpenComp — transform.frag
   2D affine transform: translate, rotate, scale around center.
   In:  u_image      RGBA32F
   Out: RGBA32F      transformed
*/

uniform sampler2D u_image;
uniform vec2      u_translate;
uniform float     u_rotate;
uniform vec2      u_scale;
uniform vec2      u_center;

in  vec2 v_uv;
out vec4 out_color;

void main() {
    vec2 uv = v_uv - u_center;

    // Inverse scale
    uv /= max(u_scale, vec2(0.0001));

    // Inverse rotate
    float c = cos(-u_rotate);
    float s = sin(-u_rotate);
    uv = vec2(uv.x * c - uv.y * s,
              uv.x * s + uv.y * c);

    // Inverse translate
    uv -= u_translate;

    uv += u_center;

    // Black outside bounds
    if (uv.x < 0.0 || uv.x > 1.0 || uv.y < 0.0 || uv.y > 1.0) {
        out_color = vec4(0.0);
    } else {
        out_color = texture(u_image, uv);
    }
}
