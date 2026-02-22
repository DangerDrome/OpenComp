/* OpenComp — cdl.frag
   ASC CDL (slope / offset / power) with saturation.
   In:  u_image  RGBA32F linear scene-referred
   Out: RGBA32F  linear scene-referred
*/

uniform sampler2D u_image;
uniform vec3      u_slope;
uniform vec3      u_offset;
uniform vec3      u_power;
uniform float     u_saturation;

in  vec2 v_uv;
out vec4 out_color;

void main() {
    vec4 src = texture(u_image, v_uv);
    vec3 col = src.rgb;

    // ASC CDL: slope, offset, power
    col = pow(max(col * u_slope + u_offset, vec3(0.0)), u_power);

    // Saturation (Rec.709 luminance)
    float luma = dot(col, vec3(0.2126, 0.7152, 0.0722));
    col = vec3(luma) + u_saturation * (col - vec3(luma));

    out_color = vec4(col, src.a);
}
