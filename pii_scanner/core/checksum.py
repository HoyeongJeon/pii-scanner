from __future__ import annotations

_RRN_WEIGHTS = [2, 3, 4, 5, 6, 7, 8, 9, 2, 3, 4, 5]


def rrn_checksum_valid(norm13: str) -> bool:
    """주민등록번호 13자리(구분자 제거)의 검증숫자 확인."""
    if len(norm13) != 13 or not norm13.isdigit():
        return False
    total = sum(int(d) * w for d, w in zip(norm13[:12], _RRN_WEIGHTS))
    check = (11 - (total % 11)) % 10
    return check == int(norm13[12])


def luhn_valid(number: str) -> bool:
    """신용카드 Luhn 체크섬."""
    digits = [c for c in number if c.isdigit()]
    if len(digits) < 13:
        return False
    total = 0
    for i, ch in enumerate(reversed(digits)):
        d = int(ch)
        if i % 2 == 1:
            d *= 2
            if d > 9:
                d -= 9
        total += d
    return total % 10 == 0
