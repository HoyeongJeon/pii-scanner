from pii_scanner.core.checksum import rrn_checksum_valid, luhn_valid, corp_reg_checksum_valid


def test_valid_synthetic_rrn_passes():
    # 900101-1234568 : 가중치 검증 통과하도록 계산된 가짜 번호
    assert rrn_checksum_valid("9001011234568") is True


def test_wrong_check_digit_fails():
    assert rrn_checksum_valid("9001011234567") is False


def test_non_13_or_nondigit_fails():
    assert rrn_checksum_valid("12345") is False
    assert rrn_checksum_valid("90010112345*8") is False


def test_luhn_valid_card():
    assert luhn_valid("4242424242424242") is True  # 테스트 카드번호


def test_luhn_invalid_card():
    assert luhn_valid("4242424242424241") is False


def test_corp_reg_checksum_valid_real_number():
    # 합성 법인등록번호 — 체크섬 규칙을 만족하도록 만든 값(실존 기업 번호 사용 금지)
    assert corp_reg_checksum_valid("1101110006240")


def test_corp_reg_checksum_invalid_check_digit():
    assert not corp_reg_checksum_valid("1101110006241")  # 마지막 자리 변조


def test_corp_reg_checksum_rejects_non_13_digits():
    assert not corp_reg_checksum_valid("12345")
    assert not corp_reg_checksum_valid("11011100062400")   # 14자리
    assert not corp_reg_checksum_valid("110111000624X")    # 비숫자
