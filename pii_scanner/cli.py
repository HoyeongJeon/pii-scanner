from __future__ import annotations

import argparse
import os
import sys

from pii_scanner.config import ScanConfig
from pii_scanner.core.detectors import ALL_DETECTOR_KEYS
from pii_scanner.core.scanner import scan_parallel, scan_paths
from pii_scanner.reporters.excel import write_excel, write_excel_stream
from pii_scanner.reporters.html import write_html, write_html_stream
from pii_scanner.reporters.summary import summarize, summarize_iter

# 주의: dropbox SDK 에 의존하는 모듈(dropbox_conn/dropbox_client)은 최상단에서 import 하지
# 않는다. cli 는 로컬 스캔의 진입점이기도 하므로, 여기서 import 하면 [dropbox] extra 미설치
# 환경에서 로컬 스캔까지 ImportError 로 깨진다. → dropbox 관련 import 는 각 핸들러 안에서 지연.


def _validate_keys(parser, keys):
    unknown = set(keys) - ALL_DETECTOR_KEYS
    if unknown:
        parser.error(
            f"알 수 없는 탐지기 키: {', '.join(sorted(unknown))}. "
            f"사용 가능: {', '.join(sorted(ALL_DETECTOR_KEYS))}"
        )


def _write_reports(result, out_dir):
    os.makedirs(out_dir, exist_ok=True)
    write_excel(result, os.path.join(out_dir, "report.xlsx"))
    write_html(result, os.path.join(out_dir, "report.html"))
    _print_summary(summarize(result), out_dir)


def _write_reports_from_state(state, out_dir):
    """state JSONL 을 스트리밍(3회 순회: 집계·excel·html)으로 리포트 생성 — O(1) 메모리.

    load_results() 경유는 대형 스캔에서 MemoryError(T-014) — dropbox 경로는 항상 이걸 쓴다.
    """
    os.makedirs(out_dir, exist_ok=True)
    s = summarize_iter(state.iter_results())
    write_excel_stream(state.iter_results(), os.path.join(out_dir, "report.xlsx"), s)
    write_html_stream(state.iter_results(), os.path.join(out_dir, "report.html"), s)
    _print_summary(s, out_dir)


def _print_summary(s, out_dir):
    print(f"스캔 완료: 파일 {s.total_files}건, 노출 {s.exposed}건, "
          f"암호화 건너뜀 {s.encrypted_files}건, 추출실패 {s.error_files}건")
    print(f"리포트: {out_dir}/report.xlsx, report.html")


def _cmd_local(argv):
    parser = argparse.ArgumentParser(
        prog="pii-scan", description="개인정보(PII) 노출 스캐너 (읽기 전용)")
    parser.add_argument("roots", nargs="+", help="스캔할 폴더 경로(1개 이상)")
    parser.add_argument("--out", required=True, help="리포트 출력 폴더")
    parser.add_argument("--disable", action="append", default=[],
                        help="비활성화할 탐지기 키")
    parser.add_argument("--enable", action="append", default=[],
                        help="기본 비활성 탐지기 켜기 (예: foreign)")
    args = parser.parse_args(argv)
    _validate_keys(parser, args.disable)
    _validate_keys(parser, args.enable)
    result = scan_paths(args.roots, ScanConfig(
        disabled=set(args.disable), enabled=set(args.enable)))
    _write_reports(result, args.out)
    return 0


def _cmd_auth(argv):
    from pii_scanner.connectors import credentials, dropbox_client
    parser = argparse.ArgumentParser(prog="pii-scan auth", description="Dropbox 인증(1회)")
    parser.add_argument("--app-key", required=True, help="Dropbox 앱 키(본인 앱)")
    parser.add_argument("--profile", default=None,
                        help="자격증명 프로필 이름(부서별 계정을 분리 저장)")
    args = parser.parse_args(argv)
    token = dropbox_client.run_oauth_flow(args.app_key)
    path = credentials.save_credentials(args.app_key, token, profile=args.profile)
    print(f"인증 완료 — 자격증명 저장: {path}")
    return 0


