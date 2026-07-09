from __future__ import annotations

from pii_scanner.core.detectors.rrn import RrnDetector
from pii_scanner.core.detectors.foreign import ForeignDetector
from pii_scanner.core.detectors.passport import PassportDetector
from pii_scanner.core.detectors.driver import DriverDetector
from pii_scanner.core.detectors.phone import MobileDetector, LandlineDetector
from pii_scanner.core.detectors.email import EmailDetector

# 키 → 탐지기 클래스
_REGISTRY = {
    "rrn": RrnDetector,
    "foreign": ForeignDetector,
    "passport": PassportDetector,
    "driver": DriverDetector,
    "phone": MobileDetector,
    "landline": LandlineDetector,
    "email": EmailDetector,
}

ALL_DETECTOR_KEYS = frozenset(_REGISTRY)

# 검증 미구현으로 오탐이 많아 기본 비활성(후순위)인 탐지기 — config.enabled 로만 켜진다.
# 외국인등록번호: 신뢰할 체크섬이 없어 추정 처리 → 과탐. 검증 붙이면 풀 것.
_DEFAULT_OFF = frozenset({"foreign"})


def build_detectors(config) -> list:
    """config.disabled 를 제외하고, 기본 비활성(_DEFAULT_OFF)은 config.enabled 일 때만 포함."""
    enabled = getattr(config, "enabled", None) or frozenset()
    return [
        cls() for key, cls in _REGISTRY.items()
        if key not in config.disabled
        and (key not in _DEFAULT_OFF or key in enabled)
    ]
