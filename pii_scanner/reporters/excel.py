from __future__ import annotations

import os

import openpyxl

from pii_scanner.core.models import ScanResult, Status
from pii_scanner.reporters.budget import RowBudget
from pii_scanner.reporters.summary import Summary, summarize

# Excel 시트 행 한도(1,048,576) 미만으로 findings 행을 캡 — 초과분은 생략하고
# summary 시트에 생략 건수를 기록한다(전체 데이터는 state JSONL 이 원본).
MAX_FINDINGS_ROWS = 1_048_000


def write_excel_stream(files, out_path: str, summary: Summary,
                       max_findings: int = MAX_FINDINGS_ROWS) -> None:
    """FileResult 이터러블을 1회 순회하며 report.xlsx 를 스트리밍으로 쓴다(T-014).

    대형 스캔(hit 4,300만/state 7.7GB)은 전체 결과를 RAM 이나 시트에
    담을 수 없다 — write_only 워크북으로 행 단위 append 만 하고, findings 가
    max_findings 를 넘으면 이후 행은 생략한다. 이터러블은 1회성(제너레이터)일 수
    있으므로 집계는 summarize_iter 로 미리 계산해 summary 로 받는다.
    """
    s = summary
    budget = RowBudget(s, max_findings)     # 고유식별정보·노출 → 고유식별정보·마스킹 → 나머지
    wb = openpyxl.Workbook(write_only=True)

    ws = wb.create_sheet("findings")
    ws.append([
        "파일경로", "파일명", "PII종류", "위험등급", "상태", "마스킹스니펫", "위치", "검증",
    ])
    we = wb.create_sheet("errors")
    we.append(["파일경로", "사유"])
    wenc = wb.create_sheet("encrypted")
    wenc.append(["파일경로"])

    for fr in files:
        if fr.encrypted:
            wenc.append([fr.path])
            continue                       # 암호화 파일은 hits 없음
        if fr.error:
            we.append([fr.path, fr.error])
        for h in fr.hits:
            if not budget.allow(h):
                continue
            ws.append([
                fr.path,
                os.path.basename(fr.path),
                h.pii_type.value,
                h.risk.value,
                h.status.value,
                h.snippet,          # 마스킹 스니펫 — 원문 아님
                h.location or "",
                h.confidence.value,
            ])

    wsum = wb.create_sheet("summary")
    wsum.append(["항목", "값"])
    wsum.append(["스캔 파일 수", s.total_files])
    wsum.append(["추출 실패 수", s.error_files])
    wsum.append(["암호화 건너뜀 수", s.encrypted_files])
    wsum.append(["노출(EXPOSED)", s.exposed])
    wsum.append(["마스킹(MASKED)", s.masked])
    wsum.append(["마스킹률(%)", round(s.masking_rate, 1)])
    wsum.append(["법인등록번호 오탐 제거", s.corp_filtered])
    if budget.skipped:
        wsum.append(["findings 생략 행수(시트 한도 초과 — 고유식별정보 우선 수록, "
                     "전체는 state JSONL 참조)", budget.skipped])
    wsum.append([])
    wsum.append(["PII종류", "노출", "마스킹"])
    for pii_type, b in s.by_type.items():
        wsum.append([pii_type.value, b["exposed"], b["masked"]])

    wb.save(out_path)


def write_excel(result: ScanResult, out_path: str) -> None:
    write_excel_stream(result.files, out_path, summarize(result))
