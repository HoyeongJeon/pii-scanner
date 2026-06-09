from __future__ import annotations

from pii_scanner.core.detectors.rrn import RrnDetector
from pii_scanner.core.models import PiiType


class ForeignDetector(RrnDetector):
    pii_type = PiiType.FOREIGN
    _gender_ok = set("5678")
    _confirmable = False   # 체크섬 신뢰 불가 → 드롭 안 함, 추정 처리
