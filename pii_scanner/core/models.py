from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class PiiType(str, Enum):
    RRN = "주민등록번호"
    FOREIGN = "외국인등록번호"
    PASSPORT = "여권번호"
    DRIVER = "운전면허번호"
    PHONE = "휴대폰"
    LANDLINE = "유선전화"
    EMAIL = "이메일"


class RiskLevel(str, Enum):
    CRITICAL = "최상"   # 고유식별정보
    HIGH = "높음"       # 휴대폰
    MEDIUM = "중간"     # 이메일
    LOW = "낮음"        # 유선


class Status(str, Enum):
    EXPOSED = "노출"
    MASKED = "마스킹"


class Confidence(str, Enum):
    CONFIRMED = "confirmed"
    PRESUMED = "추정"


@dataclass
class PiiHit:
    pii_type: PiiType
    status: Status
    snippet: str          # 마스킹된 스니펫 — 절대 원문 아님
    start: int            # 텍스트 내 문자 오프셋
    end: int
    confidence: Confidence
    risk: RiskLevel


@dataclass
class FileResult:
    path: str
    hits: list[PiiHit] = field(default_factory=list)
    error: str | None = None


@dataclass
class ScanResult:
    files: list[FileResult] = field(default_factory=list)
