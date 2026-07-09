from __future__ import annotations

import os
from collections.abc import Iterator

from pii_scanner.config import ScanConfig
from pii_scanner.connectors.base import SourceFile, Connector


def walk_files(roots: list[str], config: ScanConfig) -> Iterator[str]:
    """여러 루트를 순회하며 스캔 대상 파일 경로를 yield (읽기 전용)."""
    for root in roots:
        for dirpath, dirnames, filenames in os.walk(root):
            # 제외 디렉터리 가지치기
            dirnames[:] = [
                d for d in dirnames
                if not any(ex.lower() in d.lower() for ex in config.exclude_dirs)
            ]
            for name in filenames:
                ext = os.path.splitext(name)[1].lower()
                if ext in config.extensions:
                    yield os.path.join(dirpath, name)


class LocalSourceFile(SourceFile):
    """로컬 파일 — 진입 시 실제 경로 반환, 정리 없음(원본 보존)."""

    def __init__(self, path: str):
        self.logical_path = path

    def __enter__(self) -> str:
        return self.logical_path

    def __exit__(self, *exc) -> None:
        return None


class LocalFsConnector(Connector):
    """로컬 디렉터리 순회 커넥터(`walk_files` 래핑)."""

    def __init__(self, roots: list[str]):
        self.roots = roots

    def iter_files(self, config: ScanConfig) -> Iterator[SourceFile]:
        for path in walk_files(self.roots, config):
            yield LocalSourceFile(path)
