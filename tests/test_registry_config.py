from pii_scanner.core.detectors import build_detectors, ALL_DETECTOR_KEYS
from pii_scanner.config import ScanConfig
from pii_scanner.core.models import PiiType


def test_default_config_enables_core_detectors():
    cfg = ScanConfig()
    dets = build_detectors(cfg)
    types = {d.pii_type for d in dets}
    assert PiiType.RRN in types
    assert PiiType.FOREIGN in types
    assert PiiType.PASSPORT in types
    assert PiiType.DRIVER in types
    assert PiiType.PHONE in types
    assert PiiType.EMAIL in types


def test_can_disable_detector():
    cfg = ScanConfig(disabled={"email"})
    dets = build_detectors(cfg)
    assert PiiType.EMAIL not in {d.pii_type for d in dets}


def test_all_keys_known():
    assert "rrn" in ALL_DETECTOR_KEYS
    assert "landline" in ALL_DETECTOR_KEYS
