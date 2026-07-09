from pii_scanner.core.models import PiiHit, PiiType, Status, Confidence, RiskLevel
from pii_scanner.core.postfilter import filter_corp_columns


def _hit(loc, corp=False, ptype=PiiType.RRN):
    return PiiHit(ptype, Status.EXPOSED, "110111-1******", 0, 13,
                  Confidence.PRESUMED, RiskLevel.CRITICAL,
                  location=loc, corp_suspect=corp)


def test_corp_column_hits_dropped():
    hits = [_hit(f"편집 2!AZ{r}", corp=True) for r in (314, 315, 334)]
    kept, dropped = filter_corp_columns(hits)
    assert kept == [] and dropped == 3


def test_real_rrn_column_kept_despite_one_chance_pass():
    # 진짜 주민번호 열: 10건 중 1건만 우연히 법인 체크섬 통과(~10%) → 비율 미달, 전부 생존
    hits = [_hit(f"Sheet1!C{r}", corp=(r == 5)) for r in range(1, 11)]
    kept, dropped = filter_corp_columns(hits)
    assert len(kept) == 10 and dropped == 0


def test_small_sample_column_kept():
    hits = [_hit(f"Sheet1!B{r}", corp=True) for r in (1, 2)]   # 표본 3 미만 → 판별 보류
    kept, dropped = filter_corp_columns(hits)
    assert len(kept) == 2 and dropped == 0


def test_non_cell_location_ignored():
    hits = [_hit("L5", corp=True), _hit("p.3 L12", corp=True), _hit(None, corp=True)]
    kept, dropped = filter_corp_columns(hits)
    assert len(kept) == 3 and dropped == 0


def test_mixed_column_drops_only_suspects_and_keeps_order():
    # 법인 열에 법인 체크섬 불통과 hit(진짜 주민번호 가능성) 1건이 섞임 → 그 1건만 생존
    a = _hit("S!AZ1", corp=True)
    b = _hit("S!AZ2", corp=False)
    c = _hit("S!AZ3", corp=True)
    d = _hit("S!AZ4", corp=True)
    e = _hit("S!AZ5", corp=True)          # corp 4/5 = 80% ≥ 70% → 판정 성립
    kept, dropped = filter_corp_columns([a, b, c, d, e])
    assert kept == [b] and dropped == 4


def test_dirty_corp_column_fires_at_observed_real_ratio():
    # 실측(D-031 검증): 실제 법인번호 열은 오타 등으로 corp_suspect 비율이 ~88%다.
    # 13/15 = 86.7% ≥ 70% → 발동해야 한다 (임계 90%는 실데이터에서 미발동했던 회귀 케이스).
    hits = [_hit(f"편집 2!AZ{r}", corp=(r > 2)) for r in range(1, 16)]
    kept, dropped = filter_corp_columns(hits)
    assert dropped == 13
    assert [h.location for h in kept] == ["편집 2!AZ1", "편집 2!AZ2"]


def test_two_thirds_small_column_held():
    # 소표본 안전장치: n=3이면 3/3만 발동(2/3=66.7% < 70%) — 진짜 주민번호 열 오폭 방지
    hits = [_hit(f"S!C{r}", corp=(r != 3)) for r in (1, 2, 3)]
    kept, dropped = filter_corp_columns(hits)
    assert len(kept) == 3 and dropped == 0
