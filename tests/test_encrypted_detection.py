import pytest

from pii_scanner.core.extractors import EncryptedFileError
from pii_scanner.core.extractors.base import EncryptedFileError as Base_EFE
from pii_scanner.core.extractors.office import DocxExtractor, XlsxExtractor
from pii_scanner.core.models import FileResult


def test_encrypted_file_error_exported_from_both():
    assert EncryptedFileError is Base_EFE
    assert issubclass(EncryptedFileError, Exception)


def test_file_result_encrypted_defaults_false():
    fr = FileResult(path="x")
    assert fr.encrypted is False


_OLE = b"\xD0\xCF\x11\xE0\xA1\xB1\x1A\xE1" + b"\x00" * 16


@pytest.mark.parametrize("ext,cls", [("docx", DocxExtractor), ("xlsx", XlsxExtractor)])
def test_office_ole_magic_raises_encrypted(tmp_path, ext, cls):
    f = tmp_path / f"locked.{ext}"
    f.write_bytes(_OLE)
    with pytest.raises(EncryptedFileError):
        cls().extract(str(f))


def test_office_non_ole_does_not_raise_encrypted(tmp_path):
    # zip 헤더(PK)로 시작하는 가짜 파일 — 암호화로 오판하면 안 됨(파싱은 다른 에러로 실패 가능)
    f = tmp_path / "plain.docx"
    f.write_bytes(b"PK\x03\x04rest")
    with pytest.raises(Exception) as ei:
        DocxExtractor().extract(str(f))
    assert not isinstance(ei.value, EncryptedFileError)


def test_pdf_encryption_error_maps_to_encrypted(tmp_path, monkeypatch):
    from pdfminer.pdfdocument import PDFEncryptionError
    import pii_scanner.core.extractors.pdf as pdfmod

    def boom(path):
        raise PDFEncryptionError("password required")
    monkeypatch.setattr(pdfmod, "extract_text", boom)

    f = tmp_path / "locked.pdf"; f.write_bytes(b"%PDF-1.4")
    with pytest.raises(EncryptedFileError):
        pdfmod.PdfExtractor().extract(str(f))
