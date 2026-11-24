"""Enumerate openPMD field arrays with h5py (no ParaView required)."""
from __future__ import annotations

from pathlib import Path

import h5py

from .file_utils import iteration_file


def _axis(name: str, index: int) -> str:
    # RZ uses r,t,z; Cartesian uses x,y,z. Keep the file's component name as axis.
    return name or ("xyz"[index] if index < 3 else str(index))


def list_quantities(pmd: str | Path, iteration: int | None = None) -> list[dict]:
    path, _ = iteration_file(pmd, iteration)
    with h5py.File(path, "r") as h5:
        it = list(h5["data"].keys())[-1]
        fields = h5[f"data/{it}/fields"]
        out: list[dict] = []
        for name in fields.keys():
            node = fields[name]
            if isinstance(node, h5py.Dataset):
                out.append({"name": name, "ncomp": 1, "components": []})
                continue
            comps = []
            for i, c in enumerate(node.keys()):
                comps.append({"index": i, "name": c, "axis": _axis(c, i)})
            out.append({"name": name, "ncomp": max(1, len(comps)),
                        "components": comps})
    return out
