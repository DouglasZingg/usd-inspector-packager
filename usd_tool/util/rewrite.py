from __future__ import annotations

from pathlib import Path
from typing import Dict, Optional

from pxr import Sdf, Usd, UsdShade

from usd_tool.util.paths import resolve_asset_path


def _to_posix(rel: str) -> str:
    return rel.replace("\\", "/")


def _dst_rel_for_src_abs(src_abs: str, mapping: Dict[str, str]) -> Optional[str]:
    return mapping.get(src_abs)


def _rewrite_layer_sublayers(layer: Sdf.Layer, mapping: Dict[str, str]) -> int:
    changed = 0
    new_paths: list[str] = []

    for authored in list(layer.subLayerPaths):
        resolved = resolve_asset_path(layer, authored)
        src_abs = str(Path(resolved).resolve())
        dst_rel = _dst_rel_for_src_abs(src_abs, mapping)

        if dst_rel:
            new_paths.append(_to_posix(dst_rel))
            changed += 1
        else:
            new_paths.append(authored)

    if changed:
        layer.subLayerPaths = new_paths

    return changed


def _listop_items(listop) -> list:
    if not listop:
        return []

    for method_name in ("GetAddedOrExplicitItems", "GetExplicitItems"):
        fn = getattr(listop, method_name, None)
        if callable(fn):
            try:
                return list(fn())
            except Exception:
                pass

    for attr_name in ("addedItems", "explicitItems"):
        items = getattr(listop, attr_name, None)
        if items:
            try:
                return list(items)
            except Exception:
                pass

    return []


def _rewrite_refs_or_payloads(stage: Usd.Stage, mapping: Dict[str, str], meta_name: str) -> int:
    """
    meta_name: "references" or "payloads"
    """
    changed = 0
    root_layer = stage.GetRootLayer()

    for prim in stage.Traverse():
        listop = prim.GetMetadata(meta_name)
        items = _listop_items(listop)
        if not items:
            continue

        new_items = []
        local_changed = False

        for it in items:
            asset_path = getattr(it, "assetPath", "") or ""
            if not asset_path:
                new_items.append(it)
                continue

            resolved = resolve_asset_path(root_layer, asset_path)
            src_abs = str(Path(resolved).resolve())
            dst_rel = _dst_rel_for_src_abs(src_abs, mapping)

            if not dst_rel:
                new_items.append(it)
                continue

            prim_path = getattr(it, "primPath", None)
            layer_offset = getattr(it, "layerOffset", None)

            if meta_name == "references":
                ref = Sdf.Reference(_to_posix(dst_rel), prim_path) if prim_path else Sdf.Reference(_to_posix(dst_rel))
                if layer_offset is not None:
                    ref.layerOffset = layer_offset
                new_items.append(ref)
            else:
                pl = Sdf.Payload(_to_posix(dst_rel), prim_path) if prim_path else Sdf.Payload(_to_posix(dst_rel))
                if layer_offset is not None:
                    pl.layerOffset = layer_offset
                new_items.append(pl)

            local_changed = True
            changed += 1

        if local_changed:
            if meta_name == "references":
                prim.GetReferences().ClearReferences()
                for ref in new_items:
                    prim.GetReferences().AddReference(ref)
            else:
                prim.GetPayloads().ClearPayloads()
                for pl in new_items:
                    prim.GetPayloads().AddPayload(pl)

    return changed


def _rewrite_shader_asset_inputs(stage: Usd.Stage, mapping: Dict[str, str]) -> int:
    changed = 0
    root_layer = stage.GetRootLayer()

    for prim in stage.Traverse():
        if not prim.IsA(UsdShade.Shader):
            continue

        shader = UsdShade.Shader(prim)
        for inp in shader.GetInputs():
            attr = inp.GetAttr()
            if attr.GetTypeName() != Sdf.ValueTypeNames.Asset:
                continue

            val = attr.Get()
            if not val or not hasattr(val, "path"):
                continue

            authored = val.path
            if not authored:
                continue

            resolved = resolve_asset_path(root_layer, authored)
            src_abs = str(Path(resolved).resolve())
            dst_rel = _dst_rel_for_src_abs(src_abs, mapping)
            if not dst_rel:
                continue

            attr.Set(Sdf.AssetPath(_to_posix(dst_rel)))
            changed += 1

    return changed


def rewrite_paths_in_packaged_usd(
    packaged_usd_path: str,
    package_root: str,
    mapping: Dict[str, str],
) -> dict[str, int]:
    """
    Rewrites:
      - root layer subLayerPaths
      - prim references
      - prim payloads
      - asset-typed shader inputs (textures)

    mapping keys MUST be absolute source paths, mapping values are packaged relative paths.
    """
    pkg_usd = Path(packaged_usd_path).resolve()
    if not pkg_usd.exists():
        raise FileNotFoundError(f"Packaged USD not found: {pkg_usd}")

    stage = Usd.Stage.Open(str(pkg_usd))
    if stage is None:
        raise RuntimeError(f"Failed to open packaged USD for rewrite: {pkg_usd}")

    root_layer = stage.GetRootLayer()

    stats = {"sublayers": 0, "references": 0, "payloads": 0, "textures": 0}

    stats["sublayers"] += _rewrite_layer_sublayers(root_layer, mapping)
    stats["references"] += _rewrite_refs_or_payloads(stage, mapping, "references")
    stats["payloads"] += _rewrite_refs_or_payloads(stage, mapping, "payloads")
    stats["textures"] += _rewrite_shader_asset_inputs(stage, mapping)

    root_layer.Save()
    return stats
