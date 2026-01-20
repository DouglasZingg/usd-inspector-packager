from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from usd_tool.models import ValidationResult


def write_report_json(
    out_path: str,
    source_usd: str,
    results: list[ValidationResult],
    tool_name: str = "USD Inspector & Packager",
    version: str = "0.1.0",
) -> str:
    data: dict[str, Any] = {
        "tool": tool_name,
        "version": version,
        "generated_at": datetime.utcnow().isoformat() + "Z",
        "source_usd": source_usd,
        "results": [r.to_dict() for r in results],
        "counts": {
            "ERROR": sum(1 for r in results if r.level == "ERROR"),
            "WARNING": sum(1 for r in results if r.level == "WARNING"),
            "INFO": sum(1 for r in results if r.level == "INFO"),
        },
    }

    p = Path(out_path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(data, indent=2), encoding="utf-8")
    return str(p)
