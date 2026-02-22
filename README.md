<p align="center">

# $${\Huge OpenComp}$$
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

OpenComp is a node-based compositing application for visual effects work. GPU-accelerated, scene-linear, multi-format — built on OpenColorIO and OpenImageIO, the same libraries that power every major VFX tool.

Pure Python and GLSL. No compilation. Runs everywhere.

<!-- TODO: screenshot -->

## Features

- **Full GPU pipeline** — every node is a GLSL fragment shader on RGBA32F textures. One draw call per node, zero CPU copies between them.
- **Grade** — lift/gamma/gain + ASC CDL, 32-bit float throughout
- **Merge** — Over, Plus, Multiply, Screen with proper premultiplication
- **Blur** — separable Gaussian, two-pass (horizontal + vertical)
- **Transform** — translate, rotate, scale with filtered sampling
- **Read / Write** — multi-layer EXR, TIFF, DPX, PNG, JPEG via OpenImageIO
- **Viewer** — real-time display with OCIO hardware transforms
- **Conform** — plate ingest, naming convention matching, `.nk` export for Nuke roundtripping
- **OpenClaw** *(coming soon)* — AI agent that builds compositing nodes from plain-language descriptions

## Quick Start

```bash
git clone https://github.com/danger-studio/opencomp.git
cd opencomp

python install.py
./opencomp
```

## Documentation

| | |
|---|---|
| [ARCHITECTURE.md](ARCHITECTURE.md) | System design, GPU pipeline, execution model |
| [ROADMAP.md](ROADMAP.md) | Build phases and progress |
| [CONVENTIONS.md](CONVENTIONS.md) | Code style and contribution guidelines |

## Contributing

Contributions are welcome. The codebase is intentionally simple — if you can write Python and basic GLSL, you can build nodes.

```bash
python -m pytest tests/
```

## License

[GPL-3.0](LICENSE)
