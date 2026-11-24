"""Publication-style 2-D openPMD plots for the Studio live view.

The old live view handed every frame to ParaView with no axes, no units, no title and
an auto-range colour bar.  That is fine for a quick sanity check but not for a paper,
a talk, or for comparing electron and proton densities.

This module deliberately depends only on h5py + matplotlib (both already used by the
analysis environment).  It reads the openPMD file directly, so it also works while
WarpX is still writing the series, and it falls back to the ParaView renderer when a
frame is 3-D or when matplotlib is unavailable.

Design choices worth keeping:

* physical axes in micrometres, equal aspect;
* a titled colour bar with units, on a white background;
* robust 1--99 % colour limits, so one hot cell does not wash out the whole plot;
* ``rho_<species>`` is converted from charge density to number density ``n``;
* a signed ``rho`` gets a symmetric diverging map; positive densities get a
  perceptually ordered map;
* the EB implicit function from ``inputs`` is drawn as an outline when available;
* every panel states iteration, time and the actual min/max, so the picture is
  self-describing.
"""
from __future__ import annotations

import math
import os
import re
from pathlib import Path
from typing import Any

os.environ.setdefault("MPLBACKEND", "Agg")

import h5py          # noqa: E402
import numpy as np   # noqa: E402

ELEMENTARY_CHARGE = 1.602176634e-19
SPECIES_TEX = {"electrons": "e", "protons": "p", "positrons": "e+", "ions": "i"}


def _species_tex(name: str) -> str:
    return SPECIES_TEX.get(name, name.replace("_", r"\_"))

FIELD_UNITS = {
    "E": "V m$^{-1}$",
    "B": "T",
    "j": "A m$^{-2}$",
    "rho": "C m$^{-3}$",
    "phi": "V",
    "divE": "V m$^{-2}$",
    "divB": "T m$^{-1}$",
    "part_per_cell": "macroparticles / cell",
    "T": "eV",
}


def _iteration_file(pmd: str, iteration: int | None) -> tuple[Path, int]:
    folder = Path(pmd).parent
    files = sorted(folder.glob("openpmd_*.h5"))
    pairs: list[tuple[int, Path]] = []
    for f in files:
        m = re.search(r"openpmd_(\d+)\.h5$", f.name)
        if m:
            pairs.append((int(m.group(1)), f))
    if not pairs:
        raise FileNotFoundError(f"no openpmd_*.h5 next to {pmd}")
    pairs.sort()
    if iteration is None:
        return pairs[-1][1], pairs[-1][0]
    for it, f in pairs:
        if it == int(iteration):
            return f, it
    raise FileNotFoundError(f"iteration {iteration} not in {folder}")


def _pick_array(fields: h5py.Group, field: str, component: str | None):
    node = fields[field]
    if isinstance(node, h5py.Dataset):
        return np.asarray(node), node.attrs, field
    names = list(node.keys())
    if component is None:
        # E/B are vector groups; x is the most useful default in a 2-D XZ plot.
        comp = "x" if "x" in names else ("y" if "y" in names else names[0])
    else:
        comp = str(component).lower()
        if comp not in names:
            comp = "x" if "x" in names else names[0]
    d = node[comp]
    return np.asarray(d), d.attrs, f"{field}_{comp}"


def _units(attrs) -> tuple[float, str]:
    """Return (unitSI, human label).  openPMD stores the SI factor separately."""
    unit_si = float(attrs.get("unitSI", 1.0))
    dim = attrs.get("unitDimension", None)
    # The label is chosen by the field name below; this helper only keeps unitSI.
    return unit_si, ("" if dim is None else "")


def _label_for(field: str, shown: str) -> tuple[str, bool]:
    """Return (colourbar label, signed)."""
    if shown.startswith("rho_") and field != "rho":
        species = _species_tex(field[4:])
        return f"$n_{{{species}}}$ [m$^{{-3}}$]", False
    if field == "rho":
        return r"charge density $\rho$ [C m$^{-3}$]", True
    if field.startswith("rho_"):
        return rf"$\rho_{{{field[4:]}}}$ [C m$^{{-3}}$]", True
    if field in ("part_per_cell",) or field.startswith("part_per_cell_"):
        return "macroparticles / cell", False
    if field in FIELD_UNITS:
        return f"{field} [{FIELD_UNITS[field]}]", field == "rho"
    if shown in FIELD_UNITS:
        return f"{shown} [{FIELD_UNITS[shown]}]", False
    # Species-resolved scalar fields.
    if field.startswith("T_") or field == "Te":
        return f"{field} [eV]", False
    if field.startswith("nbar_"):
        species = _species_tex(field[5:])
        return f"$n_{{{species}}}$ [m$^{{-3}}$]", False
    if field.startswith(("uxbar_", "uybar_", "uzbar_")):
        return f"{field} [m s$^{{-1}}$]", True
    if field.endswith("_particle_production"):
        # nuclearfusion stores probability-weighted product density, not a rate.
        return f"{field} [m$^{{-3}}$]", False
    # Vector components after _pick_array, e.g. B_r, E_t, j_z.
    if len(shown) >= 3 and shown[1] == "_" and shown[0] in ("E", "B", "j"):
        base = shown[0]
        return f"{shown} [{FIELD_UNITS[base]}]", base == "E" or base == "B" or base == "j"
    return shown, False


