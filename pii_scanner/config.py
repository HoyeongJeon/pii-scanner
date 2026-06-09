from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class ScanConfig:
    # 비활성화할 탐지기 키 (예: {"email", "landline"})
    disabled: set[str] = field(default_factory=set)
    # 순회 시 제외할 경로 조각 (대소문자 무시 부분일치)
    exclude_dirs: set[str] = field(default_factory=lambda: {".git", "__pycache__"})
    # 스캔 대상 확장자 (소문자, 점 포함)
    extensions: set[str] = field(
        default_factory=lambda: {
            ".txt", ".csv", ".hwpx", ".hwp", ".docx", ".xlsx", ".pdf",
        }
    )
