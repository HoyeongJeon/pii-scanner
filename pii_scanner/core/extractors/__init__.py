from __future__ import annotations

import os

from pii_scanner.core.extractors.plaintext import PlaintextExtractor
from pii_scanner.core.extractors.hwpx import HwpxExtractor
from pii_scanner.core.extractors.office import DocxExtractor, XlsxExtractor
from pii_scanner.core.extractors.pdf import PdfExtractor
from pii_scanner.core.extractors.hwp import HwpExtractor


class UnsupportedFormat(Exception):
    pass


_MAP = {
    ".txt": PlaintextExtractor,
    ".csv": PlaintextExtractor,
    ".hwpx": HwpxExtractor,
    ".docx": DocxExtractor,
    ".xlsx": XlsxExtractor,
    ".pdf": PdfExtractor,
    ".hwp": HwpExtractor,
}


def get_extractor(path: str):
    ext = os.path.splitext(path)[1].lower()
    cls = _MAP.get(ext)
    if cls is None:
        raise UnsupportedFormat(ext)
    return cls()
