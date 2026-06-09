import pytest
from pii_scanner.core.extractors import get_extractor, UnsupportedFormat
from pii_scanner.core.extractors.plaintext import PlaintextExtractor
from pii_scanner.core.extractors.hwpx import HwpxExtractor


def test_txt_maps_to_plaintext():
    assert isinstance(get_extractor("/x/a.txt"), PlaintextExtractor)


def test_hwpx_maps_correctly():
    assert isinstance(get_extractor("/x/a.HWPX"), HwpxExtractor)  # 대소문자 무시


def test_unsupported_raises():
    with pytest.raises(UnsupportedFormat):
        get_extractor("/x/a.zip")
