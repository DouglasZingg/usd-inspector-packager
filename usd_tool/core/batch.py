from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from usd_tool.core.loader import open_stage
from usd_tool.core.inspector import scan_stage
from usd_tool.core.packager import package_usd
from usd_tool.models import ValidationResult


USD_EXTS = {".usd", ".usda", ".usdc", ".usdz"}


def _utc_now_z() -> str:
    return datetime.utcnow().isoformat() + "Z"


def find_usd_files(folder: str) -> list[Path]:
    root = Path(folder).resolve()
    if not root.exists() or not root.is_dir():
        raise NotADirectoryError(f"Not a folder: {root}")

    files: list[Path] = []
    for p in root.rglob("*"):
        if p.is_file() and p.suffix.lower() in USD_EXTS:
            files.append(p)

    return sorted(files)


def count_levels(results: list[ValidationResult]) -> dict[str, int]:
    return {
        "ERROR": sum(1 for r in results if r.level == "ERROR"),
        "WARNING": sum(1 for r in results if r.level == "WARNING"),
        "INFO": sum(1 for r in results if r.level == "INFO"),
        "TOTAL": len(results),
    }


def batch_scan(folder: str) -> dict[str, Any]:
    usd_files = find_usd_files(folder)

    per_file: list[dict[str, Any]] = []
    totals = {"ERROR": 0, "WARNING": 0, "INFO": 0, "TOTAL": 0}

    for f in usd_files:
        stage = open_stage(str(f))
        results, deps = scan_stage(stage)
        counts = count_levels(results)

        per_file.append(
            {
                "usd": str(f),
                "counts": counts,
                "deps_found": len(deps),
            }
        )

        for k in ("ERROR", "WARNING", "INFO", "TOTAL"):
            totals[k] += counts[k]

    return {
        "mode": "scan",
        "generated_at": _utc_now_z(),
        "root": str(Path(folder).resolve()),
        "file_count": len(usd_files),
        "totals": totals,
        "files": per_file,
    }


def batch_package(
    folder: str,
    output_root: str,
    *,
    compute_hashes: bool = False,
    portable: bool = False,
    version: str = "0.1.0",
) -> dict[str, Any]:
    usd_files = find_usd_files(folder)

    out_root = Path(output_root).resolve()
    out_root.mkdir(parents=True, exist_ok=True)

    per_file: list[dict[str, Any]] = []
    totals = {
        "files_processed": 0,
        "files_failed": 0,
        "copied_total": 0,
        "missing_total": 0,
    }

    for f in usd_files:
        totals["files_processed"] += 1
        pkg_root = out_root / f"{f.stem}_PACKAGE"

        try:
            # Day 8 returns 5-tuple; Day 7 returns 4-tuple
            result = package_usd(
                str(f),
                str(pkg_root),
                compute_hashes=compute_hashes,
                portable=portable,
                version=version,
            )

            copied = []
            missing = []
            manifest_path = ""
            rewrite_stats = None

            if isinstance(result, tuple) and len(result) == 5:
                copied, _mapping, missing, manifest_path, rewrite_stats = result
            elif isinstance(result, tuple) and len(result) == 4:
                copied, _mapping, missing, manifest_path = result
            else:
                raise RuntimeError(f"Unexpected return from package_usd: {type(result)} {result!r}")

            totals["copied_total"] += len(copied)
            totals["missing_total"] += len(missing)

            per_file.append(
                {
                    "usd": str(f),
                    "package_root": str(pkg_root),
                    "manifest": manifest_path,
                    "copied_count": len(copied),
                    "missing_count": len(missing),
                    "portable": portable,
                    "rewrite_stats": rewrite_stats,
                    "status": "ok",
                }
            )

        except Exception as e:
            totals["files_failed"] += 1
            per_file.append(
                {
                    "usd": str(f),
                    "package_root": str(pkg_root),
                    "status": "failed",
                    "error": str(e),
                }
            )

    return {
        "mode": "package",
        "generated_at": _utc_now_z(),
        "root": str(Path(folder).resolve()),
        "output_root": str(out_root),
        "file_count": len(usd_files),
        "totals": totals,
        "files": per_file,
    }


def write_batch_summary(path: str, summary: dict[str, Any]) -> str:
    p = Path(path).resolve()
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    return str(p)
