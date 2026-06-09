from __future__ import annotations

import argparse
import os

from pii_scanner.config import ScanConfig
from pii_scanner.core.detectors import ALL_DETECTOR_KEYS
from pii_scanner.core.scanner import scan_paths
from pii_scanner.reporters.excel import write_excel
from pii_scanner.reporters.html import write_html


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="pii-scan", description="개인정보(PII) 노출 스캐너 (읽기 전용)"
    )
    parser.add_argument("roots", nargs="+", help="스캔할 폴더 경로(1개 이상)")
    parser.add_argument("--out", required=True, help="리포트 출력 폴더")
    parser.add_argument(
        "--disable", action="append", default=[],
        help="비활성화할 탐지기 키 (rrn/foreign/passport/driver/phone/landline/email)",
    )
    args = parser.parse_args(argv)

    unknown = set(args.disable) - ALL_DETECTOR_KEYS
    if unknown:
        parser.error(
            f"알 수 없는 탐지기 키: {', '.join(sorted(unknown))}. "
            f"사용 가능: {', '.join(sorted(ALL_DETECTOR_KEYS))}"
        )

    config = ScanConfig(disabled=set(args.disable))
    result = scan_paths(args.roots, config)

    os.makedirs(args.out, exist_ok=True)
    write_excel(result, os.path.join(args.out, "report.xlsx"))
    write_html(result, os.path.join(args.out, "report.html"))

    n_exposed = sum(
        1 for fr in result.files for h in fr.hits if h.status.value == "노출"
    )
    print(f"스캔 완료: 파일 {len(result.files)}건, 노출 {n_exposed}건")
    print(f"리포트: {args.out}/report.xlsx, report.html")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
