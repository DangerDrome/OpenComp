# OpenComp

An open source, Nuke-like VFX compositor built as a Blender add-on.

No compilation. Python + GLSL only. GPL 3.0.

---

## What It Is

OpenComp uses Blender purely as infrastructure (GPU context, OCIO, OIIO, windowing)
while building a completely custom node-based GPU compositor on top. It does not
use or extend Blender's built-in compositor.

---

## Setup

### 1. Clone the repo

```bash
git clone https://github.com/danger-studio/opencomp.git
cd opencomp
```

### 2. Download Blender 5.0

Download Blender 5.0 stable from https://blender.org/download

Extract it so the binary is at:
```
opencomp/blender/blender          (Linux / macOS)
opencomp/blender/blender.exe      (Windows)
```

The `blender/` directory is gitignored — you manage this yourself.

### 3. Run the installer

```bash
python install.py
```

This configures the bundled Blender with the OpenComp add-on and app template.

### 4. Launch OpenComp

```bash
./blender/blender --app-template OpenComp
```

---

## Running Tests

```bash
./blender/blender --background --python tests/run_tests.py
```

Exit code 0 = all pass. Exit code 1 = failures (see output).

---

## Project Structure

See `ARCHITECTURE.md` for the full technical architecture.
See `ROADMAP.md` for build phases and progress.
See `CONVENTIONS.md` for coding standards.

---

## Development

Claude Code context is in `CLAUDE.md` — this is read automatically at
the start of every Claude Code session.

---

## License

GPL 3.0 — see LICENSE file.

Monetisation model: open source core + commercial premium node packs
distributed via the OpenComp marketplace. GPL does not prevent this.