def _eb_expression(pmd: str) -> str | None:
    """Find ``warpx.eb_implicit_function`` in the run's ``inputs``, if any."""
    base = Path(pmd).resolve()
    for parent in [base.parent, *base.parents]:
        f = parent / "inputs"
        if not f.is_file():
            continue
        try:
            for line in f.read_text(encoding="utf-8", errors="replace").splitlines():
                key, _, value = line.partition("=")
                if key.strip() == "warpx.eb_implicit_function":
                    value = value.strip().strip('"').strip("'")
                    return value or None
        except OSError:
            return None
    return None


def _eb_field(expr: str, X: np.ndarray, Z: np.ndarray) -> np.ndarray | None:
    """Evaluate the implicit function on the cell centres.

    WarpX input syntax uses ``^`` for powers; Python uses ``**``.  Only a tiny
    expression environment is exposed (no builtins, no imports).
    """
    expr = expr.replace("^", "**")
    env = {
        "x": X, "z": Z, "np": np, "pi": math.pi,
        "sqrt": np.sqrt, "abs": np.abs, "sin": np.sin, "cos": np.cos,
        "tan": np.tan, "exp": np.exp, "log": np.log, "where": np.where,
    }
    try:
        val = eval(expr, {"__builtins__": {}}, env)  # noqa: S307 - local input file
        val = np.asarray(val, dtype=float)
        return val if val.shape == X.shape else None
    except Exception:
        return None


