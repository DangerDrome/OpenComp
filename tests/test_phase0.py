"""
Phase 0 tests — Repo structure and install.py.
All tests must pass before Phase 1 begins.
"""

import pathlib
import os

REPO_ROOT = pathlib.Path(__file__).parent.parent

REQUIRED_DIRS = [
    "app_template",
    "opencomp_core",
    "opencomp_core/node_graph",
    "opencomp_core/gpu_pipeline",
    "opencomp_core/nodes",
    "opencomp_core/nodes/io",
    "opencomp_core/nodes/color",
    "opencomp_core/nodes/merge",
    "opencomp_core/nodes/filter",
    "opencomp_core/nodes/transform",
    "opencomp_core/nodes/viewer",
    "opencomp_core/shaders",
    "opencomp_core/conform",
    "opencomp_core/openclaw_integration",
    "opencomp_core/openclaw_integration/memory",
    "opencomp_core/compat",
    "tests",
    "docs",
]

REQUIRED_FILES = [
    "CLAUDE.md",
    "ARCHITECTURE.md",
    "CONVENTIONS.md",
    "ROADMAP.md",
    "LICENSE",
    "README.md",
    ".gitignore",
    "install.py",
    "app_template/__init__.py",
    "opencomp_core/__init__.py",
    "opencomp_core/compat/__init__.py",
    "opencomp_core/compat/blender_5x.py",
    "opencomp_core/compat/blender_51.py",
    "opencomp_core/openclaw_integration/memory/codebase.md",
    "opencomp_core/openclaw_integration/memory/node_registry.json",
    "tests/run_tests.py",
    "tests/test_phase0.py",
]

GITIGNORE_PATTERNS = [
    "blender/",
    "__pycache__/",
    "*.pyc",
    "*.blend1",
    "*.tx",
    ".DS_Store",
    "venv/",
]


def run(test):

    def check_dirs():
        for d in REQUIRED_DIRS:
            path = REPO_ROOT / d
            assert path.is_dir(), f"Missing directory: {d}"

    def check_files():
        for f in REQUIRED_FILES:
            path = REPO_ROOT / f
            assert path.is_file(), f"Missing file: {f}"

    def check_gitignore():
        gitignore = (REPO_ROOT / ".gitignore").read_text()
        for pattern in GITIGNORE_PATTERNS:
            assert pattern in gitignore, f".gitignore missing pattern: {pattern}"

    def check_license():
        text = (REPO_ROOT / "LICENSE").read_text()
        assert "GNU GENERAL PUBLIC LICENSE" in text, "LICENSE does not contain GPL text"
        assert "Version 3" in text, "LICENSE is not GPL v3"

    def check_install_py():
        install = REPO_ROOT / "install.py"
        assert install.is_file(), "install.py missing"
        text = install.read_text()
        assert "blender" in text.lower(), "install.py doesn't reference blender"
        assert "app_template" in text, "install.py doesn't reference app_template"
        assert "opencomp_core" in text, "install.py doesn't reference opencomp_core"

    def check_blender_dir_gitignored():
        gitignore = (REPO_ROOT / ".gitignore").read_text()
        assert "blender/" in gitignore, "blender/ not in .gitignore"
        # blender/ dir itself should NOT be tracked
        blender_dir = REPO_ROOT / "blender"
        if blender_dir.exists():
            # Fine — user has downloaded it
            pass

    def check_readme_has_setup():
        readme = (REPO_ROOT / "README.md").read_text()
        assert "blender.org" in readme, "README missing blender download link"
        assert "install.py" in readme, "README missing install.py instructions"
        assert "app-template OpenComp" in readme, "README missing launch command"

    def check_claude_md():
        claude_md = (REPO_ROOT / "CLAUDE.md").read_text()
        assert "./blender/blender" in claude_md, "CLAUDE.md missing repo-local blender path"
        assert "expose_bundled_modules" in claude_md, "CLAUDE.md missing expose_bundled_modules"
        assert "RGBA32F" in claude_md, "CLAUDE.md missing RGBA32F texture info"
        assert "KISS" in claude_md, "CLAUDE.md missing KISS rule"

    test("Required directories exist",          check_dirs)
    test("Required files exist",                check_files)
    test(".gitignore has correct patterns",     check_gitignore)
    test("LICENSE is GPL 3.0",                  check_license)
    test("install.py is correct",               check_install_py)
    test("blender/ is gitignored",              check_blender_dir_gitignored)
    test("README has setup instructions",       check_readme_has_setup)
    test("CLAUDE.md has repo-local blender",   check_claude_md)
