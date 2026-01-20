from __future__ import annotations

from pathlib import Path
from pxr import Sdf


def resolve_asset_path(layer: Sdf.Layer, asset_path: str) -> str:
    if not asset_path:
        return ""

    resolved = Sdf.ComputeAssetPathRelativeToLayer(layer, asset_path)

    try:
        return str(Path(resolved).resolve())
    except Exception:
        return resolved


def path_exists(path_str: str) -> bool:
    if not path_str:
        return False
    try:
        return Path(path_str).exists()
    except Exception:
        return False
