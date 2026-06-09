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
