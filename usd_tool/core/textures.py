from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from pxr import Usd, UsdShade, Sdf

from usd_tool.util.paths import resolve_asset_path, path_exists


@dataclass(frozen=True)
class TextureHit:
    shader_path: str
    input_name: str
    raw_value: str
    resolved_path: str


def _is_udim_pattern(s: str) -> bool:
    s_up = s.upper()
    return "<UDIM>" in s_up or "%(UDIM)" in s_up or "$UDIM" in s_up


def _udim_glob_candidates(resolved_path: str) -> list[Path]:
    """
    If resolved_path contains a UDIM token, replace it with * and glob.
    Example: C:/tex/diffuse.<UDIM>.exr -> C:/tex/diffuse.*.exr
    """
    p = Path(resolved_path)
    pattern = str(p)

    pattern = pattern.replace("<UDIM>", "*").replace("<udim>", "*")
    pattern = pattern.replace("%(UDIM)d", "*").replace("%(udim)d", "*")
    pattern = pattern.replace("$UDIM", "*").replace("$udim", "*")

    # Glob must happen in parent folder
    parent = Path(pattern).parent
    name = Path(pattern).name
    if not parent.exists():
        return []
    return list(parent.glob(name))


def _extract_asset_strings(value) -> list[str]:
    """
    Handles:
      - Sdf.AssetPath
      - list/tuple of Sdf.AssetPath (asset arrays)
      - plain string
    Returns string asset paths (as authored).
    """
    if value is None:
        return []

    # Sdf.AssetPath
    if hasattr(value, "path"):
        p = getattr(value, "path", "") or ""
        return [p] if p else []

    # Asset arrays can come through as list of Sdf.AssetPath
    if isinstance(value, (list, tuple)):
        out = []
        for v in value:
            out.extend(_extract_asset_strings(v))
        return out

    # Sometimes it’s already a string
    if isinstance(value, str):
        return [value] if value else []

    return []


def find_texture_assets(stage: Usd.Stage) -> list[TextureHit]:
    """
    Traverses all UsdShade shaders and collects asset-valued inputs.
    This catches the common patterns:
      - UsdUVTexture inputs like "file"
      - RenderMan/HdStorm variations ("filename", etc.)
    """
    root_layer = stage.GetRootLayer()
    hits: list[TextureHit] = []

    for prim in stage.Traverse():
        if not prim.IsA(UsdShade.Shader):
            continue

        shader = UsdShade.Shader(prim)
        shader_path = str(shader.GetPath())

        for inp in shader.GetInputs():
            # Only consider asset/asset-array typed inputs
            attr = inp.GetAttr()
            type_name = attr.GetTypeName()
            is_assetish = (type_name == Sdf.ValueTypeNames.Asset) or (type_name == Sdf.ValueTypeNames.AssetArray)

            if not is_assetish:
                # Many networks still store file paths as asset types; if not, skip for Day 4
                continue

            val = attr.Get()
            for raw in _extract_asset_strings(val):
                if not raw:
                    continue

                resolved = resolve_asset_path(root_layer, raw)
                hits.append(
                    TextureHit(
                        shader_path=shader_path,
                        input_name=inp.GetBaseName(),
                        raw_value=raw,
                        resolved_path=resolved,
                    )
                )

    # De-dupe
    uniq = {}
    for h in hits:
        key = (h.shader_path, h.input_name, h.raw_value)
        uniq[key] = h

    return list(uniq.values())


def texture_results(stage: Usd.Stage):
    """
    Returns:
      (validation_results, texture_paths)
    """
    from usd_tool.core.inspector import ValidationResult  # local import to avoid circulars

    results: list[ValidationResult] = []
    hits = find_texture_assets(stage)

    if not hits:
        results.append(
            ValidationResult(
                level="INFO",
                category="Textures",
                message="No asset-typed texture inputs found (UsdShade).",
                prim="",
                path="",
            )
        )
        return results, hits

    for h in hits:
        # UDIM special case
        if _is_udim_pattern(h.raw_value):
            candidates = _udim_glob_candidates(h.resolved_path)
            if candidates:
                results.append(
                    ValidationResult(
                        level="INFO",
                        category="Textures",
                        message=f"UDIM texture set found ({len(candidates)} tiles). {h.input_name} @ {h.shader_path}",
                        prim=h.shader_path,
                        path=h.raw_value,
                    )
                )
            else:
                results.append(
                    ValidationResult(
                        level="ERROR",
                        category="Textures",
                        message=f"Missing UDIM texture tiles. {h.input_name} @ {h.shader_path}",
                        prim=h.shader_path,
                        path=h.raw_value,
                    )
                )
            continue

        if path_exists(h.resolved_path):
            results.append(
                ValidationResult(
                    level="INFO",
                    category="Textures",
                    message=f"Texture found. {h.input_name} @ {h.shader_path}",
                    prim=h.shader_path,
                    path=h.raw_value,
                )
            )
        else:
            results.append(
                ValidationResult(
                    level="ERROR",
                    category="Textures",
                    message=f"Missing texture on disk. {h.input_name} @ {h.shader_path}",
                    prim=h.shader_path,
                    path=h.raw_value,
                )
            )

    return results, hits
