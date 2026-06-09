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
