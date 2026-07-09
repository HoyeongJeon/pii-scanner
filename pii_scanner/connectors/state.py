from __future__ import annotations

import json
import os
import re

from pii_scanner.core.models import (
    FileResult, ScanResult, PiiHit, PiiType, Status, Confidence, RiskLevel,
)

# scan_id 는 파일명 구성요소가 되므로(그리고 CLI --scan-id 로 사용자 입력이 됨)
# 경로 순회(../ 등)·구분자를 차단한다.
_SCAN_ID_RE = re.compile(r"[\w\-]+")


def _hit_to_dict(h: PiiHit) -> dict:
    return {
        "pii_type": h.pii_type.value, "status": h.status.value,
        "snippet": h.snippet,                     # 마스킹된 스니펫 — 원문 아님
        "start": h.start, "end": h.end,
        "confidence": h.confidence.value, "risk": h.risk.value,
        "location": h.location,
    }


def _hit_from_dict(d: dict) -> PiiHit:
    return PiiHit(
        PiiType(d["pii_type"]), Status(d["status"]), d["snippet"],
        d["start"], d["end"], Confidence(d["confidence"]), RiskLevel(d["risk"]),
        location=d.get("location"),               # 구형 state 호환
    )


def _fr_to_dict(fr: FileResult) -> dict:
    return {
        "path": fr.path, "error": fr.error, "encrypted": fr.encrypted,
        "corp_filtered": fr.corp_filtered,
        "hits": [_hit_to_dict(h) for h in fr.hits],
    }


def _fr_from_dict(d: dict) -> FileResult:
    return FileResult(
        path=d["path"],
        error=d.get("error"),
        encrypted=d.get("encrypted", False),
        corp_filtered=d.get("corp_filtered", 0),   # 구형 state 호환
        hits=[_hit_from_dict(h) for h in d.get("hits", [])],
    )


def default_state_dir() -> str:
    return os.path.join(os.path.expanduser("~"), ".config", "pii-scanner", "state")


class ScanState:
    """재개용 체크포인트. 완료 결과를 JSONL 로 적재하고 목록 커서를 사이드카에 저장한다.

    JSONL 에는 마스킹된 스니펫만 들어간다(원문 PII 금지). 동기화 폴더 밖(`~/.config`)에 둔다.
    """

    def __init__(self, scan_id: str, base_dir: str | None = None):
        if not _SCAN_ID_RE.fullmatch(scan_id):
            raise ValueError(
                f"scan_id 는 영문/숫자/_/- 만 허용됩니다(경로 순회 차단): {scan_id!r}"
            )
        base = base_dir or default_state_dir()
        os.makedirs(base, exist_ok=True)
        self.jsonl_path = os.path.join(base, f"{scan_id}.jsonl")
        self.cursor_path = os.path.join(base, f"{scan_id}.cursor")
        self.done: set[str] = {fr.path for fr in self._iter_existing()}

    def _iter_existing(self):
        if not os.path.exists(self.jsonl_path):
            return
        with open(self.jsonl_path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    yield _fr_from_dict(json.loads(line))
                except (json.JSONDecodeError, KeyError, ValueError):
                    # 크래시로 마지막 줄이 잘렸을 때 건너뜀 — 나머지 레코드는 유효(재개 가능)
                    continue

    def is_done(self, path: str) -> bool:
        return path in self.done

    def record(self, fr: FileResult) -> None:
        with open(self.jsonl_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(_fr_to_dict(fr), ensure_ascii=False) + "\n")
        self.done.add(fr.path)

    def load_results(self) -> ScanResult:
        result = ScanResult()
        result.files = list(self._iter_existing())
        return result

    def save_cursor(self, cursor: str | None) -> None:
        with open(self.cursor_path, "w", encoding="utf-8") as f:
            f.write(cursor or "")

    def load_cursor(self) -> str | None:
        if not os.path.exists(self.cursor_path):
            return None
        with open(self.cursor_path, encoding="utf-8") as f:
            c = f.read().strip()
        return c or None
