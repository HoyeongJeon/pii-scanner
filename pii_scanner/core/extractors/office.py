from __future__ import annotations

import os

import docx
import openpyxl
import xlrd

from pii_scanner.core.extractors.base import Extractor, EncryptedFileError
from pii_scanner.core.locate import CellLocator, Locator

# 비밀번호 걸린 OOXML 은 OLE 복합문서로 저장된다 — 이 매직으로 시작하면 암호화로 판정.
_OLE_MAGIC = b"\xD0\xCF\x11\xE0\xA1\xB1\x1A\xE1"


def _raise_if_encrypted(path: str) -> None:
    with open(path, "rb") as f:
        head = f.read(8)
    if head == _OLE_MAGIC:
        raise EncryptedFileError(f"암호화된 OOXML 추정(OLE 컨테이너): {os.path.basename(path)}")


class DocxExtractor(Extractor):
    def extract(self, path: str) -> str:
        _raise_if_encrypted(path)
        d = docx.Document(path)
        parts = [p.text for p in d.paragraphs]
        for table in d.tables:
            for row in table.rows:
                parts.extend(cell.text for cell in row.cells)
        return "\n".join(parts)


class XlsxExtractor(Extractor):
    def extract(self, path: str) -> str:
        return self.extract_located(path)[0]

    def extract_located(self, path: str) -> tuple[str, Locator]:
        _raise_if_encrypted(path)
        wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
        parts: list[str] = []
        segments: list[tuple[int, str]] = []
        pos = 0
        for ws in wb.worksheets:
            for row in ws.iter_rows():
                for cell in row:
                    if cell.value is not None:     # EmptyCell(value=None)은 coordinate 접근 전에 걸러짐
                        s = str(cell.value)
                        segments.append((pos, f"{ws.title}!{cell.coordinate}"))
                        parts.append(s)
                        pos += len(s) + 1          # "\n".join → 파트마다 개행 1자
        wb.close()
        return "\n".join(parts), CellLocator(segments)


class XlsExtractor(Extractor):
    """구 엑셀 .xls(BIFF) — xlrd 로 읽기 전용 텍스트 추출.

    .xls 는 정상도 OLE(D0CF11E0)라 _raise_if_encrypted(OOXML 용 매직 검사)를 쓰지 않는다.
    암호화는 xlrd 가 던지는 XLRDError('...encrypted...') 신호로만 판정한다(보수적).
    """

    def extract(self, path: str) -> str:
        return self.extract_located(path)[0]

    def extract_located(self, path: str) -> tuple[str, Locator]:
        try:
            book = xlrd.open_workbook(path)
        except xlrd.XLRDError as exc:
            if "encrypt" in str(exc).lower():
                raise EncryptedFileError(f"암호화된 xls: {path}") from exc
            raise                                  # 그 외 XLRDError 는 그대로 전파
        parts: list[str] = []
        segments: list[tuple[int, str]] = []
        pos = 0
        for sheet in book.sheets():
            for r in range(sheet.nrows):
                for c in range(sheet.ncols):
                    v = sheet.cell_value(r, c)
                    if v != "":
                        s = str(v)
                        segments.append((pos, f"{sheet.name}!{xlrd.colname(c)}{r + 1}"))
                        parts.append(s)
                        pos += len(s) + 1
        return "\n".join(parts), CellLocator(segments)
