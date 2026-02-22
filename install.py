#!/usr/bin/env python3
"""
OpenComp installer.

Configures the bundled Blender with the OpenComp add-on and app template.
Run once after cloning the repo and extracting Blender to ./blender/

Usage:
    python install.py
"""

import sys
import os
import shutil
import platform
import pathlib

REPO_ROOT = pathlib.Path(__file__).parent.resolve()

# ── Locate bundled Blender ─────────────────────────────────────────────────

def find_blender_binary():
    system = platform.system()
    if system == "Windows":
        binary = REPO_ROOT / "blender" / "blender.exe"
    else:
        binary = REPO_ROOT / "blender" / "blender"

    if not binary.exists():
        print(f"[OpenComp] ERROR: Blender binary not found at {binary}")
        print(f"[OpenComp] Download Blender 5.0 from https://blender.org/download")
        print(f"[OpenComp] Extract it so the binary is at: {binary}")
        sys.exit(1)

    return binary


def find_blender_version_dir():
    """Find the versioned config directory inside the bundled Blender."""
    blender_dir = REPO_ROOT / "blender"

    # Look for version directory (e.g. 5.0, 5.1)
    for item in blender_dir.iterdir():
        if item.is_dir() and item.name[0].isdigit():
            return item

    print("[OpenComp] ERROR: Could not find Blender version directory in ./blender/")
    print("[OpenComp] Expected something like ./blender/5.0/")
    sys.exit(1)


# ── Install ────────────────────────────────────────────────────────────────

def install_addon(version_dir):
    """Symlink or copy opencomp_core into Blender's addons_core directory.

    Blender 5.0 discovers add-ons from scripts/addons_core/ (not addons/).
    """
    addons_dir = version_dir / "scripts" / "addons_core"
    addons_dir.mkdir(parents=True, exist_ok=True)

    target = addons_dir / "opencomp_core"
    source = REPO_ROOT / "opencomp_core"

    if target.exists() or target.is_symlink():
        target.unlink() if target.is_symlink() else shutil.rmtree(target)

    if platform.system() == "Windows":
        # Windows: copy instead of symlink (symlinks require admin)
        shutil.copytree(source, target)
        print(f"[OpenComp] Copied add-on to {target}")
    else:
        target.symlink_to(source)
        print(f"[OpenComp] Symlinked add-on: {target} → {source}")


def install_app_template(version_dir):
    """Symlink or copy app_template into Blender's system app templates."""
    # Blender discovers templates from bl_app_templates_system (bundled)
    # or bl_app_templates_user (user-installed). We use system dir since
    # we're installing into the bundled Blender.
    templates_dir = version_dir / "scripts" / "startup" / "bl_app_templates_system"
    templates_dir.mkdir(parents=True, exist_ok=True)

    target = templates_dir / "OpenComp"
    source = REPO_ROOT / "app_template"

    if target.exists() or target.is_symlink():
        target.unlink() if target.is_symlink() else shutil.rmtree(target)

    if platform.system() == "Windows":
        shutil.copytree(source, target)
        print(f"[OpenComp] Copied app template to {target}")
    else:
        target.symlink_to(source)
        print(f"[OpenComp] Symlinked app template: {target} → {source}")


# ── Main ───────────────────────────────────────────────────────────────────

def main():
    print("[OpenComp] Installing...")
    print(f"[OpenComp] Repo root: {REPO_ROOT}")

    binary     = find_blender_binary()
    version_dir = find_blender_version_dir()

    print(f"[OpenComp] Blender binary:      {binary}")
    print(f"[OpenComp] Blender version dir: {version_dir}")

    install_addon(version_dir)
    install_app_template(version_dir)

    print()
    print("[OpenComp] Installation complete.")
    print()
    print("Launch OpenComp:")
    print(f"    {binary} --app-template OpenComp")
    print()
    print("Run tests:")
    print(f"    {binary} --background --python tests/run_tests.py")


if __name__ == "__main__":
    main()
