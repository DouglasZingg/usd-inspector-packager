from __future__ import annotations

import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Tuple

from usd_tool.core.loader import open_stage
from usd_tool.core.inspector import scan_stage, Dependency
from usd_tool.core.textures import find_texture_assets, TextureHit


@dataclass(frozen=True)
class CopiedFile:
    src: str
    dst: str
    file_type: str  # "usd" | "texture" | "dep"


def _safe_mkdir(p: Path) -> None:
    p.mkdir(parents=True, exist_ok=True)


def _choose_unique_name(dest_dir: Path, filename: str) -> str:
    """
    If filename exists, append _001, _002, ...
    """
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

    # Keep original name if possible, else uniquify
    name = _choose_unique_name(dst_dir, src.name)
    dst = dst_dir / name

    shutil.copy2(str(src), str(dst))
    return dst


def _classify_dep_path(path_str: str) -> str:
    ext = Path(path_str).suffix.lower()
    if ext in (".usd", ".usda", ".usdc", ".usdz"):
        return "usd"
    return "dep"


def package_usd(
    source_usd: str,
    output_root: str,
) -> tuple[list[CopiedFile], dict[str, str]]:
    """
    Returns:
      copied_files: list of CopiedFile
      mapping: {src_abs: dst_rel}
    """
    src_path = Path(source_usd).resolve()
    out_root = Path(output_root).resolve()

    # Package layout
    usd_dir = out_root / "usd"
    tex_dir = out_root / "textures"
    dep_dir = out_root / "deps"

    _safe_mkdir(out_root)
    _safe_mkdir(usd_dir)
    _safe_mkdir(tex_dir)
    _safe_mkdir(dep_dir)

    stage = open_stage(str(src_path))

    results, deps = scan_stage(stage)  # deps includes layers/refs/payloads
    tex_hits = find_texture_assets(stage)

    copied: list[CopiedFile] = []
    mapping: dict[str, str] = {}  # abs src -> relative dst (from out_root)

    # 1) Copy root USD into /usd/
    dst_root = _copy_file(src_path, usd_dir)
    copied.append(CopiedFile(src=str(src_path), dst=str(dst_root), file_type="usd"))
    mapping[str(src_path)] = str(dst_root.relative_to(out_root))

    # 2) Copy dependency USD/dep files
    for d in deps:
        # skip root layer (already copied) if same path
        abs_src = Path(d.resolved_path).resolve() if d.resolved_path else None
        if abs_src is None:
            continue
        if not abs_src.exists():
            continue
        if str(abs_src) == str(src_path):
            continue

        ftype = _classify_dep_path(str(abs_src))
        target_dir = usd_dir if ftype == "usd" else dep_dir
        dst = _copy_file(abs_src, target_dir)

        copied.append(CopiedFile(src=str(abs_src), dst=str(dst), file_type=ftype))
        mapping[str(abs_src)] = str(dst.relative_to(out_root))

    # 3) Copy textures into /textures/
    for h in tex_hits:
        abs_tex = Path(h.resolved_path).resolve()
        if not abs_tex.exists():
            continue
        dst = _copy_file(abs_tex, tex_dir)

        copied.append(CopiedFile(src=str(abs_tex), dst=str(dst), file_type="texture"))
        mapping[str(abs_tex)] = str(dst.relative_to(out_root))

    return copied, mapping
