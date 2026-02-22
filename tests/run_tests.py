#!/usr/bin/env python3
"""
OpenComp test runner.

Run with bundled Blender:
    ./blender/blender --background --python tests/run_tests.py

Exit code 0 = all tests pass.
Exit code 1 = one or more failures.
"""

import sys
import os
import traceback
import pathlib

# Add repo root to path
REPO_ROOT = pathlib.Path(__file__).parent.parent
sys.path.insert(0, str(REPO_ROOT))

results = {"passed": [], "failed": [], "errors": []}


def test(name, fn):
    try:
        fn()
        results["passed"].append(name)
        print(f"  ✓  {name}")
    except AssertionError as e:
        results["failed"].append((name, str(e)))
        print(f"  ✗  {name}: {e}")
    except Exception as e:
        results["errors"].append((name, traceback.format_exc()))
        print(f"  !  {name}: {e}")


def run_suite(suite_name, suite_module_path):
    print(f"\n{suite_name}")
    print("─" * 60)
    try:
        import importlib.util
        spec   = importlib.util.spec_from_file_location("suite", suite_module_path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        module.run(test)
    except FileNotFoundError:
        print(f"  (not yet written)")
    except Exception as e:
        print(f"  ERROR loading suite: {e}")
        traceback.print_exc()


# ── Run all suites ─────────────────────────────────────────────────────────

tests_dir = REPO_ROOT / "tests"

run_suite("Phase 0 — Repo Structure",  tests_dir / "test_phase0.py")
run_suite("Phase 1 — GPU Pipeline",    tests_dir / "test_phase1.py")
run_suite("Phase 2 — Node Graph",      tests_dir / "test_phase2.py")
run_suite("Phase 3 — First Pipeline",  tests_dir / "test_phase3.py")
run_suite("Phase 4 — Node Library",    tests_dir / "test_phase4.py")
run_suite("Phase 5 — Viewer",          tests_dir / "test_phase5.py")
run_suite("Phase 6 — Conform Tool",    tests_dir / "test_phase6.py")
run_suite("Phase 7 — OpenClaw",        tests_dir / "test_phase7.py")

# ── Results ────────────────────────────────────────────────────────────────

total  = len(results["passed"]) + len(results["failed"]) + len(results["errors"])
passed = len(results["passed"])

print(f"\n{'━' * 60}")
print(f"  {passed}/{total} tests passed")

if results["failed"]:
    print("\nFailed:")
    for name, msg in results["failed"]:
        print(f"  ✗  {name}")
        if msg:
            print(f"     {msg}")

if results["errors"]:
    print("\nErrors:")
    for name, tb in results["errors"]:
        print(f"  !  {name}")
        print(tb)

if passed == total and total > 0:
    print("\n  All tests passed ✓")
    sys.exit(0)
else:
    print("\n  Tests FAILED ✗")
    sys.exit(1)
