/* OpenComp — viewer_display.frag
   Display shader for the viewer with gain, gamma, channel isolation,
   false colour, clipping indicators, zoom, pan, ROI overlay, and LUT.

   In:  u_image  RGBA32F from node graph output (linear scene-referred)
   Out: display-ready RGBA (viewer only — not pipeline)
*/

uniform sampler2D u_image;
uniform float     u_gain;
uniform float     u_gamma;
uniform float     u_channel;
uniform float     u_false_color;
uniform float     u_clipping;
uniform float     u_zoom;
uniform vec2      u_pan;
uniform float     u_roi_enabled;
uniform vec4      u_roi;
uniform vec2      u_resolution;
uniform vec2      u_image_resolution;
uniform float     u_bg_mode;
uniform vec3      u_bg_color;
uniform float     u_lut_mode;  /* 0=sRGB, 1=Linear, 2=AgX, 3=Filmic */

in  vec2 v_uv;
out vec4 out_color;

const vec3 LUMA_COEFF = vec3(0.2126, 0.7152, 0.0722);

/* ─── View Transform Functions ─────────────────────────────────────────── */

/* sRGB OETF (linear to sRGB gamma) */
vec3 linear_to_srgb(vec3 c) {
    vec3 lo = c * 12.92;
    vec3 hi = 1.055 * pow(max(c, vec3(0.0)), vec3(1.0/2.4)) - 0.055;
    return mix(lo, hi, step(vec3(0.0031308), c));
}

/* AgX tone mapping (simplified) — attempt to match Blender's AgX */
vec3 agx_tonemap(vec3 c) {
    /* AgX log encoding */
    const float agx_min = -10.0;
    const float agx_max = 6.5;
    c = max(c, vec3(1e-10));
    c = log2(c);
    c = (c - agx_min) / (agx_max - agx_min);
    c = clamp(c, 0.0, 1.0);

    /* AgX sigmoid curve approximation */
    vec3 x = c;
    vec3 x2 = x * x;
    vec3 x4 = x2 * x2;
    c = 15.5 * x4 * x2 - 40.14 * x4 * x + 31.96 * x4 - 6.868 * x2 * x + 0.4298 * x2 + 0.1191 * x - 0.00232;

    return clamp(c, 0.0, 1.0);
}

/* Filmic tone mapping (attempt to match Blender's Filmic) */
vec3 filmic_tonemap(vec3 c) {
    /* Attempt to match Blender Filmic's contrast curve */
    c = max(c, vec3(0.0));

    /* Log encoding similar to Filmic */
    c = log2(c + 0.001) / 10.0 + 0.5;
    c = clamp(c, 0.0, 1.0);

    /* S-curve contrast */
    c = c * c * (3.0 - 2.0 * c);

    return c;
}

/* Apply view transform based on u_lut_mode */
vec3 apply_view_transform(vec3 linear_col) {
    if (u_lut_mode < 0.5) {
        /* sRGB (Standard) */
        return linear_to_srgb(linear_col);
    } else if (u_lut_mode < 1.5) {
        /* Linear (Raw) — no transform, just clamp */
        return clamp(linear_col, 0.0, 1.0);
    } else if (u_lut_mode < 2.5) {
        /* AgX */
        vec3 tonemapped = agx_tonemap(linear_col);
        return linear_to_srgb(tonemapped);
    } else {
        /* Filmic */
        vec3 tonemapped = filmic_tonemap(linear_col);
        return linear_to_srgb(tonemapped);
    }
}

vec3 false_color_map(float luma) {
    if (luma < 0.0)    return vec3(0.0, 0.0, 0.8);
    if (luma < 0.01)   return vec3(0.15, 0.0, 0.3);
    if (luma < 0.18)   return vec3(0.0, 0.4, 0.0);
    if (luma < 0.45)   return vec3(0.3, 0.65, 0.3);
    if (luma < 0.55)   return vec3(0.5, 0.5, 0.5);
    if (luma < 0.7)    return vec3(0.9, 0.85, 0.0);
    if (luma < 0.9)    return vec3(1.0, 0.5, 0.0);
    if (luma < 1.0)    return vec3(0.9, 0.0, 0.0);
    return vec3(1.0, 0.0, 1.0);
}

