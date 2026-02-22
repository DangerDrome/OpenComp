/* OpenComp — blur_h.frag
   Horizontal gaussian blur pass (separable).
   In:  u_image      RGBA32F
   Out: RGBA32F      horizontally blurred
*/

uniform sampler2D u_image;
uniform float     u_radius;
uniform vec2      u_resolution;

in  vec2 v_uv;
out vec4 out_color;

void main() {
    float step_size = 1.0 / u_resolution.x;
    int radius = int(clamp(u_radius, 0.0, 100.0));

    if (radius == 0) {
        out_color = texture(u_image, v_uv);
        return;
    }

    float sigma = max(u_radius * 0.5, 0.001);
    float inv_2sig2 = 0.5 / (sigma * sigma);

    vec4 sum = vec4(0.0);
    float weight_sum = 0.0;

    for (int i = -radius; i <= radius; i++) {
        float x = float(i);
        float weight = exp(-x * x * inv_2sig2);
        sum += texture(u_image, v_uv + vec2(x * step_size, 0.0)) * weight;
        weight_sum += weight;
    }

    out_color = sum / max(weight_sum, 0.0001);
}
