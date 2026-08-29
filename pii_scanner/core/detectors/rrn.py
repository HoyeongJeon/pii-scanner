from __future__ import annotations

import datetime
import re
from collections.abc import Iterator

from pii_scanner.core.checksum import rrn_checksum_valid, corp_reg_checksum_valid
from pii_scanner.core.detectors.base import Detector
from pii_scanner.core.masking import (
    count_masks, count_digits, strip_separators, SEPARATOR_CLASS,
)
from pii_scanner.core.models import (
    PiiHit, PiiType, RiskLevel, Status, Confidence,
)

# 6자리(생년월일) + 구분자 + 7자리(성별1 + 일련6) — 숫자 또는 마스킹문자.
# 구분자는 masking.SEPARATOR_CLASS 단일 출처 — 정규식이 매치하는 구분자를 strip_separators 가
# 반드시 지우게 묶어 둔다(어긋나면 길이 검사에서 진짜 번호가 조용히 드롭된다).
_PAT = re.compile(
    rf"(?<![0-9A-Za-z])([0-9*●■○xX＊]{{6}}){SEPARATOR_CLASS}?([0-9*●■○xX＊]{{7}})(?![0-9])"
)
# 이 탐지기가 인정하는 성별코드(숫자일 때)
_GENDER_OK = set("1234")

# 성별코드 → 출생 세기 (윤년 2/29 까지 정확히 보려면 연도가 필요)
_CENTURY = {
    "1": 1900, "2": 1900, "5": 1900, "6": 1900,
    "3": 2000, "4": 2000, "7": 2000, "8": 2000,
    "9": 1800, "0": 1800,
}


def _birthdate_valid(norm: str, reference_year: int) -> bool:
    """앞 6자리(YYMMDD)가 실제 달력 날짜인지, 그리고 미래 출생이 아닌지 검증한다.

    체크섬만으로는 13자리 난수의 약 1/10 이 우연히 통과하므로 불가능한 날짜·미래연도를 거른다.
    앞자리가 가려져(숫자 아님) 검증 불가하면 통과시킨다(과잉 드롭 방지).
    성별코드(7번째)가 숫자일 때만 세기를 신뢰해 미래연도를 판정한다.
    """
    front = norm[:6]
    if not front.isdigit():
        return True
    gender = norm[6] if len(norm) > 6 and norm[6].isdigit() else ""
    century = _CENTURY.get(gender, 2000)
    yy, mm, dd = int(front[:2]), int(front[2:4]), int(front[4:6])
    try:
        datetime.date(century + yy, mm, dd)
    except ValueError:
        return False
    if gender and century + yy > reference_year:   # 미래 출생 → 주민/외국인번호 아님
        return False
    return True


def _snippet(norm: str) -> str:
    """생년월일-성별 + 뒤 6자리 강제 마스킹. 원문 노출 안 함."""
    return f"{norm[:6]}-{norm[6]}{'*' * 6}"


class RrnDetector(Detector):
    pii_type = PiiType.RRN
    risk = RiskLevel.CRITICAL
    _gender_ok = _GENDER_OK
    _confirmable = True   # 체크섬으로 confirm 가능

    def __init__(self, reference_year: int | None = None):
        # reference_year 는 테스트 결정론용 seam — 프로덕션(build_detectors의 무인자 cls())은 실행시점 연도 사용
        self._reference_year = reference_year or datetime.date.today().year

    def find(self, text: str) -> Iterator[PiiHit]:
        for m in _PAT.finditer(text):
            norm = strip_separators(m.group(0))
            if len(norm) != 13:
                continue
            gender = norm[6]
            # 성별코드가 숫자인데 이 타입 소관이 아니면 스킵
            if gender.isdigit() and gender not in self._gender_ok:
                continue
            # 앞 6자리가 실제 날짜가 아니면 주민/외국인등록번호 아님(오탐 제거)
            if not _birthdate_valid(norm, self._reference_year):
                continue
            hit = self._judge(norm, m.start(), m.end())
            if hit is not None:
                yield hit

    def _judge(self, norm: str, start: int, end: int) -> PiiHit | None:
        back = norm[6:]  # 7자리
        corp_suspect = False
        if count_masks(back) >= 6:
            status, conf = Status.MASKED, Confidence.CONFIRMED
        elif count_digits(norm) == 13:
            # 전부 숫자 → 체크섬으로 진위 판정
            if self._confirmable and not rrn_checksum_valid(norm):
                return None  # 주민번호 아님 → 드롭 (오탐 제거)
            status = Status.EXPOSED
            if self._confirmable:
                # RRN 체크섬은 통과했지만 법인 체크섬도 통과하면 법인번호 의심 → 추정 강등 + 마킹
                corp_suspect = corp_reg_checksum_valid(norm)
                conf = Confidence.PRESUMED if corp_suspect else Confidence.CONFIRMED
            else:
                conf = Confidence.PRESUMED
        else:
            # 부분 마스킹이지만 충분히 안 가려짐 → 노출(추정)
            status, conf = Status.EXPOSED, Confidence.PRESUMED
        return PiiHit(
            self.pii_type, status, _snippet(norm), start, end, conf, self.risk,
            corp_suspect=corp_suspect,
        )
