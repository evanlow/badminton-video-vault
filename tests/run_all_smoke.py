#!/usr/bin/env python
"""
Regression suite runner.

Discovers every tests/smoke_*.py file, runs all tests, and reports results.
Exits with code 0 on full pass, code 1 on any failure or error.

Usage (from project root):
    .\\venv\\Scripts\\python.exe tests/run_all_smoke.py
"""
import os
import sys
import glob
import importlib.util
import unittest

# ── Environment setup — MUST come before any project import ──────────────────
_TESTS_DIR = os.path.dirname(os.path.abspath(__file__))
_ROOT_DIR = os.path.dirname(_TESTS_DIR)
_TEST_DB_PATH = os.path.join(_TESTS_DIR, "_smoke_test.db").replace("\\", "/")

sys.path.insert(0, _ROOT_DIR)

os.environ["DATABASE_URL"] = f"sqlite:///{_TEST_DB_PATH}"
os.environ.setdefault("FLASK_ENV", "development")
os.environ.setdefault("AWS_ACCESS_KEY_ID", "test-key")
os.environ.setdefault("AWS_SECRET_ACCESS_KEY", "test-secret")
os.environ.setdefault("S3_BUCKET_NAME", "test-bucket")
os.environ.setdefault("AWS_REGION", "us-east-1")
# ─────────────────────────────────────────────────────────────────────────────


def _load_module(filepath):
    module_name = os.path.splitext(os.path.basename(filepath))[0]
    spec = importlib.util.spec_from_file_location(module_name, filepath)
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def main():
    smoke_files = sorted(glob.glob(os.path.join(_TESTS_DIR, "smoke_*.py")))

    if not smoke_files:
        print("ERROR: No smoke_*.py files found in tests/")
        sys.exit(1)

    loader = unittest.TestLoader()
    suite = unittest.TestSuite()

    for filepath in smoke_files:
        module = _load_module(filepath)
        suite.addTests(loader.loadTestsFromModule(module))

    total_tests = suite.countTestCases()
    print(f"{'=' * 60}")
    print(f"Badminton Video Vault — Regression Suite")
    print(f"Discovered {total_tests} tests across {len(smoke_files)} file(s)")
    print(f"{'=' * 60}")

    runner = unittest.TextTestRunner(verbosity=2, stream=sys.stdout)
    result = runner.run(suite)

    total = result.testsRun
    failures = len(result.failures) + len(result.errors)
    passed = total - failures

    print()
    print("=" * 60)
    if failures == 0:
        print(f"RESULT: {passed}/{total} passed — ALL PASS ✓")
    else:
        print(f"RESULT: {passed}/{total} passed, {failures} failure(s) — FAIL ✗")
    print("=" * 60)

    # Clean up test database file
    if os.path.exists(_TEST_DB_PATH):
        try:
            os.unlink(_TEST_DB_PATH)
        except OSError:
            pass  # Non-critical; file may be locked on Windows

    sys.exit(1 if failures else 0)


if __name__ == "__main__":
    main()
