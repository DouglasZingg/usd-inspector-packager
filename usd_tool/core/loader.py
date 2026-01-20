from __future__ import annotations

from pathlib import Path
from pxr import Usd


def open_stage(usd_path: str) -> Usd.Stage:
    p = Path(usd_path).resolve()
    if not p.exists():
        raise FileNotFoundError(f"USD file not found: {p}")

    stage = Usd.Stage.Open(str(p))
    if stage is None:
        raise RuntimeError(f"Usd.Stage.Open failed: {p}")

    return stage
