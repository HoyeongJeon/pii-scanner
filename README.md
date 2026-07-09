# PII 스캐너 (pii-scanner)

> 문서 폴더를 **읽기 전용**으로 훑어 **마스킹되지 않은 개인정보(PII)**를 찾아내고, Excel·HTML 리포트로 보고하는 한국어 특화 스캐너.
>
> *A read-only scanner that finds unmasked Korean PII in document folders and reports it as Excel/HTML — without ever writing raw PII into the report.*

탐지된 결과는 **원문이 아니라 마스킹된 스니펫 + 위치**로만 기록되므로, 리포트 자체가 또 다른 유출본이 되지 않습니다.

---

## 무엇을 찾나

| 종류 | 위험등급 | 검증 |
|---|---|---|
| 주민등록번호 | 🔴 최상 | 생년월일 + 성별코드 + **체크섬** (오탐 거의 0) |
| 외국인등록번호 | 🔴 최상 | 생년월일 + 성별코드(5~8) |
| 여권번호 | 🔴 최상 | 형식 (추정) |
| 운전면허번호 | 🔴 최상 | 형식 (추정) |
| 휴대폰 | 🟠 높음 | 형식 |
| 이메일 | 🟡 중간 | 형식 |
| 유선/대표번호 | 🟢 낮음 | 형식 |

각 항목은 **노출(🔴)** vs **마스킹(🟢)**으로 구분되며, 부분 마스킹은 보수적으로 노출로 처리합니다.

## 동작 방식

```
폴더 → [순회] → [텍스트 추출] → [PII 탐지] → [마스킹 판정] → [리포트]
```

- **읽기 전용**: 원본 파일을 절대 수정하지 않습니다.
- **파일 단위 독립 처리**: 손상/암호 파일이 있어도 스캔이 멈추지 않고, 실패는 리포트에 따로 기록됩니다.
- **다중 폴더**: 여러 경로를 한 번에 스캔합니다 (로컬 폴더, 네트워크 공유, 동기화 폴더 모두 동일).
- **위치까지 리포트**: 텍스트는 줄(`L42`), PDF는 페이지+줄(`p.3 L17`), 엑셀은 셀 좌표(`Sheet1!B12`)로 찾아갑니다.
- **오탐 자동 제거**: 법인등록번호가 몰린 엑셀 컬럼(양쪽 체크섬을 모두 통과해 주민번호로 오인되는 패턴)을 후처리 필터로 걸러냅니다.

지원 포맷: `.txt` `.csv` `.hwpx` `.docx` `.xlsx` `.xls` `.pdf` — `.hwp`(아래아한글 바이너리)는 `[hwp]`,
이미지(`.png` `.jpg` `.jpeg`)와 스캔본 PDF의 OCR은 `[ocr]` 옵션 설치 시 지원.

## 설치

```bash
pip install -e ".[dev]"                  # 기본 (로컬 폴더 스캔)
pip install -e ".[dev,hwp]"              # + .hwp 지원
pip install -e ".[dev,ocr]"              # + 이미지·스캔본 PDF OCR (시스템 패키지 tesseract·tesseract-ocr-kor·poppler-utils 필요)
pip install -e ".[dev,dropbox]"          # + Dropbox API 커넥터 (읽기 전용)
```

## 사용법

```bash
# 1) 합성 데모 데이터 생성 후 스캔 (안전하게 체험)
python examples/make_demo_data.py demo_data
pii-scan demo_data --out report_out

# editable 설치 없이 모듈로 실행해도 동일
python -m pii_scanner.cli demo_data --out report_out

# 2) 여러 폴더 동시 스캔
pii-scan ./폴더A ./폴더B --out report_out

# 3) 특정 탐지기 끄기 (키: rrn foreign passport driver phone landline email)
pii-scan ./문서 --out report_out --disable landline --disable email

# 4) Dropbox 스캔 (읽기 전용 · 중단 후 재개 가능)
pii-scan auth --app-key <본인 Dropbox 앱 키> --profile work        # 최초 1회 — refresh token 저장
pii-scan dropbox --root "/스캔할 폴더" --out report_out --profile work
```

