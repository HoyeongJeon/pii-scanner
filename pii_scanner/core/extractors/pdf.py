from __future__ import annotations

from pdfminer.high_level import extract_text
from pdfminer.pdfdocument import PDFEncryptionError

from pii_scanner.core.extractors.base import Extractor, EncryptedFileError
from pii_scanner.core.locate import Locator, PageLineLocator
from pii_scanner.core.timeout import run_with_timeout

OCR_TEXT_THRESHOLD = 300   # 글자수 미만이면 스캔본으로 보고 OCR 폴백 (DECISIONLOG D-028 근거)
OCR_MAX_PAGES = 300        # 스캔본 OCR 페이지 상한 — 초과분 생략(수천 페이지 PDF 무한작업 방지, T-016)
POPPLER_TIMEOUT = 90       # poppler(pdfinfo/pdftoppm) 호출당 초 상한 — 멈춘 poppler를 죽여 교착 방지(T-016)
PDFMINER_TIMEOUT = 90      # pdfminer extract_text 초 상한 — 병리적 PDF의 순수파이썬 스핀(4.6GB 폭탄,
                           # T-016)을 비동기 예외로 끊고 OCR 폴백. 정상 문서는 훨씬 빨라 영향 없음.


class PdfExtractor(Extractor):
    def extract(self, path: str) -> str:
        import os
        if os.path.getsize(path) == 0:
            raise ValueError("빈 파일(0바이트) — 업로드 실패 잔재로 추정")
        try:
            # T-016: extract_text 를 인터럽트 가능한 timeout 으로 감싼다 — 병리적 PDF(0.3MB가
            # pdfminer에서 4.6GB로 스핀하는 폭탄)가 워커를 영구 점유해 스레드풀을 교착시키던 것을 차단.
            text = run_with_timeout(lambda: extract_text(path), PDFMINER_TIMEOUT) or ""
        except PDFEncryptionError as exc:
            raise EncryptedFileError(f"암호화된 PDF: {path}") from exc
        except Exception:
            # 비표준/손상 PDF에 pdfminer가 관대하지 못함(PDFSyntaxError·PSEOF 등, T-013)이거나
            # 위 timeout(CallTimeout) 발생 — poppler(OCR 경로)는 렌더 가능한 경우가 많아
            # 텍스트 없음으로 두고 폴백을 태운다. poppler도 실패하면 파일 단위 에러로 기록된다.
            text = ""
        if len(text.strip()) >= OCR_TEXT_THRESHOLD:
            return text             # born-digital — 빠른 텍스트 경로
        # 텍스트 레이어가 사실상 없음(빈 것 포함) = 스캔본 → 페이지 OCR 후 합치기.
        # 전체 페이지를 한꺼번에 펼치면 페이지당 ~12MB 비트맵이 쌓여 대형 스캔본에서
        # GB 단위 메모리로 OOM(T-011) — 반드시 한 페이지씩 변환·OCR·해제한다.
        # T-015: poppler 호출에 timeout 필수 — 없으면 불량/거대 PDF에서 poppler 가 멈춰
        # 워커가 영영 안 돌아오고 as_completed 가 무한 대기 → 스레드풀 futex 교착(2.5일 정지 실측).
        # timeout 을 두면 '멈춤'이 '예외'가 되어 process_file 의 파일단위 격리가 에러로 기록·재개한다.
        import pdf2image
        from PIL import Image
        from pii_scanner.core.extractors.ocr import ocr_image
        # 대판형 스캔(도면·현수막 등)이 PIL 폭탄 가드(1.8억 화소)에 걸림(T-013 8건) —
        # 16MP 축소(ocr_image)와 스크립트 RLIMIT_AS가 방어하므로 상한만 완화.
        Image.MAX_IMAGE_PIXELS = 500_000_000
        n_pages = int(pdf2image.pdfinfo_from_path(path, timeout=POPPLER_TIMEOUT)["Pages"])
        pages_to_ocr = min(n_pages, OCR_MAX_PAGES)
        parts = []
        for i in range(1, pages_to_ocr + 1):
            try:
                page = pdf2image.convert_from_path(
                    path, first_page=i, last_page=i, timeout=POPPLER_TIMEOUT)[0]
                parts.append(ocr_image(page))
            except Exception as exc:
                # 페이지 단위 격리 — 멈추거나(timeout) 터지는 한 페이지가 파일 전체·스캔을 막지 않게.
                parts.append(f"[페이지 {i} OCR 실패: {type(exc).__name__}]")
        if pages_to_ocr < n_pages:
            parts.append(f"[OCR 생략: 전체 {n_pages}p 중 {pages_to_ocr}p만 처리(상한 {OCR_MAX_PAGES}, T-015)]")
        ocr_text = "\n".join(parts)
        return f"{text}\n{ocr_text}" if text.strip() else ocr_text

    def extract_located(self, path: str) -> tuple[str, Locator]:
        text = self.extract(path)
        # pdfminer가 넣는 \x0c 페이지 경계 기반. OCR 합본(스캔본) 구간은 page/line 근사.
        return text, PageLineLocator(text)
