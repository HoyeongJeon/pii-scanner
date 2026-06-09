from __future__ import annotations

import os

import openpyxl

from pii_scanner.core.models import ScanResult, Status
from pii_scanner.reporters.summary import summarize


def write_excel(result: ScanResult, out_path: str) -> None:
    wb = openpyxl.Workbook()

    ws = wb.active
    ws.title = "findings"
    ws.append([
        "파일경로", "파일명", "PII종류", "위험등급", "상태", "마스킹스니펫", "검증",
    ])
    for fr in result.files:
        for h in fr.hits:
            ws.append([
                fr.path,
                os.path.basename(fr.path),
                h.pii_type.value,
                h.risk.value,
                h.status.value,
                h.snippet,          # 마스킹 스니펫 — 원문 아님
                h.confidence.value,
            ])

    we = wb.create_sheet("errors")
    we.append(["파일경로", "사유"])
    for fr in result.files:
        if fr.error:
            we.append([fr.path, fr.error])

    s = summarize(result)
    wsum = wb.create_sheet("summary")
    wsum.append(["항목", "값"])
    wsum.append(["스캔 파일 수", s.total_files])
    wsum.append(["추출 실패 수", s.error_files])
    wsum.append(["노출(EXPOSED)", s.exposed])
    wsum.append(["마스킹(MASKED)", s.masked])
    wsum.append(["마스킹률(%)", round(s.masking_rate, 1)])
    wsum.append([])
    wsum.append(["PII종류", "노출", "마스킹"])
    for pii_type, b in s.by_type.items():
        wsum.append([pii_type.value, b["exposed"], b["masked"]])

    wb.save(out_path)
