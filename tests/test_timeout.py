"""인터럽트 가능한 제한시간 유틸 테스트 (T-016)."""
import time

import pytest

from pii_scanner.core.timeout import run_with_timeout, CallTimeout


def test_returns_result_when_fast():
    assert run_with_timeout(lambda: 1 + 1, timeout=5) == 2


def test_propagates_callee_exception():
    def boom():
        raise ValueError("callee 예외")
    with pytest.raises(ValueError, match="callee 예외"):
        run_with_timeout(boom, timeout=5)


def test_interrupts_pure_python_spin():
    # 순수 파이썬 무한 스핀(pdfminer 폭탄과 동형)이 비동기 예외 주입으로 실제로 끊겨야 한다.
    def spin():
        while True:
            pass
    t0 = time.monotonic()
    with pytest.raises(CallTimeout):
        run_with_timeout(spin, timeout=0.3, poll=0.1, tries=20)
    assert time.monotonic() - t0 < 8      # 무한 대기가 아니라 실제 중단됨
