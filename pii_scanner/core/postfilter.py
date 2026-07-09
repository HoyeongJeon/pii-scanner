from __future__ import annotations

import re
from collections import defaultdict

from pii_scanner.core.models import PiiHit

CORP_COL_MIN_HITS = 3     # 열 판정 최소 표본 — 미만이면 보류(보수적)
CORP_COL_RATIO = 0.7      # corp_suspect 비율 임계 — 실측(D-031): 법인 열 ~88%(오타 섞임), 주민번호 열 ~10%

_CELL = re.compile(r"^(?P<sheet>.+)!(?P<col>[A-Z]+)\d+$")


def filter_corp_columns(hits: list[PiiHit]) -> tuple[list[PiiHit], int]:
    """법인등록번호 열 오탐 제거 — (시트, 열, PII종류) 그룹의 corp_suspect 비율로 판정.

    실측(D-031 검증): 법인번호 열은 오타 등 오염 때문에 hit의 ~88%만 법인 체크섬을 통과하고,
    진짜 주민번호 열은 ~10%만 우연 통과한다. 임계 0.7은 오염 30%까지 허용하면서
    소표본(n=3)엔 3/3을 요구(2/3=66.7%<0.7)해 진짜 주민번호 열 오폭을 막는다.
    셀 좌표가 없는 hit(텍스트/PDF 등)은 판별 대상이 아니며 무조건 생존한다.
    """
    groups: dict[tuple, list[PiiHit]] = defaultdict(list)
    for h in hits:
        m = _CELL.match(h.location or "")
        if m:
            groups[(m["sheet"], m["col"], h.pii_type)].append(h)
    drop: set[int] = set()
    for group in groups.values():
        suspects = [h for h in group if h.corp_suspect]
        if len(group) >= CORP_COL_MIN_HITS and len(suspects) / len(group) >= CORP_COL_RATIO:
            drop.update(id(h) for h in suspects)
    if not drop:
        return hits, 0
    kept = [h for h in hits if id(h) not in drop]
    return kept, len(hits) - len(kept)
