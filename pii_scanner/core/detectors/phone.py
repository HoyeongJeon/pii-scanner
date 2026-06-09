from __future__ import annotations

import re
from collections.abc import Iterator

from pii_scanner.core.detectors.base import Detector
from pii_scanner.core.masking import count_masks
from pii_scanner.core.models import (
    PiiHit, PiiType, RiskLevel, Status, Confidence,
)

_MOBILE = re.compile(
    r"(?<![0-9])(01[016789])[-\s]?([0-9*●■○xX＊]{3,4})[-\s]?(\d{4})(?![0-9])"
)
_LANDLINE = re.compile(
    r"(?<![0-9])(0\d{1,2})[-\s]?(\d{3,4})[-\s]?(\d{4})(?![0-9])"
)


class MobileDetector(Detector):
    pii_type = PiiType.PHONE
    risk = RiskLevel.HIGH

    def find(self, text: str) -> Iterator[PiiHit]:
        for m in _MOBILE.finditer(text):
            head, mid, tail = m.group(1), m.group(2), m.group(3)
            status = Status.MASKED if count_masks(mid) >= 3 else Status.EXPOSED
            snippet = f"{head}-****-{tail}"
            yield PiiHit(
                self.pii_type, status, snippet, m.start(), m.end(),
                Confidence.CONFIRMED, self.risk,
            )


class LandlineDetector(Detector):
    pii_type = PiiType.LANDLINE
    risk = RiskLevel.LOW

    def find(self, text: str) -> Iterator[PiiHit]:
        for m in _LANDLINE.finditer(text):
            head, mid, tail = m.group(1), m.group(2), m.group(3)
            if head.startswith("01") and len(head) == 3:
                continue  # 휴대폰은 MobileDetector 소관
            snippet = f"{head}-***-{tail}"
            yield PiiHit(
                self.pii_type, Status.EXPOSED, snippet, m.start(), m.end(),
                Confidence.PRESUMED, self.risk,
            )
