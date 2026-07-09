from __future__ import annotations

from bisect import bisect_right
from typing import Protocol


class Locator(Protocol):
    """평탄화된 텍스트의 문자 오프셋 → 사람이 읽는 위치 라벨."""

    def label(self, offset: int) -> str | None: ...


class LineLocator:
    """줄 번호 라벨 `L{n}` (1-기준). 페이지/셀 구조가 없는 포맷의 기본값."""

    def __init__(self, text: str):
        self._text = text

    def label(self, offset: int) -> str | None:
        line = self._text.count("\n", 0, offset) + 1
        return f"L{line}"


class PageLineLocator:
    """`p.{page} L{line}` — pdfminer가 페이지 경계마다 넣는 \\x0c(form feed) 기반."""

    def __init__(self, text: str):
        self._text = text

    def label(self, offset: int) -> str | None:
        page = self._text.count("\x0c", 0, offset) + 1
        page_start = self._text.rfind("\x0c", 0, offset) + 1   # 없으면 -1+1=0
        line = self._text.count("\n", page_start, offset) + 1
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
