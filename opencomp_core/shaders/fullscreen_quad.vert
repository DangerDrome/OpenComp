/* OpenComp — fullscreen_quad.vert
   Shared vertex shader used by all compositor node fragment shaders.
   Renders a fullscreen quad covering the entire output framebuffer.

   v_uv: (0,0) = bottom-left, (1,1) = top-right
   Do NOT modify this file.
*/

in  vec2 position;
out vec2 v_uv;

void main() {
    v_uv        = position * 0.5 + 0.5;
    gl_Position = vec4(position, 0.0, 1.0);
}
