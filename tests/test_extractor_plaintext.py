from pii_scanner.core.extractors.plaintext import PlaintextExtractor


def test_extract_utf8_text(tmp_path):
    p = tmp_path / "a.txt"
    p.write_text("홍길동 900101-1234568", encoding="utf-8")
    assert "900101-1234568" in PlaintextExtractor().extract(str(p))


def test_extract_cp949_fallback(tmp_path):
    p = tmp_path / "b.txt"
    p.write_bytes("한글본문".encode("cp949"))
    assert "한글본문" in PlaintextExtractor().extract(str(p))
