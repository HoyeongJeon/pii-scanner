from __future__ import annotations

import os
import random
import tempfile
import time
from collections.abc import Iterator

import dropbox
import requests

from pii_scanner.config import ScanConfig
from pii_scanner.connectors.base import SourceFile, Connector


def _retry(fn, max_tries: int = 5, sleep=time.sleep, rand=random.random):
    """429(Retry-After) / 5xx · 일시적 네트워크 오류(지수 백오프) 재시도. 그 외 예외는 즉시 전파.

    409 path_not_found 같은 ApiError 는 재시도 대상이 아니라 호출부로 전파된다(스킵+기록).
    """
    delay = 1.0
    last: BaseException | None = None
    for _ in range(max_tries):
        try:
            return fn()
        except dropbox.exceptions.RateLimitError as e:      # 429
            last = e
            wait = getattr(e, "backoff", None)
            sleep(wait if wait is not None else 1.0)        # Retry-After 준수(0 도 그대로)
        except dropbox.exceptions.InternalServerError as e:  # 5xx
            last = e
            sleep(delay + rand())                            # 지터
            delay *= 2
        except (requests.exceptions.ConnectionError,
                requests.exceptions.Timeout,
                requests.exceptions.ChunkedEncodingError) as e:  # 일시적 네트워크 오류
            last = e
            sleep(delay + rand())                            # 5xx 와 동일한 지수 백오프
            delay *= 2
    if last is None:                                        # max_tries < 1 — 호출 오류
        raise ValueError("_retry: max_tries 는 1 이상이어야 합니다")
    raise last


class DropboxSourceFile(SourceFile):
    """Dropbox 파일 — 진입 시 시스템 temp(동기화 폴더 밖)로 다운로드, 종료 시 삭제."""

    def __init__(self, dbx, dbx_path: str, logical_path: str, temp_dir: str | None = None):
        self.dbx = dbx
        self.dbx_path = dbx_path            # path_lower — 다운로드용
        self.logical_path = logical_path    # path_display — 리포트용
        self._temp_dir = temp_dir           # None → 시스템 temp(동기화 폴더 밖)
        self._temp_path: str | None = None

    def __enter__(self) -> str:
        suffix = os.path.splitext(self.logical_path)[1]
        fd, self._temp_path = tempfile.mkstemp(suffix=suffix, dir=self._temp_dir)
        os.close(fd)
        try:
            _retry(lambda: self.dbx.files_download_to_file(self._temp_path, self.dbx_path))
        except BaseException:
            self.__exit__(None, None, None)   # 다운로드 실패 시 temp 자기정리 후 전파
            raise
        return self._temp_path

    def __exit__(self, *exc) -> None:
        if self._temp_path:
            try:
                if os.path.exists(self._temp_path):
                    os.remove(self._temp_path)
            except OSError:
                pass  # best-effort — 정리 실패가 원래 예외를 가리지 않게
        self._temp_path = None


class DropboxConnector(Connector):
    """Dropbox 팀 공유 공간을 재귀 나열해 파일을 스트리밍한다.

    커서는 페이지를 '완전히 소진한 뒤'에만 저장한다 — 제너레이터는 다음 항목을 요청받을 때
    재개되므로, 페이지 루프가 끝나는 시점엔 그 페이지의 모든 파일이 이미 스캔·적재된 상태다.
    따라서 페이지 중간 크래시 시엔 커서가 이전 위치에 머물러 재나열되고, done-set 이 중복을 막는다.
    (이 불변식은 `scan(connector, config, state=state)` 로 구동될 때 성립한다 —
    scan 이 파일마다 state.record() 를 호출해 done-set 을 채우기 때문이다.)
    """

    def __init__(self, dbx, root: str, state=None, temp_dir: str | None = None):
        self.dbx = dbx
        self.root = root
        self.state = state
        self.temp_dir = temp_dir

    def iter_files(self, config: ScanConfig) -> Iterator[SourceFile]:
        cursor = self.state.load_cursor() if self.state else None
        if cursor is None:
            res = _retry(lambda: self.dbx.files_list_folder(self.root, recursive=True))
        else:
            res = _retry(lambda: self.dbx.files_list_folder_continue(cursor))

        while True:
            for entry in res.entries:
                if not isinstance(entry, dropbox.files.FileMetadata):
                    continue                                  # 폴더/삭제 등 제외
                ext = os.path.splitext(entry.name)[1].lower()
                if ext not in config.extensions:
                    continue
                yield DropboxSourceFile(
                    self.dbx, entry.path_lower, entry.path_display, self.temp_dir)
            nxt = res.cursor                                  # 람다 늦은바인딩 방지 위해 캡처
            if self.state is not None:
                self.state.save_cursor(nxt)                   # 페이지 소진 후 갱신
            if not res.has_more:
                break
            res = _retry(lambda: self.dbx.files_list_folder_continue(nxt))

    def iter_batches(self, config: ScanConfig) -> Iterator[list[SourceFile]]:
        """한 API 페이지를 배치 1개로 묶어 흘려보낸다. 커서는 페이지 소진 후에만 저장.

        소비자(scan_parallel)가 한 배치를 전부 기록한 뒤 다음 배치를 요청할 때 제너레이터가
        재개되어 그 페이지의 커서를 저장한다 → 페이지 경계 배리어가 보존된다(재개·무누락).
        """
        cursor = self.state.load_cursor() if self.state else None
        if cursor is None:
            res = _retry(lambda: self.dbx.files_list_folder(self.root, recursive=True))
        else:
            res = _retry(lambda: self.dbx.files_list_folder_continue(cursor))

        while True:
            batch = [
                DropboxSourceFile(
                    self.dbx, entry.path_lower, entry.path_display, self.temp_dir)
                for entry in res.entries
                if isinstance(entry, dropbox.files.FileMetadata)
                and os.path.splitext(entry.name)[1].lower() in config.extensions
            ]
            if batch:
                yield batch
            nxt = res.cursor
            if self.state is not None:
                self.state.save_cursor(nxt)
            if not res.has_more:
                break
            res = _retry(lambda: self.dbx.files_list_folder_continue(nxt))
