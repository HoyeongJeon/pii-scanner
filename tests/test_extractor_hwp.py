from __future__ import annotations

import io
import os
from unittest.mock import MagicMock, patch

import pytest

from pii_scanner.core.extractors.hwp import HwpExtractor

FIXTURE = os.path.join(os.path.dirname(__file__), "fixtures", "synthetic.hwp")

# ---------------------------------------------------------------------------
# Import-smoke: HwpExtractor 클래스 자체는 pyhwp 없어도 import 가능해야 한다.
# ---------------------------------------------------------------------------

def test_hwp_extractor_class_importable():
    """HwpExtractor 클래스는 pyhwp 설치 여부와 무관하게 import 가능해야 한다."""
    assert HwpExtractor is not None


# ---------------------------------------------------------------------------
# 의존성 누락 시 에러 변환: raw ModuleNotFoundError 대신 ImportError + 안내 메시지.
# 이 환경에서는 six 가 없어 pyhwp 가 완전히 broken 상태이므로 항상 실행된다.
# ---------------------------------------------------------------------------

_hwp5_importable: bool
try:
    # six 를 포함한 전체 import 체인이 성공하는지 확인
    import hwp5.dataio  # six 를 가장 먼저 끌어당기는 모듈
    _hwp5_importable = True
except Exception:
    _hwp5_importable = False


@pytest.mark.skipif(
    _hwp5_importable,
    reason="pyhwp(six 포함)가 정상 설치된 환경 — 의존성 누락 경로 테스트 불필요",
)
def test_hwp_extract_missing_dep_raises_import_error(tmp_path):
    """six 등 전이 의존성 누락 시 extract() 가 ModuleNotFoundError 가 아닌
    ImportError 를 발생시키고 'pyhwp' 와 설치 힌트를 메시지에 포함해야 한다."""
    dummy = tmp_path / "dummy.hwp"
    dummy.write_bytes(b"not a real hwp")
    with pytest.raises(ImportError, match="pyhwp"):
        HwpExtractor().extract(str(dummy))


# ---------------------------------------------------------------------------
# 통합 테스트: 실제 합성 .hwp 픽스처가 있을 때만 실행.
# 픽스처는 Windows+한글 환경에서 가짜 데이터로 생성해 커밋한다.
# ---------------------------------------------------------------------------

@pytest.mark.skipif(
    not os.path.exists(FIXTURE),
    reason="합성 .hwp 픽스처 필요 (Windows+한글에서 가짜 데이터로 생성 후 커밋)",
)
def test_hwp_extract_returns_text():
    text = HwpExtractor().extract(FIXTURE)
    assert isinstance(text, str)
    assert len(text) > 0


# ---------------------------------------------------------------------------
# 단위 테스트: pyhwp 의 bytes 출력 계약을 모킹으로 고정.
# transform_hwp5_to_text 는 dest 에 bytes 를 write 한다(binary stream 계약).
# extract() 는 BytesIO 를 dest 로 넘겨야 하며, 결과를 str 로 디코딩해야 한다.
# ---------------------------------------------------------------------------

def test_hwp_extract_uses_bytesio_and_decodes(tmp_path):
    """pyhwp transform 이 bytes 를 write 하더라도 extract() 가 str 을 반환해야 한다.

    pyhwp 0.1b15 의 XSLT 백엔드(_lxml.py:_transform)는 binary stream 계약을 가지며
    ``output.write(bytes(result))`` 를 수행한다. 따라서 dest 는 BytesIO 여야 한다.
    이 테스트는 transform 함수가 실제로 bytes 를 기록하는 상황을 sys.modules 모킹으로
    구현해, extract() 가 BytesIO 를 dest 로 사용하고 결과를 str 로 디코딩하는지 검증한다.
    """
    import sys

    dummy = tmp_path / "dummy.hwp"
    dummy.write_bytes(b"fake")

    sample_bytes = "합성텍스트\n".encode("utf-8")

    # pyhwp transform 이 dest(binary stream) 에 bytes 를 write 하는 동작을 재현한다.
    def fake_transform(hwp5file, dest):
        dest.write(sample_bytes)

    mock_transform_instance = MagicMock()
    mock_transform_instance.transform_hwp5_to_text = fake_transform

    mock_TextTransform = MagicMock(return_value=mock_transform_instance)

    mock_hwp5file_instance = MagicMock()
    mock_hwp5file_instance.close = MagicMock()
    mock_Hwp5File = MagicMock(return_value=mock_hwp5file_instance)

    # extract() 가 지연 import 하는 모듈을 sys.modules 에 주입한다.
    mock_hwp5txt_mod = MagicMock()
    mock_hwp5txt_mod.TextTransform = mock_TextTransform
    mock_xmlmodel_mod = MagicMock()
    mock_xmlmodel_mod.Hwp5File = mock_Hwp5File

    modules_to_inject = {
        "hwp5": MagicMock(),
        "hwp5.hwp5txt": mock_hwp5txt_mod,
        "hwp5.xmlmodel": mock_xmlmodel_mod,
    }
    original_modules = {k: sys.modules.get(k) for k in modules_to_inject}

    try:
        sys.modules.update(modules_to_inject)
        result = HwpExtractor().extract(str(dummy))
    finally:
        for k, v in original_modules.items():
            if v is None:
                sys.modules.pop(k, None)
            else:
                sys.modules[k] = v

    assert isinstance(result, str), "extract() 는 반드시 str 을 반환해야 한다"
    assert result == "합성텍스트\n", f"디코딩 결과 불일치: {result!r}"
