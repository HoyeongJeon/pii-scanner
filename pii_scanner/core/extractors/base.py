from __future__ import annotations

from abc import ABC, abstractmethod


class Extractor(ABC):
    """얇은 인터페이스: 파일 경로 → 순수 텍스트."""

    @abstractmethod
    def extract(self, path: str) -> str:
        ...
