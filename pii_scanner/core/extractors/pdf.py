from __future__ import annotations

from pdfminer.high_level import extract_text

from pii_scanner.core.extractors.base import Extractor


class PdfExtractor(Extractor):
    def extract(self, path: str) -> str:
        return extract_text(path) or ""
