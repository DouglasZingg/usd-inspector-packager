from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from pxr import Usd, UsdShade, Sdf

from usd_tool.models import ValidationResult
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
    p = Path(resolved_path)
    pattern = str(p)

    pattern = pattern.replace("<UDIM>", "*").replace("<udim>", "*")
    pattern = pattern.replace("%(UDIM)d", "*").replace("%(udim)d", "*")
    pattern = pattern.replace("$UDIM", "*").replace("$udim", "*")

    parent = Path(pattern).parent
    name = Path(pattern).name
    if not parent.exists():
        return []
    return list(parent.glob(name))


def _extract_asset_strings(value) -> list[str]:
    if value is None:
        return []

    # Sdf.AssetPath
    if hasattr(value, "path"):
        p = getattr(value, "path", "") or ""
        return [p] if p else []

    # Asset arrays
    if isinstance(value, (list, tuple)):
        out: list[str] = []
        for v in value:
            out.extend(_extract_asset_strings(v))
        return out

    # Sometimes already string
    if isinstance(value, str):
        return [value] if value else []

    return []


def find_texture_assets(stage: Usd.Stage) -> list[TextureHit]:
    root_layer = stage.GetRootLayer()
    hits: list[TextureHit] = []

    for prim in stage.Traverse():
        if not prim.IsA(UsdShade.Shader):
            continue

        shader = UsdShade.Shader(prim)
        shader_path = str(shader.GetPath())

        for inp in shader.GetInputs():
            attr = inp.GetAttr()
            type_name = attr.GetTypeName()
            is_assetish = (type_name == Sdf.ValueTypeNames.Asset) or (type_name == Sdf.ValueTypeNames.AssetArray)

            if not is_assetish:
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

    # de-dupe
    uniq = {}
    for h in hits:
        uniq[(h.shader_path, h.input_name, h.raw_value)] = h
    return list(uniq.values())


def texture_results(stage: Usd.Stage) -> tuple[list[ValidationResult], list[TextureHit]]:
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
