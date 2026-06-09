from __future__ import annotations

# 마스킹문자로 인정하는 것 (공백은 제외 — 서식 오탐 방지)
MASK_CHARS = set("*●■○xX＊")

_SEPARATORS = set("- .")


def is_mask_char(ch: str) -> bool:
    return ch in MASK_CHARS


def strip_separators(s: str) -> str:
    """구분자(-, 공백, .)만 제거하고 숫자/마스킹문자는 유지."""
    return "".join(c for c in s if c not in _SEPARATORS)


def count_masks(s: str) -> int:
    return sum(1 for c in s if c in MASK_CHARS)


def count_digits(s: str) -> int:
    return sum(1 for c in s if c.isdigit())
