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


def test_passport_letter_whitelist_blocks_code_families():
    # D-034 실측 오탐: 여권 종류 글자(M/S/R/O/D/T)가 아닌 대문자는 접수·관리 코드
    assert list(PassportDetector().find("접수 N11100123 처리")) == []
    assert list(PassportDetector().find("코드 G04112345 발번")) == []
    assert list(PassportDetector().find("W20012345")) == []


def test_passport_all_type_letters_detected():
    # 공식 종류 글자 전부 인정: M복수 S단수 R거주 O관용 D외교 T여행증명서
    for letter in "MSRODT":
        hits = list(PassportDetector().find(f"여권 {letter}12345678 사본"))
        assert len(hits) == 1, letter
        assert hits[0].status is Status.EXPOSED


def test_passport_new_format_detected():
    # 차세대 여권(2020~): 종류1 + 숫자3 + 로마자1 + 숫자4
    hits = list(PassportDetector().find("여권번호 M123A4567 확인"))
    assert len(hits) == 1
    assert hits[0].status is Status.EXPOSED
    assert hits[0].confidence is Confidence.PRESUMED
    assert hits[0].snippet.startswith("M123")
    assert "4567" not in hits[0].snippet     # 뒷자리 원문 미기록


def test_passport_new_format_masked():
    hits = list(PassportDetector().find("M123A****"))
    assert len(hits) == 1
    assert hits[0].status is Status.MASKED


def test_passport_adjacent_alnum_not_matched():
    # 앞뒤에 영숫자가 붙은 긴 코드의 일부는 여권이 아님
    assert list(PassportDetector().find("AM12345678")) == []
    assert list(PassportDetector().find("M12345678A")) == []
    assert list(PassportDetector().find("M123456789")) == []


def test_driver_bare_digit_run_not_matched():
    # 구분자 없는 평범한 12자리 숫자열은 운전면허로 오탐하지 않음
    assert list(DriverDetector().find("주문번호 202401150001")) == []
    assert list(DriverDetector().find("계좌 110234567890")) == []
