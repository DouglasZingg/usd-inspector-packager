from __future__ import annotations

from pathlib import Path

from usd_tool.core.loader import open_stage
from usd_tool.core.inspector import scan_stage
from usd_tool.models import ValidationResult


USD_EXTS = {".usd", ".usda", ".usdc", ".usdz"}


def find_usd_files(folder: str) -> list[Path]:
    root = Path(folder).resolve()
    if not root.exists() or not root.is_dir():
        raise NotADirectoryError(f"Not a folder: {root}")

    files: list[Path] = []
    for p in root.rglob("*"):
        if p.is_file() and p.suffix.lower() in USD_EXTS:
            files.append(p)

    return sorted(files)


def batch_scan_full(folder: str) -> list[ValidationResult]:
    """
    Returns ALL results for ALL USDs in folder, including a header row per file.
    """
    usd_files = find_usd_files(folder)

    all_results: list[ValidationResult] = []

    for f in usd_files:
        # Add a readable "header" row so results are grouped by file
        all_results.append(
            ValidationResult(
                level="INFO",
                category="Batch",
                message="------------------------------------------------------------",
                prim="",
                path="",
            )
        )
        all_results.append(
            ValidationResult(
                level="INFO",
                category="Batch",
                message=f"FILE: {f.name}",
                prim="",
                path=str(f),
            )
        )

        try:
            stage = open_stage(str(f))
            results, _deps = scan_stage(stage)
            all_results.extend(results)
        except Exception as e:
            all_results.append(
                ValidationResult(
                    level="ERROR",
                    category="Batch",
                    message=f"Failed to scan: {e}",
                    prim="",
                    path=str(f),
                )
            )

    return all_results
