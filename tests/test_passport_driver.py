from pii_scanner.core.detectors.passport import PassportDetector
from pii_scanner.core.detectors.driver import DriverDetector
from pii_scanner.core.models import Status, Confidence, PiiType, RiskLevel


def test_passport_detected_presumed():
    hits = list(PassportDetector().find("여권 M12345678 발급"))
    assert len(hits) == 1
    assert hits[0].pii_type is PiiType.PASSPORT
    assert hits[0].confidence is Confidence.PRESUMED
    assert hits[0].risk is RiskLevel.CRITICAL
    assert hits[0].status is Status.EXPOSED
    assert "*" in hits[0].snippet  # 일부 마스킹된 스니펫


def test_passport_masked_is_masked():
    hits = list(PassportDetector().find("M123*****"))
    assert hits[0].status is Status.MASKED


def test_driver_detected_presumed():
    hits = list(DriverDetector().find("면허 11-12-345678-90 발급"))
    assert len(hits) == 1
    assert hits[0].pii_type is PiiType.DRIVER
    assert hits[0].confidence is Confidence.PRESUMED
    assert hits[0].status is Status.EXPOSED


def test_driver_masked():
    hits = list(DriverDetector().find("11-12-34****-**"))
    assert hits[0].status is Status.MASKED


def test_passport_lowercase_not_matched():
    # 소문자 영문+8자리는 여권으로 보지 않음 (과탐 방지)
    assert list(PassportDetector().find("토큰 a12345678 입니다")) == []


def test_driver_bare_digit_run_not_matched():
    # 구분자 없는 평범한 12자리 숫자열은 운전면허로 오탐하지 않음
    assert list(DriverDetector().find("주문번호 202401150001")) == []
    assert list(DriverDetector().find("계좌 110234567890")) == []
