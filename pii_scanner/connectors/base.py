from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Iterator

from pii_scanner.config import ScanConfig


class SourceFile(ABC):
    """스캔 대상 파일 1개. 컨텍스트 매니저로 진입하면 읽을 수 있는 로컬 경로를 반환한다.

    구현체는 `logical_path`(리포트 표시용)를 설정하고, `__enter__`에서 다운로드(필요시),
    `__exit__`에서 정리(temp 삭제)를 수행한다.
    """

    logical_path: str

    @abstractmethod
    def __enter__(self) -> str:
        ...

    @abstractmethod
    def __exit__(self, *exc) -> None:
        ...


class Connector(ABC):
    """스캔 대상의 원천. 파일을 SourceFile 스트림으로 흘려보낸다."""

    @abstractmethod
    def iter_files(self, config: ScanConfig) -> Iterator[SourceFile]:
        ...

    def iter_batches(self, config: ScanConfig) -> Iterator[list[SourceFile]]:
        """파일을 배치(페이지) 단위로 흘려보낸다. 병렬 스캔의 동시 처리 단위.

        기본 구현은 파일 1개짜리 배치(배리어 = 파일 1개). 페이지·커서가 있는 커넥터
        (예: Dropbox)는 한 API 페이지를 1개 배치로 묶어 오버라이드한다.
        """
        for sf in self.iter_files(config):
            yield [sf]
