"""워커 스레드 안에서 실행되는 호출에 '인터럽트 가능한' 제한시간을 건다 (T-016).

process_file 은 스레드풀 워커에서 돈다. 파이썬 스레드는 밖에서 죽일 수 없어, 한 파일 처리가
무한정 스핀(예: 병리적 PDF에 pdfminer가 빠지는 파싱 폭탄)하면 워커가 영영 안 돌아오고
스레드풀이 교착된다. 순수 파이썬 스핀은 CPython 의 비동기 예외 주입
(`PyThreadState_SetAsyncExc`)으로 바이트코드 사이에서 끊을 수 있다 — 그걸 이용한다.

한계: C 레벨 블로킹(서브프로세스 대기 등)은 이 방식으로 못 끊는다. 그런 호출(poppler 등)은
각자의 timeout 으로 막아야 한다.
"""
from __future__ import annotations

import ctypes
import threading
from collections.abc import Callable
from typing import Any


class CallTimeout(Exception):
    """run_with_timeout 이 제한시간 초과로 호출을 중단시켰음."""


def _async_raise(tid: int, exctype: type) -> None:
    n = ctypes.pythonapi.PyThreadState_SetAsyncExc(
        ctypes.c_long(tid), ctypes.py_object(exctype))
    if n > 1:                                   # 비정상: 여러 스레드에 걸림 → 되돌림
        ctypes.pythonapi.PyThreadState_SetAsyncExc(ctypes.c_long(tid), None)


def run_with_timeout(fn: Callable[[], Any], timeout: float,
                     poll: float = 5.0, tries: int = 6) -> Any:
    """fn() 을 보조 스레드에서 실행. timeout 초 내 미완료면 예외를 주입해 중단하고 CallTimeout.

    fn 이 던진 예외는 그대로 재전파한다(호출부의 기존 예외 처리가 동작하도록).
    주입이 한 번에 안 먹을 수 있어(중간 except 로 삼켜지는 경우) 여러 번 시도한다.
    그래도 안 죽는 스레드는 daemon 이라 프로세스 종료 시 정리된다.
    """
    box: dict[str, Any] = {}

    def run() -> None:
        try:
            box["value"] = fn()
        except BaseException as exc:            # 주입된 CallTimeout 포함
            box["error"] = exc

    t = threading.Thread(target=run, daemon=True)
    t.start()
    t.join(timeout)
    if not t.is_alive():
        if "error" in box:
            raise box["error"]
        return box.get("value")

    tid = t.ident
    for _ in range(tries):
        if tid is not None:
            _async_raise(tid, CallTimeout)
        t.join(poll)
        if not t.is_alive():
            break
    raise CallTimeout(f"호출이 제한시간 {timeout}s 를 초과했습니다")
