#!/bin/bash
# OpenComp Launcher
# Double-click this script to launch OpenComp

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "=============================================="
echo "  OpenComp - Professional VFX Compositor"
echo "=============================================="
echo ""

# Check for Blender
if [ ! -f "blender/blender" ]; then
    echo "ERROR: Blender not found!"
    echo ""
    echo "Please download Blender 5.0+ and extract it to:"
    echo "  $SCRIPT_DIR/blender/"
    echo ""
    echo "Download from: https://www.blender.org/download/"
    echo ""
    read -p "Press Enter to exit..."
    exit 1
fi

echo "[1/3] Checking dependencies..."

# Check for Node.js
if ! command -v node &> /dev/null; then
    echo "ERROR: Node.js not found!"
    echo ""
    echo "Please install Node.js from: https://nodejs.org/"
    echo ""
    read -p "Press Enter to exit..."
    exit 1
fi

NODE_VERSION=$(node -v | cut -d'v' -f2 | cut -d'.' -f1)
if [ "$NODE_VERSION" -lt 18 ]; then
    echo "ERROR: Node.js 18+ required (found v$NODE_VERSION)"
    exit 1
fi

# Install npm dependencies if needed
if [ ! -d "opencomp_electron/node_modules" ]; then
    echo "[2/3] Installing dependencies (first run)..."
    cd opencomp_electron
    npm install
    cd ..
else
    echo "[2/3] Dependencies OK"
fi

echo "[3/3] Launching OpenComp..."
echo ""

# Launch the Electron app
cd opencomp_electron
npm run electron:dev

# If electron:dev fails, try running directly
# node_modules/.bin/electron .
