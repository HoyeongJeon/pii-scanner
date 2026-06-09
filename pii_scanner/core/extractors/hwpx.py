from __future__ import annotations

import re
import zipfile

from pii_scanner.core.extractors.base import Extractor

# 네임스페이스 무시하고 <...:t> 태그 본문 추출
_T = re.compile(r"<(?:\w+:)?t\b[^>]*>(.*?)</(?:\w+:)?t>", re.DOTALL)
_TAG = re.compile(r"<[^>]+>")


def _unescape(s: str) -> str:
    return (
        s.replace("&lt;", "<").replace("&gt;", ">")
        .replace("&amp;", "&").replace("&quot;", '"').replace("&apos;", "'")
    )


class HwpxExtractor(Extractor):
    def extract(self, path: str) -> str:
        parts: list[str] = []
        with zipfile.ZipFile(path) as z:
            names = sorted(
                n for n in z.namelist()
                if n.startswith("Contents/section") and n.endswith(".xml")
            )
            for name in names:
                xml = z.read(name).decode("utf-8", errors="replace")
                for m in _T.finditer(xml):
                    inner = _TAG.sub("", m.group(1))
                    parts.append(_unescape(inner))
                parts.append("\n")
        return "".join(parts)
