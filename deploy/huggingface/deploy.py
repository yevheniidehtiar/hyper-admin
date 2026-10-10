"""Deploy (or restart) the hosted ERP demo on a Hugging Face Docker Space.

Used by ``.github/workflows/demo.yml``::

    HF_TOKEN=... uv run --with huggingface_hub python deploy/huggingface/deploy.py \\
        --space owner/hyper-admin-demo [--restart-only]

A deploy stages the files the Space's Dockerfile needs, rotates the Space secrets
(``HYPERADMIN_SECRET_KEY`` and a superuser password nobody needs), and replaces the
Space contents; the Space then rebuilds. ``--restart-only`` just restarts the Space,
which reseeds its throwaway database (the nightly reset).
"""

from __future__ import annotations

import argparse
import os
import secrets
import shutil
import tempfile
from pathlib import Path

from huggingface_hub import HfApi

REPO_ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent

# Paths copied from the repository into the Space (relative to the repo root).
STAGED_PATHS = (
    "pyproject.toml",
    "uv.lock",
    "LICENSE",
    "src",
    "examples/__init__.py",
    "examples/erp",
)
IGNORED = shutil.ignore_patterns("__pycache__", "*.pyc", "*.db")


def stage(target: Path) -> None:
    """Copy the demo's build context into ``target``."""
    for rel in STAGED_PATHS:
        source = REPO_ROOT / rel
        destination = target / rel
        destination.parent.mkdir(parents=True, exist_ok=True)
        if source.is_dir():
            shutil.copytree(source, destination, ignore=IGNORED)
        else:
            shutil.copy2(source, destination)
    # The Space card doubles as the package readme (pyproject's ``readme``).
    shutil.copy2(HERE / "README.md", target / "README.md")
    shutil.copy2(HERE / "Dockerfile", target / "Dockerfile")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--space", required=True, help="Space id, e.g. owner/hyper-admin-demo")
    parser.add_argument("--restart-only", action="store_true", help="restart to reset the data")
    parser.add_argument(
        "--revision", default="", help="source commit, recorded in the commit message"
    )
    args = parser.parse_args()

    api = HfApi(token=os.environ["HF_TOKEN"])

    if args.restart_only:
        api.restart_space(args.space)
        print(f"restarted https://huggingface.co/spaces/{args.space}")  # noqa: T201 - CLI output
        return

    api.create_repo(args.space, repo_type="space", space_sdk="docker", exist_ok=True)
    api.add_space_secret(args.space, "HYPERADMIN_SECRET_KEY", secrets.token_urlsafe(48))
    api.add_space_secret(args.space, "HYPERADMIN_ADMIN_PASSWORD", secrets.token_urlsafe(24))

    with tempfile.TemporaryDirectory() as tmp:
        staging = Path(tmp)
        stage(staging)
        api.upload_folder(
            repo_id=args.space,
            repo_type="space",
            folder_path=staging,
            delete_patterns="*",  # drop files that no longer exist in the build context
            commit_message=f"Deploy {args.revision[:12] or 'demo'} from GitHub",
        )
    print(f"deployed https://huggingface.co/spaces/{args.space}")  # noqa: T201 - CLI output


if __name__ == "__main__":
    main()
