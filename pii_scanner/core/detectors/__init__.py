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


def describe_detectors(config) -> tuple[list[str], list[str]]:
    """(검사한 종류, 검사하지 않은 종류와 사유) — 리포트가 커버리지를 진술하게 하는 단일 출처.

    리포트에 "이 종류는 검사하지 않았다"가 없으면 읽는 사람은 검사됐다고 믿는다.
    외국인등록번호가 그랬다 — README 표에 🔴 최상 위험으로 실려 있고 models.KEY_PII_TYPES 에도
    고유식별정보로 들어 있는데, 기본 비활성이라 실제로는 100% 미탐이었고 그 사실이 리포트
    어디에도 없었다. PIPA 고유식별정보 감사에서 이건 문서 버그가 아니라 감사 무결성 문제다.

    사유는 build_detectors 와 같은 우선순위로 판정한다 — --disable 이 기본 비활성보다 앞선다.
    (--disable 로 끈 것에 "--enable 로 켜세요"라고 안내하면 실행해도 듣지 않는 처방이 된다.)
    """
    enabled = getattr(config, "enabled", None) or frozenset()
    active: list[str] = []
    inactive: list[str] = []
    for key, cls in _REGISTRY.items():
        name = cls.pii_type.value
        if key in config.disabled:
            inactive.append(f"{name}(--disable {key} 로 끔)")
        elif key in _DEFAULT_OFF and key not in enabled:
            inactive.append(f"{name}(기본 비활성 — --enable {key} 로 활성화)")
        else:
            active.append(name)
    return active, inactive


def build_detectors(config) -> list:
    """config.disabled 를 제외하고, 기본 비활성(_DEFAULT_OFF)은 config.enabled 일 때만 포함."""
    enabled = getattr(config, "enabled", None) or frozenset()
    return [
        cls() for key, cls in _REGISTRY.items()
        if key not in config.disabled
        and (key not in _DEFAULT_OFF or key in enabled)
    ]
