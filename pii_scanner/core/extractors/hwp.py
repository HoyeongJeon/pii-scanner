from __future__ import annotations

# pyhwp(hwp5) 는 선택적 의존성(`pip install pii-scanner[hwp]`)이므로
# 최상단 import 대신 extract() 호출 시점에 지연 import 한다.
# 이 방식은 .hwp 파일을 처리하지 않는 배포에서 의존성 설치를 강제하지 않기 위함이다.
# (다른 추출기들은 필수 의존성이라 최상단 import 를 사용한다.)

import io
from contextlib import closing

from pii_scanner.core.extractors.base import Extractor


class HwpExtractor(Extractor):
    """pyhwp(hwp5) 로 .hwp 바이너리에서 텍스트 추출.

    pyhwp 0.1b15 기준 텍스트 추출 경로:
        hwp5.hwp5txt.TextTransform → transform_hwp5_to_text(hwp5file, dest)
    내부 비공개 심볼(_gen_text, hwp5.proc)은 사용하지 않는다.
    """

    def extract(self, path: str) -> str:
        # 지연 import: six 등 전이 의존성 누락 시 사용자 친화적 에러로 변환한다.
        try:
            from hwp5.hwp5txt import TextTransform
            from hwp5.xmlmodel import Hwp5File
        except (ImportError, ModuleNotFoundError) as exc:
            raise ImportError(
                ".hwp 추출을 위해 pyhwp 와 전이 의존성(six 등)이 필요합니다. "
                "'pip install pyhwp six' 로 설치하거나 "
                "'pip install pii-scanner[hwp]' 를 사용하세요. "
                f"(원인: {exc})"
            ) from exc

        # pyhwp 0.1b15 의 XSLT 백엔드(_lxml.py:_transform)는 binary stream 계약을 가진다:
        #   result = bytes(result); output.write(result)
        # 따라서 StringIO 가 아닌 BytesIO 를 사용해야 하며, getvalue() 결과를 decode 한다.
        buf = io.BytesIO()
        text_transform = TextTransform()
        transform = text_transform.transform_hwp5_to_text
        with closing(Hwp5File(path)) as hwp5file:
            transform(hwp5file, buf)
        return buf.getvalue().decode("utf-8")
