from __future__ import annotations

from pii_scanner.config import ScanConfig
from pii_scanner.connectors.local_fs import walk_files
from pii_scanner.core.detectors import build_detectors
from pii_scanner.core.extractors import get_extractor, UnsupportedFormat
from pii_scanner.core.models import FileResult, ScanResult


def scan_paths(roots: list[str], config: ScanConfig) -> ScanResult:
    detectors = build_detectors(config)
    result = ScanResult()
    for path in walk_files(roots, config):
        fr = FileResult(path=path)
        try:
            extractor = get_extractor(path)
            text = extractor.extract(path)
        except UnsupportedFormat:
            continue  # 순회 단계에서 걸러지지만 방어적으로 스킵
        except Exception as exc:  # 추출 실패 — 기록하고 계속
            fr.error = f"추출 실패: {type(exc).__name__}: {exc}"
            result.files.append(fr)
            continue
        for det in detectors:
            fr.hits.extend(det.find(text))
        result.files.append(fr)
    return result