Dropbox 스캔 참고:
- 파일은 시스템 임시 폴더로 내려받아 스캔 직후 **즉시 삭제**됩니다 (동기화 폴더를 거치지 않음).
- 진행 상태가 저장되어 **중단돼도 같은 명령 재실행으로 이어서** 스캔합니다 (`--scan-id`로 상태 구분).
- `--namespace team`으로 팀 공유 공간 루트 스캔, `--workers`로 병렬도 조절.
- 자격증명은 `~/.config/pii-scanner/`에 소유자 전용(0600)으로 저장됩니다.

산출물:
- `report_out/report.xlsx` — 상세 (findings / errors / summary 시트)
- `report_out/report.html` — 요약 대시보드 (KPI 카드 + 종류별·Top위험파일·마스킹 스니펫)

## 마스킹률 KPI

```
마스킹률 = 마스킹 건수 / (노출 + 마스킹) × 100%
```

스캔을 반복하면 마스킹률 추이로 **개선 정도**를 추적할 수 있습니다. 파일별·폴더별·PII종류별·전체로 집계됩니다.

## 보안 원칙

이 도구는 막으려는 유출을 스스로 저지르지 않도록 설계되었습니다.

1. **리포트에 PII 원문을 기록하지 않습니다** — 마스킹된 스니펫(`900101-1******`, `010-****-5678`)과 위치만 남깁니다.
2. **읽기 전용** — 원본을 수정하지 않습니다.
3. **합성 데이터로만 개발/테스트** — `tests/`와 `examples/`의 모든 값은 가짜입니다(실제 인물 아님).
4. 휴대폰/유선의 끝 4자리는 한국 표준 마스킹 형식의 정당한 잔여부로 유지됩니다.
5. **Dropbox 커넥터도 읽기 전용** — 파일은 시스템 임시 폴더로 내려받아 스캔 직후 삭제하고, 토큰은 소유자 전용(0600) 파일로만 저장합니다.

> ⚠️ 실제 데이터를 스캔할 때는 그 결과 리포트도 **민감 정보**입니다. 안전한 위치에 보관하세요.

## 프로젝트 구조

```
pii_scanner/
├── core/
│   ├── detectors/    PII 종류별 탐지기 (얇은 인터페이스 + 레지스트리)
│   ├── extractors/   포맷별 텍스트 추출기 (+ ocr.py: 이미지·스캔본 PDF)
│   ├── masking.py    노출/마스킹 판정 헬퍼
│   ├── checksum.py   주민번호 체크섬 · 법인등록번호 체크섬 · Luhn
│   ├── locate.py     탐지 위치(줄/페이지/셀) 계산
│   ├── postfilter.py 오탐 후처리 (법인번호 컬럼 제거 등)
│   └── scanner.py    파이프라인 조립 (병렬 스캔 포함)
├── connectors/       데이터 소스 (local_fs · dropbox) + 재개용 state · 자격증명
├── reporters/        Excel · HTML · 집계(KPI)
├── cli.py            명령줄 진입점 (local / auth / dropbox)
└── config.py         탐지 ON/OFF · 제외경로 · 확장자
```

확장 포인트: 새 PII 종류는 `detectors/`에, 새 포맷은 `extractors/`에 파일 하나 추가하면 됩니다 (각각 `base.py`의 얇은 인터페이스만 구현).

## 개발 / 테스트

```bash
python -m pytest -q          # 전체 테스트
```

테스트는 합성 데이터만 사용합니다. `tests/test_security_no_raw.py`는 **리포트에 원문 PII가 새지 않는지**를 자동 검증하는 회귀 테스트입니다.

## 로드맵

- ~~탐지 위치를 **페이지/행/셀 단위**까지 리포트~~ ✅ 완료
- ~~클라우드 스토리지 API 커넥터~~ ✅ 완료 (Dropbox)
- ~~OCR(스캔 이미지·이미지 PDF)~~ ✅ 완료
- 데이터베이스 커넥터
- 이름·주소(사전/NER), 민감정보(건강·범죄경력 등)
- `.doc`(MS Word 레거시) 지원
- `.hwp` 완전 추출 품질 향상 · 암호화 문서 처리

## 라이선스

[MIT](LICENSE) © 2026 hoyoung0216
