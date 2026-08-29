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


# 고유식별정보(D-001) — PIPA 시행령 제19조. 리포트 상한이 차도 이 종류는 먼저 수록한다.
KEY_PII_TYPES = (PiiType.RRN, PiiType.FOREIGN, PiiType.PASSPORT, PiiType.DRIVER)


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
    location: str | None = None   # "Sheet1!AB71762" / "p.3 L12" / "L42" — 스캐너가 주입
    corp_suspect: bool = False    # 법인 체크섬도 통과(법인번호 의심) — 내부 판별용, 리포트/state 미기록


@dataclass
class FileResult:
    path: str
    hits: list[PiiHit] = field(default_factory=list)
    error: str | None = None
    encrypted: bool = False
    unreadable: bool = False  # 순회 자체를 못 한 경로(폴더 접근 실패) — '스캔한 파일'이 아니다
    corp_filtered: int = 0   # 법인등록번호 열 오탐으로 제거된 hit 수 (summary 집계용)
    # 일부 탐지기만 실패한 파일 — 나머지 hit 은 유효하지만 '전부 봤다'고 할 수 없다.
    partial_detection: list[str] = field(default_factory=list)


@dataclass
class ScanResult:
    files: list[FileResult] = field(default_factory=list)
