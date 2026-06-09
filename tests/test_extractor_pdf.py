from reportlab.pdfgen import canvas
from pii_scanner.core.extractors.pdf import PdfExtractor


def test_pdf_text_extract(tmp_path):
    p = tmp_path / "a.pdf"
    c = canvas.Canvas(str(p))
    c.drawString(100, 700, "email test ho@example.com")
    c.save()
    text = PdfExtractor().extract(str(p))
    assert "ho@example.com" in text
