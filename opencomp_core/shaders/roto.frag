/* OpenComp — roto.frag
   Shape mask generator for Roto node.
   Generates ellipse or rectangle masks with feathering.

   Uniforms:
     u_resolution  - Output resolution (width, height)
     u_center      - Shape center (normalized 0-1)
     u_size        - Shape size (normalized)
     u_rotation    - Rotation in radians
     u_feather     - Edge softness
     u_invert      - Invert mask (0.0 or 1.0)
     u_shape_mode  - 0 = ellipse, 1 = rectangle

   Out: RGBA32F - mask value in all channels
*/

uniform vec2  u_resolution;
uniform vec2  u_center;
uniform vec2  u_size;
uniform float u_rotation;
uniform float u_feather;
uniform float u_invert;
uniform float u_shape_mode;

in  vec2 v_uv;
out vec4 out_color;

// Rotate a 2D point around origin
vec2 rotate2d(vec2 p, float angle) {
    float c = cos(angle);
    float s = sin(angle);
    return vec2(p.x * c - p.y * s, p.x * s + p.y * c);
}

// Signed distance to ellipse (approximation)
float sdEllipse(vec2 p, vec2 size) {
    // Normalize by size to get unit circle distance
    vec2 pn = p / size;
    float d = length(pn) - 1.0;
    // Scale back by average size for proper distance
    return d * min(size.x, size.y);
}

// Signed distance to rectangle
float sdBox(vec2 p, vec2 size) {
    vec2 d = abs(p) - size;
    return length(max(d, 0.0)) + min(max(d.x, d.y), 0.0);
}

void main() {
    // Account for aspect ratio
    float aspect = u_resolution.x / u_resolution.y;

    // Transform UV to centered coordinates with aspect correction
    vec2 uv = v_uv;
    uv.x *= aspect;

    vec2 center = u_center;
    center.x *= aspect;

    // Position relative to shape center
    vec2 p = uv - center;

    // Apply rotation
    p = rotate2d(p, -u_rotation);

    // Adjust size for aspect ratio
    vec2 size = u_size;
    size.x *= aspect;

    // Calculate signed distance based on shape mode
    float dist;
    if (u_shape_mode < 0.5) {
        // Ellipse
        dist = sdEllipse(p, size * 0.5);
    } else {
        // Rectangle
        dist = sdBox(p, size * 0.5);
    }

    // Apply feathering
    float feather_size = max(u_feather, 0.001);
    float mask = 1.0 - smoothstep(-feather_size, feather_size, dist);

    // Apply invert
    if (u_invert > 0.5) {
        mask = 1.0 - mask;
    }

    // Output mask in all channels
    out_color = vec4(mask, mask, mask, mask);
}
