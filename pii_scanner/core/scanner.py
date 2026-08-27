from __future__ import annotations

import os
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed

from pii_scanner.config import ScanConfig
from pii_scanner.connectors.base import Connector
from pii_scanner.connectors.local_fs import LocalFsConnector
from pii_scanner.core.detectors import build_detectors
from pii_scanner.core.extractors import (
    get_extractor, UnsupportedFormat, EncryptedFileError,
)
from pii_scanner.core.models import FileResult, ScanResult
from pii_scanner.core.postfilter import filter_corp_columns


def process_file(sf, detectors) -> FileResult | None:
    """process_file 본체를 breadcrumb(현재 처리 파일 흔적)로 감싼다.

    PII_BREADCRUMB_DIR 환경변수가 있으면, 추출 시작 전 그 디렉터리에 스레드별 파일로 현재
    logical_path 를 기록하고 끝나면 지운다 — 워커가 어떤 파일에서 교착됐는지(T-016) 외부
    감시견이 알아내 스킵리스트에 넣을 수 있게 하는 관찰 지점. env 미설정 시 완전 무동작.
    """
    bcdir = os.environ.get("PII_BREADCRUMB_DIR")
    crumb = os.path.join(bcdir, str(threading.get_ident())) if bcdir else None
    if crumb:
        try:
            with open(crumb, "w", encoding="utf-8") as f:
                f.write(sf.logical_path)
        except OSError:
            crumb = None
    try:
        return _process_file_body(sf, detectors)
    finally:
        if crumb:
            try:
                os.remove(crumb)
            except OSError:
                pass


def _process_file_body(sf, detectors) -> FileResult | None:
    """다운로드→추출→탐지. 격리된 FileResult 반환(미지원 포맷은 None).

    예외를 밖으로 던지지 않는다 — 워커 스레드에서 호출돼도 한 파일 실패가 배치를 막지 않게.
    추출뿐 아니라 탐지 단계의 예외도 fr.error 로 격리한다(탐지기가 던져도 워커가 죽지 않게).
    """
    fr = FileResult(path=sf.logical_path)
    text: str | None = None
    locator = None
    try:
        with sf as local_path:                 # 필요시 다운로드, 종료 시 temp 삭제
            text, locator = get_extractor(sf.logical_path).extract_located(local_path)
    except UnsupportedFormat:
        return None                            # 대상 아님 — 기록조차 안 함
    except EncryptedFileError:
        fr.encrypted = True                     # 🔒 건너뜀(실패 아님)
    except Exception as exc:                    # 파일별 격리
        fr.error = f"추출 실패: {type(exc).__name__}: {exc}"
    if text is not None:
        try:
            hits = []
            for det in detectors:
                for hit in det.find(text):
                    hit.location = locator.label(hit.start)
                    hits.append(hit)
            kept, dropped = filter_corp_columns(hits)
            fr.hits.extend(kept)
            fr.corp_filtered = dropped
        except Exception as exc:                # 탐지 단계도 격리 — 워커 밖으로 안 던짐
            fr.error = f"탐지 실패: {type(exc).__name__}: {exc}"
    return fr


def scan(connector: Connector, config: ScanConfig, state=None) -> ScanResult:
    """커넥터가 흘려보내는 파일을 스트리밍 스캔한다.

    state(선택): 재개용. 이미 완료한 logical_path 는 건너뛰고, 완료마다 결과를 적재한다.
    state가 있으면 결과는 state에만 쌓고 반환 ScanResult.files는 비워 둔다 — 수만 파일
    장기 실행에서 반환용 램 누적이 OOM을 유발(T-012)했고, state 경로의 소비자는 전부
    state.load_results()를 쓴다(T-008에서 통일).
    """
    detectors = build_detectors(config)
    result = ScanResult()
    for sf in connector.iter_files(config):
        if state is not None and state.is_done(sf.logical_path):
            continue
        fr = process_file(sf, detectors)
        if fr is None:                          # 미지원 포맷 — 기록 안 함
            continue
        if state is not None:
            state.record(fr)
        else:
            result.files.append(fr)
    return result


def scan_parallel(connector: Connector, config: ScanConfig, state=None,
                  max_workers: int = 8) -> ScanResult:
    """배치(페이지) 단위로 파일을 동시 처리한다. 가속용 — scan() 과 결과 동등.

    워커는 process_file(다운로드→추출→탐지)만 수행하고, 기록(result.files / state.record)은
    메인 스레드에서 as_completed 로 단독 처리한다 → state 는 싱글스레드(락 불필요).
    한 배치의 모든 파일을 기록한 뒤에야 다음 배치를 요청하므로(커서 저장),
    페이지 경계 배리어가 보존된다(재개·무누락).
    state가 있으면 결과는 state에만 쌓는다(반환 files 비움) — scan()과 같은 이유(T-012).
    """
    detectors = build_detectors(config)
    result = ScanResult()
    for batch in connector.iter_batches(config):
        todo = [sf for sf in batch
                if not (state is not None and state.is_done(sf.logical_path))]
        if not todo:
            continue
        with ThreadPoolExecutor(max_workers=max_workers) as ex:
            futures = [ex.submit(process_file, sf, detectors) for sf in todo]
            for fut in as_completed(futures):
                fr = fut.result()
                if fr is None:
                    continue
                if state is not None:
                    state.record(fr)
                else:
                    result.files.append(fr)
    return result


def scan_paths(roots: list[str], config: ScanConfig) -> ScanResult:
    """하위 호환 — 로컬 경로 스캔(기존 CLI·테스트용)."""
    return scan(LocalFsConnector(roots), config)
