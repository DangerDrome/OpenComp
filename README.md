<p align="center">
  <h1 align="center">OpenComp</h1>
  <p align="center">
    <strong>The open-source compositor the VFX industry has been waiting for.</strong>
  </p>
  <p align="center">
    GPU-accelerated. Color-managed. EXR-native. Free forever.
  </p>
  <p align="center">
    <a href="LICENSE"><img src="https://img.shields.io/badge/License-GPLv3-blue.svg" alt="License: GPL v3"></a>
    <img src="https://img.shields.io/badge/Python-GLSL-green.svg" alt="Python + GLSL">
    <img src="https://img.shields.io/badge/Platform-Linux%20%7C%20macOS%20%7C%20Windows-lightgrey.svg" alt="Cross-platform">
  </p>
</p>

---

## The Problem

Professional compositing costs **$10,000+ per seat per year**. The entire VFX industry runs on a single proprietary tool with no real competition. Studios pay millions in licensing. Freelancers get priced out. Students learn on software they can't afford to keep using.

Blender proved that open source can compete at the highest level in 3D. **OpenComp is doing the same thing for compositing.**

## What OpenComp Is

OpenComp is a production-grade, node-based VFX compositor that delivers a Nuke-class workflow at zero cost. It runs as a Blender 5.x application, leveraging Blender's battle-tested GPU backend, OpenColorIO color management, and OpenImageIO format support — while replacing Blender's compositor entirely with a purpose-built GPU pipeline designed for film and episodic work.

This is not a toy. This is not a plugin. This is a full compositing application with its own rendering pipeline, its own node system, and its own execution model.

## Why It Works

Most open-source compositing projects fail because they try to build everything from scratch — windowing, GPU abstraction, color management, file I/O, UI frameworks. That's millions of lines of infrastructure code before you write a single compositing node.

OpenComp takes a different approach: **use Blender as a runtime.** Blender already ships OpenColorIO, OpenImageIO, a proven GPU abstraction layer, a flexible node editor, and runs on every platform. We build the compositor on top of that foundation — zero compilation, pure Python and GLSL, installable in under a minute.

The result is a project that a small team can actually ship and maintain, instead of an ambitious C++ codebase that dies in pre-alpha.

## Key Capabilities

**Full GPU Pipeline** — Every compositing node executes as a GLSL fragment shader operating on 32-bit float textures. The entire image chain lives on the GPU. No CPU roundtrips, no memory copies between nodes. One draw call per operation.

**Industry-Standard Color Management** — Scene-linear workflow powered by OpenColorIO 2.5 with hardware-accelerated display transforms. Drop in your facility's ACES config and it just works.

**Native EXR & Multi-Format I/O** — Read and write multi-layer OpenEXR, TIFF, DPX, JPEG, PNG, and more via OpenImageIO 3.1. Proper half-float and full-float handling throughout.

**Production Node Set** — Grade (lift/gamma/gain + CDL), Merge (Over, Plus, Multiply, Screen), Blur (separable Gaussian), Transform (translate/rotate/scale with filtering), Crop, and a real-time Viewer with OCIO display.

**Conform & Pipeline Integration** — Ingest plates, auto-match naming conventions, and export `.nk` scripts for roundtripping with existing Nuke pipelines. OpenComp fits into your facility — it doesn't demand you abandon your infrastructure.

**AI-Assisted Node Creation** *(coming soon)* — OpenClaw, an integrated AI agent, lets artists describe compositing operations in plain language and generates validated, sandboxed nodes on the fly.

## Architecture

```
 Plate I/O          Node Graph           GPU Pipeline            Display
┌─────────┐    ┌────────────────┐    ┌─────────────────┐    ┌────────────┐
│  OIIO   │───>│  Topological   │───>│  GLSL Shader    │───>│  Viewport  │
│  Read   │    │  Sort + Dirty  │    │  Dispatch       │    │  + OCIO    │
│         │    │  Propagation   │    │  (per-node)     │    │  Display   │
└─────────┘    └────────────────┘    └─────────────────┘    └────────────┘
                                      RGBA32F textures
                                      GPU-resident pool
                                      Zero CPU copies
```

Every intermediate result is a GPU-resident RGBA32F texture. The CPU only touches pixels at I/O boundaries. A texture pool manages GPU memory reuse across the graph, keeping VRAM usage predictable under heavy node counts.

## The Market

The compositing software market is valued at over **$2 billion** and growing. It's dominated by a single vendor with no meaningful open-source alternative. Every VFX studio, advertising house, and post-production facility on the planet needs compositing software.

OpenComp follows an **open-core model**: the compositor is fully open source and always will be. Revenue comes from premium node packs, studio support contracts, and marketplace tools — the same model that made Blender, GitLab, and Red Hat into billion-dollar ecosystems.

## Getting Started

```bash
# Clone
git clone https://github.com/danger-studio/opencomp.git
cd opencomp

# Add Blender 5.0 — download from https://blender.org/download
# Extract so the binary is at: opencomp/blender/blender

# Install
python install.py

# Launch
./blender/blender --app-template OpenComp
```

That's it. No build step. No dependencies to install. No Docker containers. Under a minute from clone to running compositor.

## Development

OpenComp is actively developed and welcomes contributors.

| Document | Purpose |
|---|---|
| [ARCHITECTURE.md](ARCHITECTURE.md) | System design and GPU pipeline internals |
| [ROADMAP.md](ROADMAP.md) | Build phases and current progress |
| [CONVENTIONS.md](CONVENTIONS.md) | Coding standards and contribution guidelines |

### Running Tests

```bash
./blender/blender --background --python tests/run_tests.py
```

## License

[GNU General Public License v3.0](LICENSE)

OpenComp is free software. Use it, modify it, ship it. The core will always be open source.
