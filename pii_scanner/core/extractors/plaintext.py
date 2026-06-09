from __future__ import annotations

from pii_scanner.core.extractors.base import Extractor


class PlaintextExtractor(Extractor):
    def extract(self, path: str) -> str:
        with open(path, "rb") as f:
            raw = f.read()
        for enc in ("utf-8", "cp949", "euc-kr"):
            try:
                return raw.decode(enc)
            except UnicodeDecodeError:
                continue
        return raw.decode("utf-8", errors="replace")
