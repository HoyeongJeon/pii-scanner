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
