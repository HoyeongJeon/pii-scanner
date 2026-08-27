import time

from pii_scanner.core.extractors.base import Extractor
from pii_scanner.core.locate import CellLocator, LineLocator, PageLineLocator
from pii_scanner.core.models import PiiHit, PiiType, Status, Confidence, RiskLevel


def test_line_locator_labels_by_newline_count():
    text = "a\nbb\nccc"
    loc = LineLocator(text)
    assert loc.label(0) == "L1"                      # "a"
    assert loc.label(text.index("bb")) == "L2"
    assert loc.label(text.index("ccc")) == "L3"


def test_page_line_locator_uses_formfeed_page_breaks():
    # pdfminer는 페이지 끝마다 \x0c 를 넣는다
    text = "l1\nl2\x0cp2l1\np2l2"
    loc = PageLineLocator(text)
    assert loc.label(0) == "p.1 L1"
    assert loc.label(text.index("l2")) == "p.1 L2"
    assert loc.label(text.index("p2l1")) == "p.2 L1"
    assert loc.label(text.index("p2l2")) == "p.2 L2"


def test_cell_locator_bisects_segments():
    loc = CellLocator([(0, "S!A1"), (5, "S!B1")])
    assert loc.label(0) == "S!A1"
    assert loc.label(3) == "S!A1"
    assert loc.label(5) == "S!B1"
    assert loc.label(7) == "S!B1"


def test_cell_locator_before_first_segment_is_none():
    loc = CellLocator([(3, "S!A1")])
    assert loc.label(1) is None


def test_cell_locator_empty_segments_is_none():
    assert CellLocator([]).label(0) is None


def test_piihit_location_defaults_to_none():
    h = PiiHit(PiiType.EMAIL, Status.EXPOSED, "k**@ex***.com", 0, 13,
               Confidence.CONFIRMED, RiskLevel.MEDIUM)
    assert h.location is None               # 탐지기 기존 생성 코드 무변경 보장


def test_extractor_default_extract_located_returns_line_locator():
    class _Fixed(Extractor):
        def extract(self, path: str) -> str:
            return "one\ntwo"
    text, loc = _Fixed().extract_located("ignored")
    assert text == "one\ntwo"
    assert isinstance(loc, LineLocator)
    assert loc.label(text.index("two")) == "L2"


def test_line_locator_labels_many_hits_in_large_text_without_quadratic_cost():
    """행마다 hit 이 있는 대용량 CSV 시나리오 — hit 당 전체 재스캔이면 분 단위로 폭발한다(T-017).

    실측: 기업연구소 대장 CSV 4건이 각각 30분+ 정체 → 감시견이 교착으로 판정·스킵.
    """
    text = "".join(f"row{i},02-3456-{i % 10000:04d}\n" for i in range(60000))   # ~1.5MB
    offsets = list(range(0, len(text), max(1, len(text) // 60000)))
    loc = LineLocator(text)

    t0 = time.perf_counter()
    labels = [loc.label(o) for o in offsets]
    elapsed = time.perf_counter() - t0

    assert labels[0] == "L1"
    assert elapsed < 3.0, f"라벨링에 {elapsed:.1f}s — hit 당 전체 재스캔(2차식) 의심"


def test_page_line_locator_labels_many_hits_in_large_pdf_text_without_quadratic_cost():
    """PDF 도 같은 결함 — 페이지·줄을 hit 마다 처음부터 다시 세면 큰 PDF 에서 같은 폭발(T-017)."""
    page = "".join(f"line{i},010-1234-{i % 10000:04d}\n" for i in range(300))
    text = "\x0c".join(page for _ in range(200))                       # 200쪽 ~1.5MB
    offsets = list(range(0, len(text), max(1, len(text) // 60000)))
    loc = PageLineLocator(text)

    t0 = time.perf_counter()
    labels = [loc.label(o) for o in offsets]
    elapsed = time.perf_counter() - t0

    assert labels[0] == "p.1 L1"
    assert elapsed < 3.0, f"라벨링에 {elapsed:.1f}s — hit 당 전체 재스캔(2차식) 의심"


def test_cell_location_index_keeps_memory_small_for_many_cells():
    """셀마다 라벨 문자열을 미리 만들면 대형 시트에서 메모리가 폭발한다(T-018).

    실측: 2,300만 셀 엑셀(147MB)에서 (오프셋, 'Sheet1!AB71762') 튜플만 4.5GB —
    텍스트 자체는 24MB인데 5GB 상한에 걸려 MemoryError 로 스캔이 실패했다.
    """
    import tracemalloc
    from pii_scanner.core.locate import CellLocationIndex

    N = 200_000
    tracemalloc.start()
    idx = CellLocationIndex()
    idx.sheet("Sheet1")
    for i in range(N):
        idx.add(i * 7, i // 50 + 1, i % 50 + 1)
    loc = idx.build()
    peak = tracemalloc.get_traced_memory()[1]
    tracemalloc.stop()

    assert loc.label(0) == "Sheet1!A1"
    assert peak < N * 40, f"셀당 {peak / N:.0f}B — 라벨을 미리 만들어 들고 있다"


def test_cell_location_index_labels_match_sheet_and_coordinate():
    """라벨 형식은 기존 CellLocator 와 동일해야 한다 — 법인번호 열 오탐 필터가 이 형식을 파싱한다."""
    from pii_scanner.core.locate import CellLocationIndex

    idx = CellLocationIndex()
    idx.sheet("Sheet1")
    idx.add(0, 1, 1)            # A1
    idx.add(10, 5, 28)          # AB5
    idx.sheet("2번시트")
    idx.add(20, 3, 27)          # AA3
    loc = idx.build()

    assert loc.label(0) == "Sheet1!A1"
    assert loc.label(9) == "Sheet1!A1"          # 다음 셀 시작 전까지는 앞 셀
    assert loc.label(10) == "Sheet1!AB5"
    assert loc.label(20) == "2번시트!AA3"
    assert loc.label(99) == "2번시트!AA3"
