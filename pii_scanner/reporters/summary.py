from __future__ import annotations

from dataclasses import dataclass, field

from pii_scanner.core.models import ScanResult, Status, PiiType


@dataclass
class Summary:
    total_files: int = 0
    error_files: int = 0
    encrypted_files: int = 0
    exposed: int = 0
    masked: int = 0
    masking_rate: float = 100.0
    corp_filtered: int = 0
    by_type: dict = field(default_factory=dict)


def summarize_iter(files) -> Summary:
    """FileResult 이터러블을 1회 순회로 집계 — 대형 state 스트리밍용(T-014).

    list 를 통째로 받는 summarize() 와 달리 제너레이터를 그대로 소비하므로
    수백만 hit 규모 스캔도 O(1) 메모리로 집계된다.
    """
    s = Summary()
    by_type: dict[PiiType, dict[str, int]] = {}
    for fr in files:
        s.total_files += 1
        if fr.encrypted:
            s.encrypted_files += 1
            continue                       # 암호화 파일은 hits 없음
        if fr.error:
            s.error_files += 1
        s.corp_filtered += fr.corp_filtered
        for h in fr.hits:
            bucket = by_type.setdefault(h.pii_type, {"exposed": 0, "masked": 0})
            if h.status is Status.EXPOSED:
                s.exposed += 1
                bucket["exposed"] += 1
            else:
                s.masked += 1
                bucket["masked"] += 1
    total = s.exposed + s.masked
    s.masking_rate = 100.0 if total == 0 else s.masked / total * 100.0
    s.by_type = by_type
    return s


def summarize(result: ScanResult) -> Summary:
    return summarize_iter(result.files)
