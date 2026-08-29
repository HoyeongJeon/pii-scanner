import zipfile
from pii_scanner.core.extractors.hwpx import HwpxExtractor

SECTION_XML = (
    '<?xml version="1.0" encoding="UTF-8"?>'
    '<hs:sec xmlns:hp="http://www.hancom.co.kr/hwpml/2011/paragraph"'
    ' xmlns:hs="http://www.hancom.co.kr/hwpml/2011/section">'
    '<hp:p><hp:run><hp:t>홍길동 900101-1234568</hp:t></hp:run></hp:p>'
    '<hp:p><hp:run><hp:t>연락처 010-1234-5678</hp:t></hp:run></hp:p>'
    '</hs:sec>'
)


def make_hwpx(path):
    with zipfile.ZipFile(path, "w") as z:
        z.writestr("Contents/section0.xml", SECTION_XML)


def test_extract_hwpx_text(tmp_path):
    p = tmp_path / "doc.hwpx"
    make_hwpx(str(p))
    text = HwpxExtractor().extract(str(p))
    assert "900101-1234568" in text
    assert "010-1234-5678" in text


# ---------------------------------------------------------------------------
# 문단 경계가 없으면 무관한 두 문단의 숫자가 융합돼 '없는 주민번호'가 만들어지고,
# 문서 전체가 1줄이 되어 모든 탐지 위치가 L1 로 찍힌다.
# ---------------------------------------------------------------------------
from pii_scanner.core.detectors.rrn import RrnDetector
from pii_scanner.core.locate import LineLocator

_NS = ('<hs:sec xmlns:hp="http://www.hancom.co.kr/hwpml/2011/paragraph"'
       ' xmlns:hs="http://www.hancom.co.kr/hwpml/2011/section">')


def _make(tmp_path, body, name="doc.hwpx"):
    p = tmp_path / name
    with zipfile.ZipFile(str(p), "w") as z:
        z.writestr("Contents/section0.xml", '<?xml version="1.0"?>' + _NS + body + "</hs:sec>")
    return str(p)


def _para(t):
    return f"<hp:p><hp:run><hp:t>{t}</hp:t></hp:run></hp:p>"


def test_adjacent_paragraphs_do_not_fuse_into_a_fake_rrn(tmp_path):
    """무해한 두 문단이 붙어 체크섬까지 통과하는 confirmed 노출로 잡히던 회귀."""
    path = _make(tmp_path, _para("기준일자 900101") + _para("1123459 호") + _para("담당자 확인"))
    text = HwpxExtractor().extract(path)
    assert "9001011123459" not in text
    assert list(RrnDetector(reference_year=2026).find(text)) == []


def test_paragraph_count_equals_line_count(tmp_path):
    path = _make(tmp_path, "".join(_para(f"줄{i}") for i in range(1, 6)))
    text = HwpxExtractor().extract(path)
    assert text.splitlines() == ["줄1", "줄2", "줄3", "줄4", "줄5"]


def test_detection_location_is_the_real_paragraph_not_l1(tmp_path):
    """200페이지 문서의 모든 hit 이 L1 로 찍히면 담당자가 찾아갈 수 없다."""
    path = _make(tmp_path, _para("머리말") + _para("가운데") + _para("홍길동 900101-1234568"))
    text = HwpxExtractor().extract(path)
    loc = LineLocator(text)
    hits = list(RrnDetector(reference_year=2026).find(text))
    assert [loc.label(h.start) for h in hits] == ["L3"]


def test_table_cell_paragraphs_are_separated(tmp_path):
    """표 안 중첩 문단(hp:tc > hp:p)도 각각 한 줄 — 인접 셀이 융합되면 안 된다."""
    body = (_para("표앞")
            + "<hp:tbl><hp:tr>"
            + "<hp:tc><hp:subList>" + _para("900101") + "</hp:subList></hp:tc>"
            + "<hp:tc><hp:subList>" + _para("1234568") + "</hp:subList></hp:tc>"
            + "</hp:tr></hp:tbl>")
    text = HwpxExtractor().extract(_make(tmp_path, body))
    assert list(RrnDetector(reference_year=2026).find(text)) == []


def test_runs_inside_one_paragraph_still_join(tmp_path):
    """한 번호가 서식 때문에 여러 run 으로 쪼개지는 정상 케이스는 계속 이어 붙여야 한다."""
    body = ("<hp:p><hp:run><hp:t>홍길동 900101</hp:t></hp:run>"
            "<hp:run><hp:t>-1234568</hp:t></hp:run></hp:p>")
    text = HwpxExtractor().extract(_make(tmp_path, body))
    assert len(list(RrnDetector(reference_year=2026).find(text))) == 1


def test_sections_do_not_fuse_even_without_paragraph_tags(tmp_path):
    """문단 태그가 없는 비표준 섹션이라도 섹션끼리는 붙지 않아야 한다."""
    p = tmp_path / "multi.hwpx"
    with zipfile.ZipFile(str(p), "w") as z:
        z.writestr("Contents/section0.xml", "<hs:sec><hp:t>900101</hp:t></hs:sec>")
        z.writestr("Contents/section1.xml", "<hs:sec><hp:t>1234568</hp:t></hs:sec>")
    text = HwpxExtractor().extract(str(p))
    assert text == "900101\n1234568\n"
    assert list(RrnDetector(reference_year=2026).find(text)) == []
