from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict


class Level(str, Enum):
    ERROR = "ERROR"
    WARNING = "WARNING"
    INFO = "INFO"


LEVEL_ORDER = {Level.ERROR: 0, Level.WARNING: 1, Level.INFO: 2}


@dataclass(frozen=True)
class ValidationResult:
    level: str
    category: str
    message: str
    prim: str
    path: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "level": self.level,
            "category": self.category,
            "message": self.message,
            "prim": self.prim,
            "path": self.path,
        }
