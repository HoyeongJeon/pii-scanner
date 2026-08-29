from __future__ import annotations

import errno
import os
from collections.abc import Callable, Iterator

from pii_scanner.config import ScanConfig
from pii_scanner.connectors.base import SourceFile, Connector
from pii_scanner.core.models import FileResult

# os.walk 은 onerror 를 안 주면 listdir 실패를 통째로 삼킨다. 그러면 "그 폴더에 개인정보
# 없음"과 "그 폴더를 열지도 못했음"이 완전히 같은 출력(파일 0건·노출 0건·종료코드 0)이 되어,
# 경로 오타나 ACL 로 막힌 트리를 아무도 알아챌 수 없다 — 감사 결과가 거짓 안심이 되는
# 이 도구 최악의 실패 유형이라 반드시 결과로 드러낸다.
#
# 사유는 OSError.strerror 대신 errno 로 고른 고정 문구를 쓴다. strerror 는 로캘에 따라
# 문구가 달라져 리포트가 재현되지 않고, 리포트에 실리는 문자열은 전부 우리가 통제한다는
# 원칙(서드파티 예외 문자열을 그대로 싣지 않는다)을 코드로 지키기 위해서다.
# 표를 3개로 좁게 유지하는 이유: 항목마다 회귀 테스트가 있어야 지워도 조용히 안 넘어간다.
_ACCESS_REASONS = {
    errno.ENOENT: "접근 실패: 경로 없음",
    errno.EACCES: "접근 실패: 권한 없음",
    errno.ENOTDIR: "접근 실패: 디렉터리가 아님",
}


def access_reason(err: OSError) -> str:
    """폴더 접근 실패 사유(한국어 고정 문구). 표에 없으면 예외 타입명만 — 메시지 본문은 안 싣는다."""
    return _ACCESS_REASONS.get(err.errno, f"접근 실패: {type(err).__name__}")


def walk_files(roots: list[str], config: ScanConfig,
               on_error: Callable[[OSError], None] | None = None) -> Iterator[str]:
    """여러 루트를 순회하며 스캔 대상 파일 경로를 yield (읽기 전용).

    on_error: os.walk 이 기본값(None)으로는 조용히 삼키는 listdir 실패(OSError)를 받는 콜백.
      없는 경로(ENOENT)·권한 없는 폴더(EACCES)·디렉터리 대신 파일을 루트로 준 경우(ENOTDIR)가
      전부 이 하나의 통로로 온다(실측 확인). 기본 None 은 예전 동작(무시).

    한계: os.walk 은 followlinks=False 라 심볼릭 링크된 하위 디렉터리를 내려가지 않으면서
    onerror 도 부르지 않는다 — 링크로 걸린 서브트리는 여기서 잡히지 않는다.
    """
    for root in roots:
        for dirpath, dirnames, filenames in os.walk(root, onerror=on_error):
            # 제외 디렉터리 가지치기 (가지친 폴더는 아예 열지 않으므로 접근 실패로도 안 잡힌다)
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
    """로컬 디렉터리 순회 커넥터(`walk_files` 래핑).

    순회 중 읽지 못한 경로는 삼키지 않고 FileResult(unreadable=True) 로 모아 두고,
    iter_files() 를 끝까지 소비한 뒤 iter_access_errors() 로 내준다.
    """

    def __init__(self, roots: list[str]):
        self.roots = roots
        self._access_errors: list[FileResult] = []

    def iter_files(self, config: ScanConfig) -> Iterator[SourceFile]:
        # 제너레이터라 첫 next() 때 실행된다 — 같은 커넥터를 두 번 순회해도 접근 실패가
        # 중복 누적되지 않게 여기서 비운다.
        self._access_errors.clear()
        for path in walk_files(self.roots, config, on_error=self._on_walk_error):
            yield LocalSourceFile(path)

    def _on_walk_error(self, err: OSError) -> None:
        # err.filename 은 os.walk 이 열지 못한 그 경로. 경로는 findings 에도 실리는 정보라
        # 리포트에 넣어도 되지만, 사유는 예외 메시지 대신 고정 문구로 바꿔 싣는다.
        self._access_errors.append(FileResult(
            path=err.filename or "(경로 미상)",
            error=access_reason(err),
            unreadable=True,
        ))

    def iter_access_errors(self) -> Iterator[FileResult]:
        return iter(self._access_errors)
