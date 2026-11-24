"""Locate ParaView's headless Python interpreter when it is available.

ParaView is optional.  The normal 2-D live view uses matplotlib + h5py; ParaView is
only needed for 3-D, volume rendering, particle overlays, and VTK export.  A fresh
clone therefore must not fail just because pvpython is absent.
"""
from __future__ import annotations

import os
import shutil
from pathlib import Path


def pvpython_path() -> Path | None:
    """Return a usable ``pvpython``, honouring explicit configuration first."""
    for key in ("WARPX_STUDIO_PVPYTHON", "WARPS_STUDIO_PVPYTHON"):
        value = os.environ.get(key)
        if value:
            p = Path(value).expanduser()
            return p.resolve() if p.is_file() else None
    found = shutil.which("pvpython")
    if found:
        return Path(found).resolve()
    candidates = [
        Path.home() / "miniconda3/envs/paraview/bin/pvpython",
        Path.home() / "miniconda3/envs/paraview*/bin/pvpython",
        Path.home() / "paraview*/bin/pvpython",
        Path("/opt/paraview*/bin/pvpython"),
        Path("/usr/bin/pvpython"),
        Path("/usr/local/bin/pvpython"),
    ]
    for pattern in candidates:
        if "*" in str(pattern):
            matches = sorted(Path(str(pattern).split("*")[0]).parent.glob(pattern.name))
            if matches:
                return matches[0].resolve()
        elif pattern.is_file():
            return pattern.resolve()
    return None


def paraview_gui() -> Path | None:
    value = os.environ.get("WARPX_STUDIO_PARAVIEW")
    if value:
        p = Path(value).expanduser()
        return p.resolve() if p.is_file() else None
    found = shutil.which("paraview")
    return Path(found).resolve() if found else None


def status() -> dict:
    pv = pvpython_path()
    gui = paraview_gui()
    return {"pvpython": str(pv) if pv else None,
            "gui": str(gui) if gui else None,
            "available": pv is not None}


def missing_hint() -> str:
    return ("ParaView/pvpython not found. 2-D fields fall back to matplotlib+h5py. "
            "For 3-D/particles/VTK install ParaView and set "
            "WARPX_STUDIO_PVPYTHON=/path/to/pvpython, or `pip install -e '.[viz]'` "
            "for the 2-D fallback.")
