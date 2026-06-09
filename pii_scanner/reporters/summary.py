from __future__ import annotations

from dataclasses import dataclass, field

from pii_scanner.core.models import ScanResult, Status, PiiType


@dataclass
class Summary:
    total_files: int = 0
    error_files: int = 0
    exposed: int = 0
    masked: int = 0
    masking_rate: float = 100.0
    by_type: dict = field(default_factory=dict)


def summarize(result: ScanResult) -> Summary:
    s = Summary()
    s.total_files = len(result.files)
    by_type: dict[PiiType, dict[str, int]] = {}
    for fr in result.files:
        if fr.error:
            s.error_files += 1
        for h in fr.hits:
            bucket = by_type.setdefault(h.pii_type, {"exposed": 0, "masked": 0})
            if h.status is Status.EXPOSED:
                s.exposed += 1
                bucket["exposed"] += 1
            else:
                s.masked += 1
                bucket["masked"] += 1
    total = s.exposed + s.masked
    s.masking_rate = 100.0 if total == 0 else s.masked / total * 100.0
    s.by_type = by_type
    return s
