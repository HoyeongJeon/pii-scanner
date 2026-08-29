from __future__ import annotations

import re
import zipfile

from pii_scanner.core.extractors.base import Extractor

# <t> 태그 본문과 문단 경계를 문서 순서대로 함께 훑는다(네임스페이스 무시).
# 문단마다 개행을 넣지 않으면 서로 무관한 두 문단의 숫자가 이어 붙어 체크섬까지 통과하는
# '없는 주민번호'가 만들어진다 — 실제로 "기준일자 900101" + "1123459 호" 두 문단이
# 9001011123459 로 융합돼 confirmed 노출로 잡혔다. 게다가 개행이 섹션당 1회뿐이라
# 문서 전체가 1줄이 되어 200페이지 hwpx 의 모든 탐지 위치가 L1 로 찍혔다(찾아갈 수 없다).
# </p> 를 경계로 쓰면 표 안의 중첩 문단(hp:tc > hp:p)도 각각 한 줄이 된다.
# 같은 문단 안의 여러 <t> 는 그대로 이어 붙인다 — 한 주민번호가 서식 때문에 여러 run 으로
# 쪼개지는 정상 케이스를 깨면 안 되기 때문.
_TOKEN = re.compile(
    r"<(?:\w+:)?t\b[^>]*>(.*?)</(?:\w+:)?t>"     # 그룹1: 텍스트 런 본문
    r"|</(?:\w+:)?p>"                             # 문단 끝 → 개행
    r"|<(?:\w+:)?p\b[^>]*/>",                     # 빈 문단(자기닫힘) → 개행
    re.DOTALL,
)
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
                for m in _TOKEN.finditer(xml):
                    inner = m.group(1)
                    if inner is None:                  # 문단 경계
                        parts.append("\n")
                    else:
                        parts.append(_unescape(_TAG.sub("", inner)))
                # 문단 태그가 하나도 없는(비표준) 섹션에서도 섹션끼리 붙지 않게 한다.
                if parts and not parts[-1].endswith("\n"):
                    parts.append("\n")
        return "".join(parts)
