from __future__ import annotations

import json
import shutil
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from usd_tool.core.loader import open_stage
from usd_tool.core.inspector import scan_stage
from usd_tool.core.textures import find_texture_assets
from usd_tool.util.hashing import sha256_file


@dataclass(frozen=True)
class CopiedFile:
    src: str
    dst: str
    dst_rel: str
    file_type: str  # "usd" | "texture" | "dep"
    size_bytes: int
    sha256: str | None = None


@dataclass(frozen=True)
class MissingFile:
    category: str
    src: str
    resolved: str


def _safe_mkdir(p: Path) -> None:
    p.mkdir(parents=True, exist_ok=True)


def _utc_now_z() -> str:
    return datetime.utcnow().isoformat() + "Z"


def _choose_unique_name(dest_dir: Path, filename: str) -> str:
    base = Path(filename).stem
    ext = Path(filename).suffix
    candidate = dest_dir / (base + ext)
    if not candidate.exists():
        return candidate.name

    i = 1
    while True:
        name = f"{base}_{i:03d}{ext}"
        candidate = dest_dir / name
        if not candidate.exists():
            return name
        i += 1


def _copy_file(src: Path, dst_dir: Path) -> Path:
    _safe_mkdir(dst_dir)
    name = _choose_unique_name(dst_dir, src.name)
    dst = dst_dir / name
    shutil.copy2(str(src), str(dst))
    return dst


def _classify_dep_path(path_str: str) -> str:
    ext = Path(path_str).suffix.lower()
    if ext in (".usd", ".usda", ".usdc", ".usdz"):
        return "usd"
    return "dep"


def _write_manifest_json(
    package_root: Path,
    source_usd: Path,
    copied: list[CopiedFile],
    missing: list[MissingFile],
    tool_name: str,
    version: str,
) -> Path:
    manifest: dict[str, Any] = {
        "tool": tool_name,
        "version": version,
        "generated_at": _utc_now_z(),
        "source_usd": str(source_usd),
        "package_root": str(package_root),
        "copied_files": [
            {
                "src": c.src,
                "dst": c.dst_rel,
                "type": c.file_type,
                "size_bytes": c.size_bytes,
                **({"sha256": c.sha256} if c.sha256 else {}),
            }
            for c in copied
        ],
        "missing_files": [
            {"category": m.category, "src": m.src, "resolved": m.resolved}
            for m in missing
        ],
        "counts": {
            "copied": len(copied),
            "missing": len(missing),
            "by_type": {
                "usd": sum(1 for c in copied if c.file_type == "usd"),
                "texture": sum(1 for c in copied if c.file_type == "texture"),
                "dep": sum(1 for c in copied if c.file_type == "dep"),
            },
        },
    }

    out_path = package_root / "manifest.json"
    out_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return out_path


def package_usd(
    source_usd: str,
    output_root: str,
    *,
    compute_hashes: bool = False,
    tool_name: str = "USD Inspector & Packager",
    version: str = "0.1.0",
) -> tuple[list[CopiedFile], dict[str, str], list[MissingFile], str]:
    """
    Returns:
      copied_files, mapping(src_abs->dst_rel), missing_files, manifest_path
    """
    src_path = Path(source_usd).resolve()
    out_root = Path(output_root).resolve()

    usd_dir = out_root / "usd"
    tex_dir = out_root / "textures"
    dep_dir = out_root / "deps"

    _safe_mkdir(out_root)
    _safe_mkdir(usd_dir)
    _safe_mkdir(tex_dir)
    _safe_mkdir(dep_dir)

    stage = open_stage(str(src_path))
    _results, deps = scan_stage(stage)
    tex_hits = find_texture_assets(stage)

    copied: list[CopiedFile] = []
    mapping: dict[str, str] = {}
    missing: list[MissingFile] = []

    def record_copy(src_abs: Path, dst_abs: Path, file_type: str) -> None:
        dst_rel = str(dst_abs.relative_to(out_root))
        size = dst_abs.stat().st_size if dst_abs.exists() else 0
        digest = sha256_file(str(dst_abs)) if (compute_hashes and dst_abs.exists()) else None

        copied.append(
            CopiedFile(
                src=str(src_abs),
                dst=str(dst_abs),
                dst_rel=dst_rel,
                file_type=file_type,
                size_bytes=size,
                sha256=digest,
            )
        )
        mapping[str(src_abs)] = dst_rel

    # Copy root USD
    if not src_path.exists():
        raise FileNotFoundError(f"USD file not found: {src_path}")
    dst_root = _copy_file(src_path, usd_dir)
    record_copy(src_path, dst_root, "usd")

    # Copy deps
    for d in deps:
        if not d.resolved_path:
            continue
        try:
            abs_src = Path(d.resolved_path).resolve()
        except Exception:
            continue

        if str(abs_src) == str(src_path):
            continue

        if not abs_src.exists():
            category = "Layers" if d.dep_type == "layer" else ("References" if d.dep_type == "reference" else "Payloads")
            missing.append(MissingFile(category=category, src=d.asset_path, resolved=str(abs_src)))
            continue

        ftype = _classify_dep_path(str(abs_src))
        target_dir = usd_dir if ftype == "usd" else dep_dir
        dst = _copy_file(abs_src, target_dir)
        record_copy(abs_src, dst, ftype)

    # Copy textures
    for h in tex_hits:
        try:
            abs_tex = Path(h.resolved_path).resolve()
        except Exception:
            continue

        if not abs_tex.exists():
            missing.append(MissingFile(category="Textures", src=h.raw_value, resolved=str(abs_tex)))
            continue

        dst = _copy_file(abs_tex, tex_dir)
        record_copy(abs_tex, dst, "texture")

    manifest_path = _write_manifest_json(
        package_root=out_root,
        source_usd=src_path,
        copied=copied,
        missing=missing,
        tool_name=tool_name,
        version=version,
    )

    #Critical: ALWAYS return the 4-tuple
    return copied, mapping, missing, str(manifest_path)
