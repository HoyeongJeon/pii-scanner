from __future__ import annotations

import re
from collections.abc import Iterator

from pii_scanner.core.detectors.base import Detector
from pii_scanner.core.masking import count_masks, count_digits
from pii_scanner.core.models import (
    PiiHit, PiiType, RiskLevel, Status, Confidence,
)

# 영문 대문자 1자 + 8자리(숫자/마스킹). 대문자로 제한해 소문자 토큰
# (코드 식별자·해시 조각 등) 과탐을 줄인다. 여권은 항상 추정(PRESUMED) 등급.
_PAT = re.compile(r"(?<![A-Za-z0-9])([A-Z])([0-9*●■○xX＊]{8})(?![0-9])")


class PassportDetector(Detector):
    pii_type = PiiType.PASSPORT
    risk = RiskLevel.CRITICAL

    def find(self, text: str) -> Iterator[PiiHit]:
        for m in _PAT.finditer(text):
            letter, body = m.group(1), m.group(2)
            if count_digits(body) == 0:
                continue
            if count_masks(body) >= 4:
                status = Status.MASKED
            else:
                status = Status.EXPOSED
            snippet = f"{letter}{body[:3]}{'*' * 5}"
            yield PiiHit(
                self.pii_type, status, snippet, m.start(), m.end(),
                Confidence.PRESUMED, self.risk,
            )
