import pytest
import xlrd
import xlwt

import pii_scanner.core.extractors.office as off
from pii_scanner.core.extractors.office import XlsExtractor
from pii_scanner.core.extractors import EncryptedFileError


def _make_xls(path, rows):
    """xlwt 로 합성 .xls 작성(테스트 전용 — 실제 문서는 절대 건드리지 않음)."""
    wb = xlwt.Workbook()
    ws = wb.add_sheet("Sheet1")
    for r, row in enumerate(rows):
        for c, val in enumerate(row):
            ws.write(r, c, val)
    wb.save(str(path))


def test_xls_roundtrip_extracts_cell_text(tmp_path):
    f = tmp_path / "a.xls"
    _make_xls(f, [["홍길동", "900101-1234568"], ["연락처", "010-1234-5678"]])
    text = XlsExtractor().extract(str(f))
    assert "홍길동" in text
    assert "900101-1234568" in text          # 탐지기가 잡을 수 있게 셀 값이 텍스트로 나와야
    assert "010-1234-5678" in text


def test_xls_encrypted_maps_to_encrypted(tmp_path, monkeypatch):
    def boom(path):
        raise xlrd.XLRDError("Workbook is encrypted")
    monkeypatch.setattr(off.xlrd, "open_workbook", boom)
    f = tmp_path / "locked.xls"; f.write_bytes(b"\xD0\xCF\x11\xE0")
    with pytest.raises(EncryptedFileError):
        XlsExtractor().extract(str(f))


def test_xls_non_encryption_xlrderror_propagates(tmp_path, monkeypatch):
    # 손상 등 비암호화 XLRDError 는 암호화로 오분류하지 않고 그대로 전파(보수적).
    def boom(path):
        raise xlrd.XLRDError("corrupt or unsupported file")
    monkeypatch.setattr(off.xlrd, "open_workbook", boom)
    f = tmp_path / "bad.xls"; f.write_bytes(b"\xD0\xCF\x11\xE0")
    with pytest.raises(xlrd.XLRDError) as ei:
        XlsExtractor().extract(str(f))
    assert not isinstance(ei.value, EncryptedFileError)


def test_xls_registered_in_map_and_config():
    from pii_scanner.core.extractors import get_extractor
    from pii_scanner.config import ScanConfig
    assert ".xls" in ScanConfig().extensions
    assert isinstance(get_extractor("x.xls"), XlsExtractor)


def test_xls_end_to_end_scan_detects_rrn(tmp_path):
    from pii_scanner.config import ScanConfig
    from pii_scanner.core.scanner import scan_paths
    _make_xls(tmp_path / "members.xls", [["주민", "900101-1234568"]])
    result = scan_paths([str(tmp_path)], ScanConfig())
    assert len(result.files) == 1
    assert result.files[0].hits          # 주민번호가 탐지돼야(스캐너가 .xls 를 집어 추출·탐지)


def test_xls_extract_located_labels_cells(tmp_path):
    f = tmp_path / "a.xls"
    _make_xls(f, [["이름", "연락처"], ["홍길동", "010-1234-5678"]])
    text, locator = XlsExtractor().extract_located(str(f))
    assert locator.label(text.index("이름")) == "Sheet1!A1"
    assert locator.label(text.index("010-1234-5678")) == "Sheet1!B2"
    assert XlsExtractor().extract(str(f)) == text
