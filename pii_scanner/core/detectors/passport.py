from __future__ import annotations

import re
from collections.abc import Iterator

from pii_scanner.core.detectors.base import Detector
from pii_scanner.core.masking import count_masks, count_digits
from pii_scanner.core.models import (
    PiiHit, PiiType, RiskLevel, Status, Confidence,
)

# 마스킹 문자 — masking.MASK_CHARS 와 동일 셋만 사용(count_masks 판정과 어긋나지 않게).
_MASK = r"\*●■○xX＊"
# 여권 종류 글자(공식): M복수 S단수 R거주 O관용 D외교 T여행증명서.
# 화이트리스트로 접수·관리 코드 오탐(D-034 실측: N111 계열 1,243건·G041 계열 170건 등
# 노출 hit의 89%)을 차단한다. 여권은 체크섬이 없어 항상 추정(PRESUMED) 등급.
_TYPE = "MSRODT"

_PAT = re.compile(
    rf"(?<![A-Za-z0-9{_MASK}])"                                  # 앞에 영숫자/마스킹 금지
    rf"(?:"
    rf"[{_TYPE}][0-9{_MASK}]{{3}}[A-Z{_MASK}][0-9{_MASK}]{{4}}"  # 차세대(2020~) M123A4567
    rf"|"
    rf"[{_TYPE}][0-9{_MASK}]{{8}}"                               # 구형 M12345678
    rf")"
    rf"(?![A-Za-z0-9{_MASK}])"                                   # 뒤에도 금지
)


class PassportDetector(Detector):
    pii_type = PiiType.PASSPORT
    risk = RiskLevel.CRITICAL

    def find(self, text: str) -> Iterator[PiiHit]:
        for m in _PAT.finditer(text):
            token = m.group(0)
            letter, body = token[0], token[1:]
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
