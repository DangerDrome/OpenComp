# OpenComp

**A professional, open-source GPU compositor for VFX — built on Blender.**

[![License: GPL v3](https://img.shields.io/badge/License-GPLv3-blue.svg)](LICENSE)

OpenComp is a node-based compositing application designed for visual effects workflows. It delivers a Nuke-style experience — GPU-accelerated, color-managed, and EXR-native — without the per-seat licensing costs.

Built entirely in Python and GLSL, OpenComp runs as a Blender 5.x add-on, leveraging Blender's mature GPU backend, OpenColorIO integration, OpenImageIO support, and node editor UI. It does **not** use or extend Blender's built-in compositor — it replaces it with a purpose-built pipeline designed for production VFX work.

---

## Features

- **Full GPU pipeline** — every node executes as a GLSL fragment shader on RGBA32F textures. No CPU bottlenecks in the compositing chain.
- **Native EXR support** — read and write multi-layer OpenEXR files via OpenImageIO, with proper half/float handling.
- **OCIO color management** — scene-linear workflow with hardware-accelerated display transforms. Respects your facility's OCIO config.
- **Node-based workflow** — familiar drag-and-connect interface with Grade, Merge (Over), Blur, Transform, and more.
- **Conform toolset** — ingest plates, match naming conventions, and export `.nk` scripts for roundtripping with Nuke pipelines.
- **Zero compilation** — pure Python + GLSL. No C++ builds, no CMake, no platform-specific binaries to maintain.

---

## Requirements

- **Blender 5.0+** (stable release)
- A GPU with OpenGL 3.3+ support
- Linux, macOS, or Windows

---

## Getting Started

### 1. Clone the repository

```bash
git clone https://github.com/danger-studio/opencomp.git
cd opencomp
```

### 2. Install Blender

Download [Blender 5.0 stable](https://blender.org/download) and extract it into the repository so the binary is located at:

```
opencomp/blender/blender          # Linux / macOS
opencomp/blender/blender.exe      # Windows
```

The `blender/` directory is gitignored and not shipped with the repository.

### 3. Run the installer

```bash
python install.py
```

This registers the OpenComp add-on and app template with the bundled Blender installation.

### 4. Launch

```bash
./blender/blender --app-template OpenComp
```

---

## Architecture

OpenComp treats Blender as infrastructure — GPU context, windowing, color management — while maintaining its own compositing pipeline:

```
Node Graph  →  Topological Sort  →  GLSL Shader Dispatch  →  Display
                                      (one draw call per node)
```

Every intermediate result lives on the GPU as an RGBA32F texture. The CPU is only involved at I/O boundaries (reading plates, writing output). A texture pool manages GPU memory reuse across the graph.

For full technical details, see [ARCHITECTURE.md](ARCHITECTURE.md).

---

## Development

| Document | Purpose |
|---|---|
| [ARCHITECTURE.md](ARCHITECTURE.md) | System design and GPU pipeline details |
| [ROADMAP.md](ROADMAP.md) | Build phases and current progress |
| [CONVENTIONS.md](CONVENTIONS.md) | Coding standards and naming conventions |
| [CLAUDE.md](CLAUDE.md) | AI-assisted development context |

### Running Tests

```bash
./blender/blender --background --python tests/run_tests.py
```

Exit code `0` indicates all tests passed.

---

## License

OpenComp is released under the [GNU General Public License v3.0](LICENSE).

The project follows an open-core model: the compositor itself is fully open source, with optional premium node packs available through the OpenComp marketplace.
