from __future__ import annotations

from dataclasses import dataclass

from pxr import Usd, Sdf

from usd_tool.models import ValidationResult
from usd_tool.util.paths import resolve_asset_path, path_exists
from usd_tool.core.textures import texture_results


@dataclass(frozen=True)
class Dependency:
    dep_type: str  # "layer" | "reference" | "payload"
    asset_path: str
    resolved_path: str
    prim_path: str = ""


def _listop_items(listop) -> list:
    if listop is None:
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


def _scan_layers(root_layer: Sdf.Layer) -> list[Dependency]:
    deps: list[Dependency] = []

    deps.append(
        Dependency(
            dep_type="layer",
            asset_path=root_layer.identifier,
            resolved_path=root_layer.realPath or root_layer.identifier,
            prim_path="",
        )
    )

    for p in list(root_layer.subLayerPaths):
        resolved = resolve_asset_path(root_layer, p)
        deps.append(Dependency(dep_type="layer", asset_path=p, resolved_path=resolved, prim_path=""))

    return deps


def _scan_prim_references_and_payloads(stage: Usd.Stage) -> list[Dependency]:
    deps: list[Dependency] = []
    root_layer = stage.GetRootLayer()

    for prim in stage.Traverse():
        prim_path = str(prim.GetPath())

        # References
        refs_listop = prim.GetMetadata("references")
        for ref in _listop_items(refs_listop):
            asset_path = getattr(ref, "assetPath", "") or ""
            if asset_path:
                resolved = resolve_asset_path(root_layer, asset_path)
                deps.append(
                    Dependency(
                        dep_type="reference",
                        asset_path=asset_path,
                        resolved_path=resolved,
                        prim_path=prim_path,
                    )
                )

        # Payloads (some builds use payloads vs payload)
        payload_listop = prim.GetMetadata("payloads")
        if payload_listop is None:
            payload_listop = prim.GetMetadata("payload")

        for pl in _listop_items(payload_listop):
            asset_path = getattr(pl, "assetPath", "") or ""
            if asset_path:
                resolved = resolve_asset_path(root_layer, asset_path)
                deps.append(
                    Dependency(
                        dep_type="payload",
                        asset_path=asset_path,
                        resolved_path=resolved,
                        prim_path=prim_path,
                    )
                )

    return deps


def scan_stage(stage: Usd.Stage) -> tuple[list[ValidationResult], list[Dependency]]:
    root_layer = stage.GetRootLayer()

    deps: list[Dependency] = []
    deps.extend(_scan_layers(root_layer))
    deps.extend(_scan_prim_references_and_payloads(stage))

    # De-dupe deps
    uniq = {}
    for d in deps:
        uniq[(d.dep_type, d.resolved_path, d.prim_path, d.asset_path)] = d
    deps = list(uniq.values())

    results: list[ValidationResult] = []

    results.append(
        ValidationResult(
            level="INFO",
            category="Stage",
            message="USD stage opened successfully.",
            prim="/",
            path=root_layer.realPath or root_layer.identifier,
        )
    )

    # Validate deps
    for d in deps:
        category = "Layers" if d.dep_type == "layer" else ("References" if d.dep_type == "reference" else "Payloads")
        prim = d.prim_path or ""
        display_path = d.asset_path

        if d.dep_type == "layer" and (d.resolved_path == "" or d.resolved_path.startswith("anon:")):
            results.append(
                ValidationResult(
                    level="INFO",
                    category=category,
                    message="Anonymous/in-memory layer.",
                    prim=prim,
                    path=display_path,
                )
            )
            continue

        if not path_exists(d.resolved_path):
            results.append(
                ValidationResult(
                    level="ERROR",
                    category=category,
                    message="Missing dependency on disk.",
                    prim=prim,
                    path=display_path,
                )
            )
        else:
            results.append(
                ValidationResult(
                    level="INFO",
                    category=category,
                    message="Dependency found.",
                    prim=prim,
                    path=display_path,
                )
            )

    # Textures (Day 4)
    tex_results, _ = texture_results(stage)
    results.extend(tex_results)

    return results, deps
