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


def build_detectors(config) -> list:
    """config.disabled 를 제외한 탐지기 인스턴스 목록."""
    return [
        cls() for key, cls in _REGISTRY.items()
        if key not in config.disabled
    ]
