"""Report which optional renderers are importable."""
from __future__ import annotations

import importlib.util


def status() -> dict:
    return {
        "matplotlib": importlib.util.find_spec("matplotlib") is not None,
        "h5py": importlib.util.find_spec("h5py") is not None,
        "yt": importlib.util.find_spec("yt") is not None,
    }
