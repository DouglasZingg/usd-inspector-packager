from __future__ import annotations

import os
import sys
from pathlib import Path


def try_import_pxr():
    try:
        from pxr import Usd, Sdf  # type: ignore
        return Usd, Sdf, None
    except Exception as e:
        return None, None, e


def print_stage_info(usd_path: Path) -> int:
    Usd, Sdf, err = try_import_pxr()
    if err is not None:
        print("ERROR: Failed to import OpenUSD Python bindings (pxr).")
        print(f"Exception: {err!r}\n")
        print("What to do next (common fixes):")
        print("1) Confirm you are using the Python that ships with your USD install, OR")
        print("2) Add USD's Python bindings to PYTHONPATH, OR")
        print("3) Install a platform build of OpenUSD that includes Python bindings.\n")
        print("Quick debug info:")
        print(f"  sys.executable: {sys.executable}")
        print(f"  sys.version:    {sys.version.split()[0]}")
        print(f"  PYTHONPATH:     {os.environ.get('PYTHONPATH', '')}")
        return 2

    usd_path = usd_path.resolve()
    if not usd_path.exists():
        print(f"ERROR: File not found: {usd_path}")
        return 1

    stage = Usd.Stage.Open(str(usd_path))
    if stage is None:
        print(f"ERROR: Usd.Stage.Open failed: {usd_path}")
        return 1

    root_layer = stage.GetRootLayer()
    print("=== USD LOAD OK ===")
    print(f"Input:         {usd_path}")
    print(f"Root layer id: {root_layer.identifier}")
    print(f"Root real path:{root_layer.realPath}")
    print(f"Format:        {root_layer.GetFileFormat().formatId}")

    # Sublayers
    sublayers = list(root_layer.subLayerPaths)
    print("\n--- Sublayers (root layer) ---")
    if not sublayers:
        print("(none)")
    else:
        for i, p in enumerate(sublayers, start=1):
            print(f"{i:02d}. {p}")

    # Simple stage stats
    prim_count = sum(1 for _ in stage.Traverse())
    default_prim = stage.GetDefaultPrim()
    print("\n--- Stage Stats ---")
    print(f"Default prim:  {default_prim.GetPath() if default_prim else '(none)'}")
    print(f"Prim count:    {prim_count}")

    return 0


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        print("Usage:")
        print("  python main.py <path-to.usd/.usda/.usdc/.usdz>")
        return 1

    usd_path = Path(argv[1])
    return print_stage_info(usd_path)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
