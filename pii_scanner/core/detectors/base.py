from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Iterator

from pii_scanner.core.models import PiiHit, PiiType, RiskLevel


class Detector(ABC):
    """모든 PII 탐지기의 얇은 인터페이스: find(text) -> PiiHit들."""

    pii_type: PiiType
    risk: RiskLevel

    @abstractmethod
    def find(self, text: str) -> Iterator[PiiHit]:
        ...