void main() {
    /* Flip Y — GPU textures are bottom-up, images are top-down */
    vec2 vp_uv = vec2(v_uv.x, 1.0 - v_uv.y);

    /* Aspect-ratio correction: fit image inside viewport */
    float img_aspect = u_image_resolution.x / max(u_image_resolution.y, 1.0);
    float vp_aspect  = u_resolution.x / max(u_resolution.y, 1.0);
    vec2 scale = (vp_aspect > img_aspect)
        ? vec2(img_aspect / vp_aspect, 1.0)   /* pillarbox */
        : vec2(1.0, vp_aspect / img_aspect);   /* letterbox */

    /* Zoom + pan: transform viewport UV to image UV */
    vec2 uv = (vp_uv - 0.5) / (scale * u_zoom) + 0.5 - u_pan;

    /* Out-of-bounds → configurable background */
    if (uv.x < 0.0 || uv.x > 1.0 || uv.y < 0.0 || uv.y > 1.0) {
        vec3 bg;
        if (u_bg_mode < 0.5) {
            bg = vec3(0.0);                           /* BLACK */
        } else if (u_bg_mode < 1.5) {
            bg = vec3(0.18);                          /* GREY  */
        } else if (u_bg_mode < 2.5) {
            /* CHECKER — 8px tiles alternating two greys */
            float check = mod(floor(gl_FragCoord.x / 8.0) + floor(gl_FragCoord.y / 8.0), 2.0);
            bg = mix(vec3(0.15), vec3(0.25), check);
        } else {
            bg = u_bg_color;                          /* CUSTOM */
        }
        out_color = vec4(bg, 1.0);
        return;
    }

    vec4 src = texture(u_image, uv);
    vec3 col = src.rgb;

    /* Gain (linear exposure multiplier) — applied in linear space */
    col *= u_gain;

    /* Store linear values for clipping detection */
    vec3 linear_col = col;

    /* Channel isolation (before view transform for proper linear handling) */
    bool single_channel = false;
    if (u_channel > 0.5 && u_channel < 1.5) {
        col = vec3(col.r);
        single_channel = true;
    } else if (u_channel > 1.5 && u_channel < 2.5) {
        col = vec3(col.g);
        single_channel = true;
    } else if (u_channel > 2.5 && u_channel < 3.5) {
        col = vec3(col.b);
        single_channel = true;
    } else if (u_channel > 3.5 && u_channel < 4.5) {
        col = vec3(src.a);
        single_channel = true;
    } else if (u_channel > 4.5) {
        float lum = dot(linear_col, LUMA_COEFF);
        col = vec3(lum);
        single_channel = true;
    }

    /* Apply view transform (LUT) */
    col = apply_view_transform(col);

    /* Additional gamma adjustment on top of view transform */
    if (abs(u_gamma - 1.0) > 0.001) {
        col = pow(max(col, vec3(0.0)), vec3(1.0 / max(u_gamma, 0.0001)));
    }

    /* False colour — overrides channel isolation, works in linear space */
    if (u_false_color > 0.5) {
        float luma = dot(src.rgb * u_gain, LUMA_COEFF);
        col = false_color_map(luma);
    }

    /* Clipping indicators: red = over white, blue = under black */
    if (u_clipping > 0.5) {
        if (linear_col.r > 1.0 || linear_col.g > 1.0 || linear_col.b > 1.0)
            col = mix(col, vec3(1.0, 0.0, 0.0), 0.7);
        if (linear_col.r < 0.0 || linear_col.g < 0.0 || linear_col.b < 0.0)
            col = mix(col, vec3(0.0, 0.0, 1.0), 0.7);
    }

    /* ROI overlay — operates in viewport space (v_uv) */
    if (u_roi_enabled > 0.5) {
        vec2 roi_min = u_roi.xy;
        vec2 roi_max = u_roi.zw;
        bool inside = v_uv.x >= roi_min.x && v_uv.x <= roi_max.x &&
                      v_uv.y >= roi_min.y && v_uv.y <= roi_max.y;
        if (!inside) col *= 0.3;

        float bw = 2.0 / min(u_resolution.x, u_resolution.y);
        bool on_h = (abs(v_uv.x - roi_min.x) < bw || abs(v_uv.x - roi_max.x) < bw) &&
                    v_uv.y >= roi_min.y && v_uv.y <= roi_max.y;
        bool on_v = (abs(v_uv.y - roi_min.y) < bw || abs(v_uv.y - roi_max.y) < bw) &&
                    v_uv.x >= roi_min.x && v_uv.x <= roi_max.x;
        if (on_h || on_v) col = vec3(1.0, 1.0, 0.0);
    }

    out_color = vec4(col, 1.0);
}
