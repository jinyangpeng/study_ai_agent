"""Console-script entry points (dev / prod / lint / fmt)."""

# -*- coding: utf-8 -*-
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent


def _run(env: str) -> None:
    """Launch the FastAPI server in the given environment."""
    os.environ["ENV"] = env
    cmd = [sys.executable, str(PROJECT_ROOT / "main.py")]
    raise SystemExit(subprocess.call(cmd, cwd=PROJECT_ROOT))


def _ruff(*args: str) -> None:
    """Run ruff with the given subcommand against the project sources."""
    cmd = [sys.executable, "-m", "ruff", *args, "src/", "main.py"]
    raise SystemExit(subprocess.call(cmd, cwd=PROJECT_ROOT))


def dev() -> None:
    """Run the dev server (ENV=development)."""
    _run("development")


def prod() -> None:
    """Run the prod server (ENV=production)."""
    _run("production")


def lint() -> None:
    """Run `ruff check` on the project sources."""
    _ruff("check")


def fmt() -> None:
    """Run `ruff format` on the project sources."""
    _ruff("format")


__all__ = ["dev", "prod", "lint", "fmt"]
