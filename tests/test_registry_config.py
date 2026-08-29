from pii_scanner.core.detectors import build_detectors, ALL_DETECTOR_KEYS
from pii_scanner.config import ScanConfig
from pii_scanner.core.models import PiiType


def test_default_config_enables_core_detectors():
    cfg = ScanConfig()
    dets = build_detectors(cfg)
    types = {d.pii_type for d in dets}
    assert PiiType.RRN in types
    assert PiiType.PASSPORT in types
    assert PiiType.DRIVER in types
    assert PiiType.PHONE in types
    assert PiiType.EMAIL in types
    assert PiiType.FOREIGN not in types   # 외국인등록번호는 검증 미구현 → 기본 비활성(후순위)


def test_foreign_off_by_default_but_on_when_enabled():
    assert PiiType.FOREIGN not in {d.pii_type for d in build_detectors(ScanConfig())}
    on = build_detectors(ScanConfig(enabled={"foreign"}))
    assert PiiType.FOREIGN in {d.pii_type for d in on}


def test_foreign_still_a_known_key():
    assert "foreign" in ALL_DETECTOR_KEYS   # --enable/--disable 검증 통과해야 하므로


def test_can_disable_detector():
    cfg = ScanConfig(disabled={"email"})
    dets = build_detectors(cfg)
    assert PiiType.EMAIL not in {d.pii_type for d in dets}


def test_all_keys_known():
    assert "rrn" in ALL_DETECTOR_KEYS
    assert "landline" in ALL_DETECTOR_KEYS


# ---------------------------------------------------------------------------
# 리포트가 "무엇을 검사하지 않았는지"를 진술하게 하는 단일 출처.
# 이게 없으면 외국인등록번호처럼 100% 미탐인 종류를 읽는 사람이 검사됐다고 믿는다.
# ---------------------------------------------------------------------------
from pii_scanner.core.detectors import describe_detectors


def test_describe_detectors_flags_foreign_as_not_checked_by_default():
    active, inactive = describe_detectors(ScanConfig())
    assert "외국인등록번호" not in " ".join(active)
    assert inactive == ["외국인등록번호(기본 비활성 — --enable foreign 로 활성화)"]
    assert "주민등록번호" in active


def test_describe_detectors_reports_enabled_foreign_as_checked():
    active, inactive = describe_detectors(ScanConfig(enabled={"foreign"}))
    assert "외국인등록번호" in active
    assert inactive == []


def test_disabled_key_gets_the_right_prescription_not_the_enable_one():
    """--disable 로 끈 것에 '--enable 로 켜세요'라고 안내하면 실행해도 듣지 않는 처방이다."""
    _, inactive = describe_detectors(ScanConfig(disabled={"foreign"}, enabled={"foreign"}))
    assert inactive == ["외국인등록번호(--disable foreign 로 끔)"]
    _, inactive2 = describe_detectors(ScanConfig(disabled={"email"}))
    assert "이메일(--disable email 로 끔)" in inactive2


def test_describe_matches_build_detectors():
    """진술과 실제가 갈리면 리포트가 거짓말을 한다 — 두 함수의 판정이 항상 같아야 한다."""
    from pii_scanner.core.detectors import build_detectors
    for cfg in [ScanConfig(), ScanConfig(enabled={"foreign"}), ScanConfig(disabled={"email"}),
                ScanConfig(disabled={"foreign"}, enabled={"foreign"}),
                ScanConfig(disabled={"rrn", "email"})]:
        active, _ = describe_detectors(cfg)
        assert active == [d.pii_type.value for d in build_detectors(cfg)]
