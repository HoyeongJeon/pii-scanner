from __future__ import annotations

from array import array
from bisect import bisect_right
from typing import Protocol


class Locator(Protocol):
    """평탄화된 텍스트의 문자 오프셋 → 사람이 읽는 위치 라벨."""

    def label(self, offset: int) -> str | None: ...


def _starts(text: str, sep: str) -> list[int]:
    """`sep` 로 나뉜 각 구간의 시작 오프셋(항상 0으로 시작). 텍스트당 한 번만 만든다."""
    out = [0]
    i = text.find(sep)
    while i != -1:
        out.append(i + 1)
        i = text.find(sep, i + 1)
    return out


class LineLocator:
    """줄 번호 라벨 `L{n}` (1-기준). 페이지/셀 구조가 없는 포맷의 기본값.

    줄 시작 오프셋을 한 번 만들어 bisect 로 조회한다 — hit 마다 텍스트를 처음부터 다시 세면
    O(hit수 × 파일크기)라, 행마다 연락처가 있는 대장 CSV 에서 30분+ 교착이 났다(T-017).
    """

    def __init__(self, text: str):
        self._line_starts = _starts(text, "\n")

    def label(self, offset: int) -> str | None:
        return f"L{bisect_right(self._line_starts, offset)}"


class PageLineLocator:
    """`p.{page} L{line}` — pdfminer가 페이지 경계마다 넣는 \\x0c(form feed) 기반.

    LineLocator 와 같은 이유로 페이지·줄 시작 오프셋을 미리 만들어 bisect 로 조회한다(T-017).
    """

    def __init__(self, text: str):
        self._page_starts = _starts(text, "\x0c")
        self._line_starts = _starts(text, "\n")

    def label(self, offset: int) -> str | None:
        page = bisect_right(self._page_starts, offset)
        page_start = self._page_starts[page - 1]
        # 페이지 시작~offset 사이의 줄 시작 개수 = 그 구간의 개행 수(= 페이지 내 줄 번호 - 1)
        line = (bisect_right(self._line_starts, offset)
                - bisect_right(self._line_starts, page_start) + 1)
        return f"p.{page} L{line}"


class CellLocator:
    """세그먼트 라벨(예: `Sheet1!AB71762`) — 정렬된 [(시작오프셋, 라벨)]을 bisect로 조회."""

    def __init__(self, segments: list[tuple[int, str]]):
        self._starts = [s for s, _ in segments]
        self._labels = [lbl for _, lbl in segments]

    def label(self, offset: int) -> str | None:
        i = bisect_right(self._starts, offset)
        if i == 0:
            return None                     # 첫 세그먼트 시작 이전
        return self._labels[i - 1]


def _col_letters(col: int) -> str:
    """1-기준 열 번호 → 엑셀 열 문자(1→A, 27→AA). 조회 시점에만 만든다."""
    out = ""
    while col > 0:
        col, rem = divmod(col - 1, 26)
        out = chr(65 + rem) + out
    return out


class CellLocationIndex:
    """셀 위치를 정수 배열로만 담아 두고, 라벨은 조회할 때 조립한다.

    셀마다 `(오프셋, "Sheet1!AB71762")` 를 미리 만들면 셀당 ~200B — 2,300만 셀 시트(147MB)에서
    그것만 4.5GB 라 5GB 상한에 걸려 MemoryError 였다. 정작 텍스트는 24MB 였다(T-018).
    배열 3개(오프셋 int64 · 행/열 int32)면 셀당 16B 로 떨어진다. 라벨 형식은 CellLocator 와 동일 —
    법인번호 열 오탐 필터(D-031)가 `시트!열행` 형식을 파싱하므로 바꾸면 안 된다.
    """

    def __init__(self):
        self._starts = array("q")
        self._rows = array("i")
        self._cols = array("i")
        self._sheets: list[tuple[int, str]] = []     # (셀 인덱스, 시트명)

    def sheet(self, title: str) -> None:
        """이후 add() 되는 셀이 속할 시트를 연다."""
        self._sheets.append((len(self._starts), title))

    def add(self, pos: int, row: int, col: int) -> None:
        """텍스트 오프셋 pos 에서 시작하는 셀(1-기준 행·열)을 기록한다."""
        self._starts.append(pos)
        self._rows.append(row)
        self._cols.append(col)

    def build(self) -> Locator:
        return _IndexedCellLocator(self._starts, self._rows, self._cols, self._sheets)


class _IndexedCellLocator:
    """CellLocationIndex 가 만든 조회 전용 뷰 — bisect 2회로 시트·셀을 찾는다."""

    def __init__(self, starts, rows, cols, sheets):
        self._starts = starts
        self._rows = rows
        self._cols = cols
        self._sheet_at = [i for i, _ in sheets]
        self._titles = [t for _, t in sheets]

    def label(self, offset: int) -> str | None:
        i = bisect_right(self._starts, offset)
        if i == 0:
            return None                              # 첫 셀 시작 이전
        i -= 1
        s = bisect_right(self._sheet_at, i) - 1
        title = self._titles[s] if s >= 0 else ""
        return f"{title}!{_col_letters(self._cols[i])}{self._rows[i]}"
