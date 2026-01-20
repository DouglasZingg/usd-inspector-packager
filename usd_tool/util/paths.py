from __future__ import annotations

from pathlib import Path

from pxr import Sdf


def resolve_asset_path(layer: Sdf.Layer, asset_path: str) -> str:
    """
    Resolve an asset path string relative to a given Sdf.Layer.

    - If asset_path is relative, compute a layer-relative absolute-ish path.
    - Returns a normalized string path.
    """
    if not asset_path:
        return ""

    # Sdf helper handles relative paths relative to the layer identifier
    resolved = Sdf.ComputeAssetPathRelativeToLayer(layer, asset_path)

    # Normalize for display/exists checks
    try:
        return str(Path(resolved).resolve())
    except Exception:
        # If it's not a normal filesystem path, just return as-is
        return resolved


def path_exists(path_str: str) -> bool:
    if not path_str:
        return False
    try:
        return Path(path_str).exists()
    except Exception:
        return False
