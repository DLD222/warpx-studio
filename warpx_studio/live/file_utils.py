"""Small openPMD helpers shared by the h5py, yt, and matplotlib renderers."""
from __future__ import annotations

import re
from pathlib import Path

_ITER = re.compile(r"openpmd_(\d+)\.h5$")


def iteration_file(pmd: str | Path, iteration: int | None = None) -> tuple[Path, int]:
    folder = Path(pmd).parent
    pairs = [(int(m.group(1)), p) for p in folder.glob("openpmd_*.h5")
             if (m := _ITER.search(p.name))]
    if not pairs:
        raise FileNotFoundError(f"no openpmd_*.h5 next to {pmd}")
    pairs.sort()
    if iteration is None:
        return pairs[-1][1], pairs[-1][0]
    for it, p in pairs:
        if it == int(iteration):
            return p, it
    raise FileNotFoundError(f"iteration {iteration} not in {folder}")
