from __future__ import annotations

import datetime
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
    unreadable_paths: int = 0
    # 감사 증적 — "언제·어느 버전으로·무엇을 검사했나". 비어 있으면 리포트에 안 실린다.
    scanned_at: str = ""
    tool_version: str = ""
    active_types: tuple = ()
    inactive_types: tuple = ()
    by_type: dict = field(default_factory=dict)


def summarize_iter(files) -> Summary:
    """FileResult 이터러블을 1회 순회로 집계 — 대형 state 스트리밍용(T-014).

    list 를 통째로 받는 summarize() 와 달리 제너레이터를 그대로 소비하므로
    수백만 hit 규모 스캔도 O(1) 메모리로 집계된다.
    """
    s = Summary()
    by_type: dict[PiiType, dict[str, int]] = {}
    for fr in files:
        if fr.unreadable:
            # 읽지 못한 '폴더'는 스캔한 파일이 아니다 — total_files/error_files 어디에도
            # 섞지 않는다. 섞으면 커버리지 숫자가 실제보다 좋아 보인다.
            s.unreadable_paths += 1
            continue
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


def stamp_scan_meta(s: Summary, config, *, now=None) -> Summary:
    """이번 실행의 출처(일시·버전·검사한/안 한 종류)를 Summary 에 찍는다.

    now 는 테스트 결정론용 seam(RrnDetector.reference_year 와 같은 이유).
    집계 함수(summarize_iter)의 시그니처는 건드리지 않는다 — 호출부가 여럿이고
    이 정보는 FileResult 가 아니라 설정에서 오기 때문.
    """
    from pii_scanner import __version__
    from pii_scanner.core.detectors import describe_detectors

    s.scanned_at = (now or datetime.datetime.now()).replace(microsecond=0).isoformat()
    s.tool_version = __version__
    active, inactive = describe_detectors(config)
    s.active_types, s.inactive_types = tuple(active), tuple(inactive)
    return s


def summarize(result: ScanResult) -> Summary:
    return summarize_iter(result.files)
