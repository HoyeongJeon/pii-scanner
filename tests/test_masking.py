from pii_scanner.core.masking import (
    MASK_CHARS, is_mask_char, strip_separators, count_masks, count_digits
)


def test_mask_chars_include_common_symbols():
    for c in "*●■○xX":
        assert is_mask_char(c) is True
    assert is_mask_char("5") is False
    assert is_mask_char(" ") is False  # 공백은 마스킹문자 아님


def test_strip_separators_keeps_digits_and_masks():
    assert strip_separators("900101-1******") == "9001011******"
    assert strip_separators("010 1234 5678") == "01012345678"


def test_count_masks_and_digits():
    assert count_masks("1******") == 6
    assert count_digits("1******") == 1


# ---------------------------------------------------------------------------
# 정규식이 구분자로 인정하는 문자는 strip_separators 가 반드시 지워야 한다.
# 어긋나면 매치는 되는데 길이 검사(len != 13)에서 조용히 드롭돼 진짜 번호가 사라진다 —
# 탭·NBSP 구분 주민번호가 정확히 그렇게 미탐이었다.
# ---------------------------------------------------------------------------
import re
from pii_scanner.core.masking import (
    SEPARATOR_CLASS, _DETECTOR_SEPARATORS, _SEPARATORS, strip_separators,
)


def test_every_regex_separator_is_stripped():
    for ch in _DETECTOR_SEPARATORS:
        assert re.fullmatch(SEPARATOR_CLASS, ch), f"클래스가 {ch!r} 를 매치하지 못함"
        assert strip_separators(f"1{ch}2") == "12", f"strip 이 {ch!r} 를 안 지움"
    assert _DETECTOR_SEPARATORS <= _SEPARATORS


def test_separator_class_is_escaped_not_a_character_range():
    # re.escape 없이 정렬만 하면 '[\t -\xa0]' 가 되어 U+0020~U+00A0 범위가 열리고
    # 숫자·영문·마스킹문자까지 구분자로 먹는다(실측 130자).
    for ch in "05Az*●,+":
        assert not re.fullmatch(SEPARATOR_CLASS, ch), f"{ch!r} 가 구분자로 매치됨 — 범위가 열렸다"


def test_boundary_chars_are_not_separators():
    # 추출기가 엑셀 셀·hwpx 문단을 "\n" 으로 잇는다 — 경계를 구분자로 인정하면 인접 셀이 융합된다.
    for ch in "\n\r\x0c\v  ":
        assert not re.fullmatch(SEPARATOR_CLASS, ch), f"경계문자 {ch!r} 가 구분자로 인정됨"
        assert strip_separators(f"1{ch}2") == f"1{ch}2"
