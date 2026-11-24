"""Command-line entry point for the standalone WarpX Studio."""
from __future__ import annotations

import argparse
import os
import threading
import webbrowser


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="warpx-studio",
                                     description="Standalone WarpX simulation studio")
    parser.add_argument("--root", help="WarpX source checkout (official or fork)")
    parser.add_argument("--binary", help="explicit WarpX executable")
    parser.add_argument("--profile", choices=["official", "fork"], help="label/override binary family")
    parser.add_argument("--data", help="writable data root (projects/runs/builds)")
    parser.add_argument("--projects", help="project directory override")
    parser.add_argument("--runs", help="run output directory override")
    parser.add_argument("--pvpython", help="ParaView pvpython for 3-D/particles/VTK (optional)")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8770)
    parser.add_argument("--no-browser", action="store_true")
    args = parser.parse_args(argv)

    # uvicorn imports the app module in this process; set configuration first.
    env = {
        "WARPX_STUDIO_WARPX_ROOT": args.root,
        "WARPX_STUDIO_BINARY": args.binary,
        "WARPX_STUDIO_PROFILE": args.profile,
        "WARPX_STUDIO_DATA": args.data,
        "WARPX_STUDIO_PROJECTS": args.projects,
        "WARPX_STUDIO_RUNS": args.runs,
        "WARPX_STUDIO_PVPYTHON": args.pvpython,
    }
    for key, value in env.items():
        if value:
            os.environ[key] = value

    import uvicorn
    if not args.no_browser:
        url = f"http://{args.host}:{args.port}"
        threading.Timer(1.2, lambda: webbrowser.open(url)).start()
    uvicorn.run("warpx_studio.web.app:app", host=args.host, port=args.port,
                log_level="info")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
