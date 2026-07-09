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
