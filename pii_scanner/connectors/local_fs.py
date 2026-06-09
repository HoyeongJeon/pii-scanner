from __future__ import annotations

import os
from collections.abc import Iterator

from pii_scanner.config import ScanConfig


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
