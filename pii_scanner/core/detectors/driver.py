from __future__ import annotations

import re
from collections.abc import Iterator

from pii_scanner.core.detectors.base import Detector
from pii_scanner.core.masking import count_masks, strip_separators
from pii_scanner.core.models import (
    PiiHit, PiiType, RiskLevel, Status, Confidence,
)

# 2-2-6-2 (지역2 연도2 일련6 검증2), 숫자/마스킹.
# 구분자(-, 공백)를 "필수"로 둬서 평범한 12자리 숫자열(주문번호·계좌·타임스탬프)을
# 운전면허로 오탐하지 않게 한다. 운전면허는 항상 추정(PRESUMED) 등급.
_PAT = re.compile(
    r"(?<![0-9A-Za-z])([0-9*●■○xX＊]{2})[-\s]([0-9*●■○xX＊]{2})[-\s]"
    r"([0-9*●■○xX＊]{6})[-\s]([0-9*●■○xX＊]{2})(?![0-9])"
)


class DriverDetector(Detector):
    pii_type = PiiType.DRIVER
    risk = RiskLevel.CRITICAL

    def find(self, text: str) -> Iterator[PiiHit]:
        for m in _PAT.finditer(text):
            norm = strip_separators(m.group(0))
            if len(norm) != 12:
                continue
            status = Status.MASKED if count_masks(norm) >= 6 else Status.EXPOSED
            snippet = f"{norm[:4]}-{'*' * 6}-**"
            yield PiiHit(
                self.pii_type, status, snippet, m.start(), m.end(),
                Confidence.PRESUMED, self.risk,
            )
