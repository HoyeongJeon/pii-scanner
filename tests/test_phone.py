from pii_scanner.core.detectors.phone import MobileDetector, LandlineDetector
from pii_scanner.core.models import Status, PiiType, RiskLevel


def test_mobile_detected_high_risk():
    hits = list(MobileDetector().find("연락처 010-1234-5678 입니다"))
    assert len(hits) == 1
    assert hits[0].pii_type is PiiType.PHONE
    assert hits[0].risk is RiskLevel.HIGH
    assert hits[0].status is Status.EXPOSED
    assert hits[0].snippet == "010-****-5678"


def test_mobile_masked_middle_is_masked():
    hits = list(MobileDetector().find("010-****-5678"))
    assert hits[0].status is Status.MASKED


def test_landline_low_risk():
    hits = list(LandlineDetector().find("대표번호 02-123-4567"))
    assert len(hits) == 1
    assert hits[0].pii_type is PiiType.LANDLINE
    assert hits[0].risk is RiskLevel.LOW


def test_mobile_not_matched_inside_longer_digits():
    assert list(MobileDetector().find("01012345678999")) == []
