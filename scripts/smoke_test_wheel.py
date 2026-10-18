"""Smoke-test an installed ``hyper-admin`` wheel before it is uploaded to PyPI.

Run it with the interpreter of a clean virtualenv that holds only the built
wheel (plus ``httpx`` for ``TestClient``), from a directory outside the source
tree so ``import hyperadmin`` resolves to the installed wheel::

    python scripts/smoke_test_wheel.py --expect-version 0.5.0a1

A bare ``import hyperadmin`` is not enough: zero-config demo mode creates its
``sqlite+aiosqlite`` engine lazily, so a wheel missing a runtime dependency only
fails on the first request. This script makes that request.
"""

from __future__ import annotations

import argparse
import sys

from fastapi import FastAPI
from fastapi.testclient import TestClient

import hyperadmin
from hyperadmin import Admin


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Smoke-test an installed hyper-admin wheel.")
    parser.add_argument("--expect-version", help="fail unless hyperadmin.__version__ equals this")
    args = parser.parse_args(argv)

    sys.stdout.write(f"hyperadmin {hyperadmin.__version__} from {hyperadmin.__file__}\n")
    if args.expect_version and hyperadmin.__version__ != args.expect_version:
        sys.stderr.write(
            f"version mismatch: installed {hyperadmin.__version__}, "
            f"expected {args.expect_version}\n"
        )
        return 1

    app = FastAPI()
    Admin(app).mount("/admin")
    with TestClient(app) as client:
        response = client.get("/admin/")
    sys.stdout.write(f"GET /admin/ -> {response.status_code}\n")
    if response.status_code != 200:
        sys.stderr.write(response.text[:2000] + "\n")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
