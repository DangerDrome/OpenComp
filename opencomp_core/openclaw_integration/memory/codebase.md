# OpenComp Codebase — OpenClaw Agent Memory

Read this before writing any node code.

## What OpenComp Is

Open source Nuke-like compositor. Blender 5.x add-on. Python + GLSL only.
Blender = infrastructure only. Custom GPU compositor built on top.

## Key Directories

- opencomp_core/nodes/      — compositor node implementations (you write here)
- opencomp_core/shaders/    — GLSL fragment shaders (you write here)
- opencomp_core/gpu_pipeline/ — GPU executor, texture pool, framebuffers (read only)
- opencomp_core/node_graph/   — NodeTree, evaluator, sockets (read only)

## GPU Model

Every node = Python wrapper + GLSL fragment shader.
Input = RGBA32F GPUTexture. Output = RGBA32F GPUTexture.
No CPU operations in the middle. Texture pool manages allocation.

## Node Naming

bl_idname = "OC_N_{nodename}"   e.g. "OC_N_grade"
File:      nodes/{category}/{nodename}.py
Shader:    shaders/{nodename}.frag

## Writing a New Node

1. Copy the GradeNode template from CONVENTIONS.md
2. Write the Python wrapper in nodes/{category}/{name}.py
3. Write the GLSL shader in shaders/{name}.frag
4. Add entry to memory/node_registry.json
5. Call opencomp.node_registry.refresh()

## Current Nodes

See node_registry.json for the full list.

## Rules

- Return None if input is None — never crash the graph
- Use texture_pool.get() — never allocate GPUTexture directly
- Never clamp pipeline values (only at display)
- Preserve alpha unless node specifically handles it
- See CONVENTIONS.md for full rules
