from __future__ import annotations

import re

# 마스킹문자로 인정하는 것 (공백은 제외 — 서식 오탐 방지)
MASK_CHARS = set("*●■○xX＊")

# strip_separators 가 지우는 문자. 탭(\t)·NBSP(\xa0)를 넣는 이유: 탐지기 정규식은 예전부터
# [-\s]? 로 이들을 "매치"했는데 여기서 못 지워 길이 검사(len != 13)에 걸려 조용히 드롭됐다
# — 즉 탭 구분 진짜 주민번호가 통째로 미탐이었다.
_SEPARATORS = set("- .\t\xa0")

# 탐지기 정규식이 구분자로 인정하는 문자 — "줄 안쪽 서식" 문자만이고 _SEPARATORS 의 부분집합이다.
# 개행·CR·폼피드 같은 경계 문자를 빼는 이유: 추출기가 엑셀 셀(office.py)과 hwpx 문단을 "\n" 으로
# 잇기 때문에, 경계를 구분자로 인정하면 무관한 두 셀의 숫자가 이어 붙어 없는 주민번호가 생긴다.
# 경계 문자를 매치 대상에서도 빼면, 줄을 넘긴 매치가 바로 뒤의 진짜 번호를 삼켜 버리는
# 미탐도 함께 사라진다.
# '.' 은 _SEPARATORS 에 있지만 탐지기 문자클래스가 '.' 를 매치할 수 없어 여기엔 넣지 않는다.
#
# 오탐 대가(실측, 6자리 생년월일 열 + 무관한 7자리 열이 인접한 2만행):
#   공백 546건 · 탭 546건 · NBSP 546건 · 개행 0건
# 공백은 이미 구분자였으므로 탭·NBSP 추가는 새 실패 유형이 아니라 같은 비율을 다른 포맷
# (TSV·워드 탭스톱·HTML 변환물)으로 넓히는 것이다. 보이지 않는 미탐보다 사람이 알아챌 수
# 있는 과탐을 택한다는 이 저장소의 기존 방침과 같은 선택.
_DETECTOR_SEPARATORS = frozenset("- \t\xa0")

# re.escape 필수 — 없이 정렬만 하면 '[\t -\xa0]' 가 되어 U+0020~U+00A0 범위가 열리고
# 숫자·영문·마스킹문자까지 130자를 구분자로 먹는다(실측).
SEPARATOR_CLASS = "[" + "".join(re.escape(c) for c in sorted(_DETECTOR_SEPARATORS)) + "]"


def is_mask_char(ch: str) -> bool:
    return ch in MASK_CHARS


def strip_separators(s: str) -> str:
    """구분자(-, 공백, ., 탭, NBSP)만 제거하고 숫자/마스킹문자는 유지."""
    return "".join(c for c in s if c not in _SEPARATORS)


def count_masks(s: str) -> int:
    return sum(1 for c in s if c in MASK_CHARS)


def count_digits(s: str) -> int:
    return sum(1 for c in s if c.isdigit())