def _cmd_dropbox(argv):
    import dropbox  # 지연 import — [dropbox] extra 미설치 시 로컬 스캔까지 깨지지 않게
    from pii_scanner.connectors import credentials, dropbox_client
    from pii_scanner.connectors.state import ScanState
    from pii_scanner.connectors.dropbox_conn import DropboxConnector
    parser = argparse.ArgumentParser(prog="pii-scan dropbox", description="Dropbox 스캔")
    parser.add_argument("--root", required=True, help="스캔 시작 경로(네임스페이스 기준)")
    parser.add_argument("--out", required=True, help="리포트 출력 폴더")
    parser.add_argument("--profile", default=None, help="자격증명 프로필(인증 때 쓴 이름)")
    parser.add_argument("--namespace", choices=["home", "team"], default="home",
                        help="스캔 네임스페이스 (home=계정 홈[기본], team=팀 공유공간)")
    parser.add_argument("--scan-id", default=None,
                        help="재개 식별자(기본: 프로필명 또는 'dropbox')")
    parser.add_argument("--disable", action="append", default=[])
    parser.add_argument("--enable", action="append", default=[],
                        help="기본 비활성 탐지기 켜기 (예: foreign)")
    parser.add_argument("--workers", type=int, default=8,
                        help="동시 다운로드·추출 워커 수(기본 8)")
    args = parser.parse_args(argv)
    _validate_keys(parser, args.disable)
    _validate_keys(parser, args.enable)
    if args.workers < 1:
        parser.error("--workers 는 1 이상이어야 합니다")
    scan_id = args.scan_id or args.profile or "dropbox"

    # 자격증명 부재·토큰 폐기는 트레이스백 대신 깔끔한 안내로.
    try:
        creds = credentials.load_credentials(profile=args.profile)
        dbx = dropbox_client.make_client(creds, namespace=args.namespace)
    except FileNotFoundError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    except dropbox.exceptions.AuthError as exc:
        print(f"인증 오류 — 토큰이 무효/폐기됨. 'pii-scan auth --app-key <KEY>' 로 재인증하세요. ({exc})",
              file=sys.stderr)
        return 1

    config = ScanConfig(disabled=set(args.disable), enabled=set(args.enable))
    state = ScanState(scan_id)
    connector = DropboxConnector(dbx, args.root, state=state)
    try:
        scan_parallel(connector, config, state=state, max_workers=args.workers)
    except KeyboardInterrupt:
        print("\n중단됨 — 진행상황 저장됨. 같은 --scan-id 로 다시 실행하면 이어서 진행합니다.")
        _write_reports_from_state(state, args.out)
        return 130          # POSIX: SIGINT 종료코드
    except dropbox.exceptions.ApiError as exc:
        print(f"Dropbox 경로/네임스페이스 확인 필요 — --root '{args.root}' "
              f"(--namespace {args.namespace})를 찾을 수 없거나 접근 불가합니다.\n  ({exc})",
              file=sys.stderr)
        _write_reports_from_state(state, args.out)
        return 1
    # 리포트는 상태파일 기준으로 그린다 — scan_parallel() 반환값엔 '이번 실행분'만 담기지만(재개 시
    # 이미 끝난 파일은 건너뜀), 리포트는 이전 실행 누적분까지 포함한 '전체'여야 하기 때문.
    _write_reports_from_state(state, args.out)
    return 0


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    if argv and argv[0] == "auth":
        return _cmd_auth(argv[1:])
    if argv and argv[0] == "dropbox":
        return _cmd_dropbox(argv[1:])
    return _cmd_local(argv)             # 기존 로컬 스캔(하위 호환)


if __name__ == "__main__":
    raise SystemExit(main())
