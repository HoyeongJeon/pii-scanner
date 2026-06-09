from __future__ import annotations

import docx
import openpyxl

from pii_scanner.core.extractors.base import Extractor


class DocxExtractor(Extractor):
    def extract(self, path: str) -> str:
        d = docx.Document(path)
        parts = [p.text for p in d.paragraphs]
        for table in d.tables:
            for row in table.rows:
                parts.extend(cell.text for cell in row.cells)
        return "\n".join(parts)


class XlsxExtractor(Extractor):
    def extract(self, path: str) -> str:
        wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
        parts: list[str] = []
        for ws in wb.worksheets:
            for row in ws.iter_rows(values_only=True):
                for cell in row:
                    if cell is not None:
                        parts.append(str(cell))
        wb.close()
        return "\n".join(parts)
