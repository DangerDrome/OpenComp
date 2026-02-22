<p align="center">
  <h1 align="center">OpenComp</h1>
  <p align="center">
    <strong>Open-source GPU compositor for VFX.</strong><br>
    Node-based. Color-managed. EXR-native. Cross-platform.
  </p>
  <p align="center">
    <a href="LICENSE"><img src="https://img.shields.io/badge/License-GPLv3-blue.svg" alt="License: GPL v3"></a>
    <img src="https://img.shields.io/badge/Python + GLSL-green.svg" alt="Python + GLSL">
    <img src="https://img.shields.io/badge/Linux%20%7C%20macOS%20%7C%20Windows-lightgrey.svg" alt="Cross-platform">
  </p>
</p>

---

OpenComp is a node-based compositing application for visual effects work. It gives you a Nuke-style workflow — GPU-accelerated, scene-linear, multi-format — without paying five figures a year for the privilege.

The compositor is entirely custom: its own node system, its own GLSL pipeline, its own execution model. Built on OpenColorIO and OpenImageIO — the same libraries that power every major VFX tool. Pure Python and GLSL, no compilation, runs everywhere.

Open source proved it can go toe-to-toe with the best in 3D. We think compositing is next.

---

## How It Works

Every compositing node is a GLSL fragment shader. Every intermediate result is a GPU-resident RGBA32F texture. The CPU only touches pixels at I/O boundaries. One draw call per node, zero copies between them.

```
 Read (OIIO)  →  Node Graph  →  GLSL Dispatch  →  Viewer (OCIO)
                  topo sort       per-node          hardware
                  dirty prop      RGBA32F           display
                                  GPU-resident      transform
```

A texture pool manages VRAM reuse across the graph, so memory stays predictable even with heavy node counts. The whole pipeline lives on the GPU from the moment pixels leave disk to the moment they hit your monitor.

## What's In The Box

- **Grade** — lift/gamma/gain + ASC CDL, 32-bit float throughout
- **Merge** — Over, Plus, Multiply, Screen with proper premultiplication
- **Blur** — separable Gaussian, runs as two passes (horizontal + vertical)
- **Transform** — translate, rotate, scale with filtered sampling
- **Read / Write** — multi-layer EXR, TIFF, DPX, PNG, JPEG via OpenImageIO
- **Viewer** — real-time display with OCIO hardware transforms
- **Conform** — plate ingest, naming convention matching, `.nk` export for Nuke roundtripping

### Coming Soon

- **OpenClaw** — an AI agent that builds compositing nodes from plain-language descriptions, validated and sandboxed

## Quick Start

```bash
git clone https://github.com/danger-studio/opencomp.git
cd opencomp

python install.py
./opencomp
```

Clone to running compositor in under a minute. No build step. No dependency hell.

## Contributing

OpenComp is actively developed and contributions are welcome. The codebase is intentionally simple — if you can write Python and basic GLSL, you can build nodes.

| Document | What's in it |
|---|---|
| [ARCHITECTURE.md](ARCHITECTURE.md) | System design, GPU pipeline, execution model |
| [ROADMAP.md](ROADMAP.md) | Build phases and progress |
| [CONVENTIONS.md](CONVENTIONS.md) | Code style and contribution guidelines |

### Tests

```bash
python -m pytest tests/
```

## Business Model

OpenComp is free software and the core always will be. The project follows an open-core model — premium node packs and studio tools available through the OpenComp marketplace.

## License

[GNU General Public License v3.0](LICENSE)
