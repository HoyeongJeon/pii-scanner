from __future__ import annotations

from abc import ABC, abstractmethod

from pii_scanner.core.locate import LineLocator, Locator


class Extractor(ABC):
    """얇은 인터페이스: 파일 경로 → 순수 텍스트."""

    @abstractmethod
    def extract(self, path: str) -> str:
        ...

    def extract_located(self, path: str) -> tuple[str, Locator]:
        """텍스트 + 위치 라벨러. 기본은 줄 번호 — 구조 좌표가 있는 포맷(xlsx/xls/pdf)만 오버라이드."""
        text = self.extract(path)
        return text, LineLocator(text)


class EncryptedFileError(Exception):
    """비밀번호로 암호화돼 텍스트를 추출할 수 없는 파일(실패 아님 — 건너뜀 분류)."""
    pass
