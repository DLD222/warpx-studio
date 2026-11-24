"""Runtime configuration for the standalone WarpX Studio.

The Studio does not assume that it lives inside a WarpX checkout.  Everything that
depends on a particular WarpX installation is resolved here:

* ``WARPX_STUDIO_WARPX_ROOT``  WarpX source checkout (official or fork)
* ``WARPX_STUDIO_BINARY``      explicit executable (may be outside that checkout)
* ``WARPX_STUDIO_DATA``        projects/runs (default: ~/.local/share/warpx-studio)
* ``WARPX_STUDIO_PROFILE``     auto|official|fork (labels the selected binary)

Old in-repo data can be migrated by pointing ``WARPX_STUDIO_DATA`` at
``<checkout>/audit_runs/studio_projects`` once, then copying it.
"""
from __future__ import annotations

import os
from pathlib import Path


def _marker(path: Path) -> bool:
    return (path / "Source" / "WarpX.cpp").is_file()


def warpx_root() -> Path | None:
    """Return the WarpX checkout, if one is configured/auto-detectable."""
    explicit = os.environ.get("WARPX_STUDIO_WARPX_ROOT")
    if explicit:
        p = Path(explicit).expanduser().resolve()
        return p if p.is_dir() else None
    here = Path.cwd().resolve()
    for p in (here, *here.parents):
        if _marker(p):
            return p
    return None


def profile(root: Path | None = None) -> str:
    """``official`` or ``fork`` (best-effort, only used for display/gating hints)."""
    explicit = os.environ.get("WARPX_STUDIO_PROFILE")
    if explicit in ("official", "fork"):
        return explicit
    root = root or warpx_root()
    if root and (root / "Source" / "Plugins" / "PicEm").is_dir():
        return "fork"
    return "official"


def data_root() -> Path:
    """Writable user data directory (projects, runs, build outputs)."""
    explicit = os.environ.get("WARPX_STUDIO_DATA")
    if explicit:
        return Path(explicit).expanduser().resolve()
    return Path.home() / ".local" / "share" / "warpx-studio"


def projects_root() -> Path:
    """Named projects. Can point at an old ``audit_runs/studio_projects`` during migration."""
    explicit = os.environ.get("WARPX_STUDIO_PROJECTS")
    p = Path(explicit).expanduser().resolve() if explicit else data_root() / "projects"
    p.mkdir(parents=True, exist_ok=True)
    return p


def runs_root() -> Path:
    explicit = os.environ.get("WARPX_STUDIO_RUNS")
    p = Path(explicit).expanduser().resolve() if explicit else data_root() / "runs"
    p.mkdir(parents=True, exist_ok=True)
    return p


def explicit_binary() -> Path | None:
    value = os.environ.get("WARPX_STUDIO_BINARY")
    if not value:
        return None
    p = Path(value).expanduser().resolve()
    return p if p.is_file() else None


def summary() -> dict:
    root = warpx_root()
    return {
        "warpx_root": str(root) if root else None,
        "profile": profile(root),
        "data_root": str(data_root()),
        "projects_root": str(projects_root()),
        "runs_root": str(runs_root()),
        "explicit_binary": str(explicit_binary()) if explicit_binary() else None,
    }
