"""Find runnable WarpX binaries and label their build features/family.

Works with both an official WarpX checkout and a fork:

* official: ``build/bin/warpx.2d``, ``build_multi/bin/warpx.2d`` ...
* fork:     ``audit_build/fork/bin/warpx.2d.MPI.OMP.DP...``
* arbitrary compiled binary: ``WARPX_STUDIO_BINARY=/path/to/warpx.2d``

The fork encodes build features in the executable name; official names are plain.
"""
from __future__ import annotations

import os
import re
from pathlib import Path

FEATURES = {
    "MPI": "MPI", "OMP": "OpenMP", "OPMD": "openPMD", "FFT": "spectral (PSATD)",
    "EB": "embedded boundary", "QED": "QED", "PSATD": "PSATD", "GPU": "GPU",
}
PATTERN = re.compile(r"^warpx\.([0-9]+d|rz)((?:\\.[A-Za-z0-9]+)*)$", re.I)


def describe(path: Path, family: str | None = None) -> dict:
    match = PATTERN.match(path.name)
    dims = match.group(1).lower() if match else "?"
    tags = [t for t in (match.group(2).split(".") if match else []) if t]
    features = [FEATURES.get(t.upper(), t) for t in tags]
    path_s = str(path)
    if family is None:
        family = "fork" if ("/audit_build/" in path_s or "/fork/" in path_s) else "official"
    return {"path": path_s, "name": path.name, "dims": dims,
            "family": family, "build": path.parent.parent.name,
            "features": features, "mtime": path.stat().st_mtime}


def _candidates(root: Path, extra_dirs: list[Path]) -> list[Path]:
    roots = [root / "audit_build", root / "build", root / "build_multi",
             root / "build_star", root / "build_multi_hdf5_fft",
             root / "build_*", root / "audit_runs/studio_builds",
             *extra_dirs]
    out: list[Path] = []
    out.extend(sorted(root.glob("build_*/bin/warpx.*")))
    for base in roots:
        if base.exists():
            out.extend(sorted(base.glob("*/bin/warpx.*")))
            out.extend(sorted(base.glob("bin/warpx.*")))
    return out


def discover(root: Path | None, extra_dirs: list[Path] | None = None,
             explicit: Path | None = None) -> list[dict]:
    """Return every runnable ``warpx.*`` binary, de-duplicated by real path."""
    found: dict[str, dict] = {}
    explicit = explicit or None
    if explicit is not None and explicit.is_file():
        found[str(explicit.resolve())] = describe(explicit.resolve(), family="explicit")
    root = root or Path.cwd()
    for candidate in _candidates(root, list(extra_dirs or [])):
        if candidate.is_file() and os.access(candidate, os.X_OK):
            found.setdefault(str(candidate.resolve()), describe(candidate))
    return sorted(found.values(), key=lambda item: (item["dims"], item["family"], item["name"]))
