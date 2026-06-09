from __future__ import annotations

import re
from collections.abc import Iterator

from pii_scanner.core.detectors.base import Detector
from pii_scanner.core.models import (
    PiiHit, PiiType, RiskLevel, Status, Confidence,
)

_PAT = re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}")


def _snippet(addr: str) -> str:
    local, _, domain = addr.partition("@")
    keep = min(2, max(1, len(local) - 1))
    masked = local[:keep] + "*" * min(5, max(1, len(local) - keep))
    return f"{masked}@{domain}"


class EmailDetector(Detector):
    pii_type = PiiType.EMAIL
    risk = RiskLevel.MEDIUM

    def find(self, text: str) -> Iterator[PiiHit]:
        for m in _PAT.finditer(text):
            yield PiiHit(
                self.pii_type, Status.EXPOSED, _snippet(m.group(0)),
                m.start(), m.end(), Confidence.CONFIRMED, self.risk,
            )