def render(request: dict) -> dict[str, Any]:
    """Render one 2-D openPMD frame.  Raises on non-2-D data so callers fall back."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.colors import Normalize, TwoSlopeNorm
    from matplotlib.ticker import FuncFormatter

    pmd = str(request["pmd"])
    out = Path(request["out"])
    field = str(request.get("field") or "rho")
    component = request.get("component")
    iteration = request.get("iteration")
    fpath, it = _iteration_file(pmd, int(iteration) if iteration is not None else None)

    with h5py.File(fpath, "r") as h5:
        root = h5["data"][str(it)]
        fields = root["fields"]
        available = list(fields.keys())
        if field not in available:
            raise ValueError(f"field {field!r} not in {available}")
        raw, attrs, shown = _pick_array(fields, field, component)
        raw = np.squeeze(np.asarray(raw, dtype=float))
        if raw.ndim != 2:
            raise ValueError(f"matplotlib renderer only handles 2-D fields, got {raw.ndim}-D")
        spacing = np.asarray(attrs.get("gridSpacing", [1.0, 1.0]), dtype=float)
        offset = np.asarray(attrs.get("gridGlobalOffset", [0.0, 0.0]), dtype=float)
        grid_si = float(attrs.get("gridUnitSI", 1.0))
        spacing = spacing * grid_si
        offset = offset * grid_si
        unit_si, _ = _units(attrs)
        time = float(root.attrs.get("time", 0.0)) * float(root.attrs.get("timeUnitSI", 1.0))

    data = raw
    label, signed = _label_for(field, shown)
    if shown.startswith("rho_") and field != "rho":
        # rho_<species> is a charge density; n is the positive number density.
        data = np.abs(data) / ELEMENTARY_CHARGE
        label = rf"$n_{{{_species_tex(field[4:])}}}$ [m$^{{-3}}$]"
        signed = False
    elif field.startswith("rho_"):
        label = rf"$\rho_{{{field[4:]}}}$ [C m$^{{-3}}$]"
        signed = True

    finite = data[np.isfinite(data)]
    if finite.size == 0:
        raise ValueError("field is entirely non-finite")
    data_min, data_max = float(np.nanmin(data)), float(np.nanmax(data))
    if signed:
        lim = max(abs(float(np.nanpercentile(finite, 1))),
                  abs(float(np.nanpercentile(finite, 99))), 1e-30)
        norm = TwoSlopeNorm(vcenter=0.0, vmin=-lim, vmax=lim)
        cmap = "RdBu_r"
    else:
        lo = 0.0 if data_min >= 0.0 else float(np.nanpercentile(finite, 1))
        hi = float(np.nanpercentile(finite, 99))
        if not np.isfinite(hi) or hi <= lo:
            hi = max(data_max, lo + 1e-30)
        norm = Normalize(vmin=lo, vmax=hi)
        cmap = "inferno"

    nz, nx = data.shape
    dz, dx = float(spacing[0]), float(spacing[1])
    z0, x0 = float(offset[0]), float(offset[1])
    # Choose a readable physical unit.  A scaled similarity run can have a
    # 0.1--1 m box; forcing µm then prints 100000, which is unreadable.
    x_edges_si = x0 + np.arange(nx + 1) * dx
    z_edges_si = z0 + np.arange(nz + 1) * dz
    span_si = max(abs(x_edges_si[-1] - x_edges_si[0]),
                  abs(z_edges_si[-1] - z_edges_si[0]))
    if span_si >= 0.1:
        unit, unit_scale = "m", 1.0
    elif span_si >= 1e-4:
        unit, unit_scale = "mm", 1e3
    else:
        unit, unit_scale = "µm", 1e6
    x_edges = x_edges_si * unit_scale
    z_edges = z_edges_si * unit_scale
    X_si, Z_si = np.meshgrid(0.5 * (x_edges_si[:-1] + x_edges_si[1:]),
                             0.5 * (z_edges_si[:-1] + z_edges_si[1:]))
    X, Z = np.meshgrid(0.5 * (x_edges[:-1] + x_edges[1:]),
                       0.5 * (z_edges[:-1] + z_edges[1:]))

    aspect = max(0.35, min(2.8, (z_edges[-1] - z_edges[0]) / max(1e-30, x_edges[-1] - x_edges[0])))
    fig_w = 7.6
    fig_h = max(4.6, min(9.0, fig_w * aspect + 1.25))
    fig, ax = plt.subplots(figsize=(fig_w, fig_h), dpi=150, facecolor="white")
    ax.set_facecolor("#f4f6f8")
    mesh = ax.pcolormesh(x_edges, z_edges, data, cmap=cmap, norm=norm,
                         shading="auto", rasterized=True)
    ax.set_xlabel(f"x  [{unit}]", fontsize=10)
    ax.set_ylabel(f"z  [{unit}]", fontsize=10)
    ax.set_aspect("equal", adjustable="box")
    ax.tick_params(labelsize=9, colors="#333333")
    for spine in ax.spines.values():
        spine.set_color("#777777")
        spine.set_linewidth(0.8)

    cbar = fig.colorbar(mesh, ax=ax, pad=0.018, fraction=0.046)
    # A colour-bar offset text such as "×10^28" is drawn at the top of the bar and
    # collides with the title.  Put the scale into the axis label instead, and label
    # every tick with the same number of significant digits.
    vmax_abs = max(abs(float(norm.vmin)), abs(float(norm.vmax)), 1e-30)
    exp = int(math.floor(math.log10(vmax_abs))) if vmax_abs > 0 else 0
    scale = 10.0 ** exp
    cbar.formatter = FuncFormatter(lambda v, _pos: f"{v / scale:.2f}")
    cbar.set_label(label + (rf"  ($\times10^{{{exp}}}$)" if exp else ""), fontsize=9)
    cbar.ax.tick_params(labelsize=8, colors="#333333")

    eb = _eb_expression(pmd)
    # The EB expression is in SI metres, not in the display unit.
    eb_field = _eb_field(eb, X_si, Z_si) if eb else None
    if eb_field is not None:
        try:
            ax.contour(X, Z, eb_field, levels=[0.0], colors="white",
                       linewidths=1.15, linestyles="--")
        except Exception:
            pass

    display = shown
    if shown.startswith("rho_") and field != "rho":
        display = rf"$n_{{{_species_tex(field[4:])}}}$"
    elif field == "rho":
        display = r"$\rho$"
    ax.set_title(
        f"{display}   ·   iteration {it}   ·   t = {time * 1e12:.3f} ps\n"
        f"min {data_min:.3g}   max {data_max:.3g}",
        loc="left", fontsize=11, fontweight="bold", color="#111111", pad=8)
    fig.tight_layout()
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out, dpi=150, bbox_inches="tight", facecolor="white")
    plt.close(fig)

    return {
        "ok": True,
        "out": str(out),
        "iteration": it,
        "time": time,
        "field": shown,
        "component": component,
        "range": [data_min, data_max],
        "shape": [int(nx), int(nz)],
    }
