from __future__ import annotations

from pii_scanner.core.models import KEY_PII_TYPES, Status
from pii_scanner.reporters.summary import Summary


class RowBudget:
    """리포트 행 상한을 '무엇을 먼저 실을지' 우선순위로 나눠 쓰는 배분기(T-017 후속).

    상한을 파일 순서대로 채우면 압도적으로 많은 연락처류가 자리를 다 차지해, 정작 감사
    대상인 고유식별정보가 잘려나간다(실측: 주민 노출 257건 중 204건 생략). 순위는
    ① 고유식별정보·노출 ② 고유식별정보·마스킹 ③ 나머지 — 앞 순위가 못 쓴 자리는
    뒤 순위가 이어받는다. 종류별 건수는 summarize_iter 결과에 이미 있으므로 몫 계산은 O(1)이고,
    스트리밍 1회 순회·유계 메모리(T-014)는 그대로 유지된다.
    """

    def __init__(self, summary: Summary, cap: int):
        key_exposed = sum(b["exposed"] for t, b in summary.by_type.items()
                          if t in KEY_PII_TYPES)
        key_masked = sum(b["masked"] for t, b in summary.by_type.items()
                         if t in KEY_PII_TYPES)
        self._quota = [min(key_exposed, cap)]
        self._quota.append(min(key_masked, cap - self._quota[0]))
        self._quota.append(cap - self._quota[0] - self._quota[1])
        self._used = [0, 0, 0]
        self.skipped = 0

    @staticmethod
    def _tier(hit) -> int:
        if hit.pii_type not in KEY_PII_TYPES:
            return 2
        return 0 if hit.status is Status.EXPOSED else 1

    def allow(self, hit) -> bool:
        """이 hit 을 리포트에 실을 수 있으면 True(자리 차감), 아니면 False(생략 카운트)."""
        t = self._tier(hit)
        if self._used[t] >= self._quota[t]:
            self.skipped += 1
            return False
        self._used[t] += 1
        return True
