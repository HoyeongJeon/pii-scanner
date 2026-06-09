from __future__ import annotations

import re
from collections.abc import Iterator

from pii_scanner.core.checksum import rrn_checksum_valid
from pii_scanner.core.detectors.base import Detector
from pii_scanner.core.masking import count_masks, count_digits, strip_separators
from pii_scanner.core.models import (
    PiiHit, PiiType, RiskLevel, Status, Confidence,
)

# 6자리(생년월일) + 구분자 + 7자리(성별1 + 일련6) — 숫자 또는 마스킹문자
_PAT = re.compile(
    r"(?<![0-9A-Za-z])([0-9*●■○xX＊]{6})[-\s]?([0-9*●■○xX＊]{7})(?![0-9])"
)
# 이 탐지기가 인정하는 성별코드(숫자일 때)
_GENDER_OK = set("1234")


def _snippet(norm: str) -> str:
    """생년월일-성별 + 뒤 6자리 강제 마스킹. 원문 노출 안 함."""
    return f"{norm[:6]}-{norm[6]}{'*' * 6}"


class RrnDetector(Detector):
    pii_type = PiiType.RRN
    risk = RiskLevel.CRITICAL
    _gender_ok = _GENDER_OK
    _confirmable = True   # 체크섬으로 confirm 가능

    def find(self, text: str) -> Iterator[PiiHit]:
        for m in _PAT.finditer(text):
            norm = strip_separators(m.group(0))
            if len(norm) != 13:
                continue
            gender = norm[6]
            # 성별코드가 숫자인데 이 타입 소관이 아니면 스킵
            if gender.isdigit() and gender not in self._gender_ok:
                continue
            hit = self._judge(norm, m.start(), m.end())
            if hit is not None:
                yield hit

    def _judge(self, norm: str, start: int, end: int) -> PiiHit | None:
        back = norm[6:]  # 7자리
        if count_masks(back) >= 6:
            status, conf = Status.MASKED, Confidence.CONFIRMED
        elif count_digits(norm) == 13:
            # 전부 숫자 → 체크섬으로 진위 판정
            if self._confirmable and not rrn_checksum_valid(norm):
                return None  # 주민번호 아님 → 드롭 (오탐 제거)
            status = Status.EXPOSED
            conf = Confidence.CONFIRMED if self._confirmable else Confidence.PRESUMED
        else:
            # 부분 마스킹이지만 충분히 안 가려짐 → 노출(추정)
            status, conf = Status.EXPOSED, Confidence.PRESUMED
        return PiiHit(
            self.pii_type, status, _snippet(norm), start, end, conf, self.risk
        )
