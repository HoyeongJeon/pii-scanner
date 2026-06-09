from __future__ import annotations

import os
import sys

# 전부 합성/가짜 데이터 — 실제 인물 아님
_SAMPLE1 = """샘플 회원 명단 (합성 데이터 — 실제 인물 아님)
홍길동 900101-1234568 010-1234-5678 hong.gildong@example.com
김철수 850302-2345672 010-9876-5432
이미정 (마스킹 예시) 850302-1****** 010-****-1111
"""
_SAMPLE2 = """샘플 문서 (합성 데이터 — 실제 인물 아님)
담당자 이영희 02-123-4567 lee@example.com
여권 M12345678 / 면허 11-12-345678-90
"""


def build_demo(out_dir: str) -> None:
    os.makedirs(out_dir, exist_ok=True)
    with open(os.path.join(out_dir, "sample1.txt"), "w", encoding="utf-8") as f:
        f.write(_SAMPLE1)
    with open(os.path.join(out_dir, "sample2.txt"), "w", encoding="utf-8") as f:
        f.write(_SAMPLE2)


if __name__ == "__main__":
    target = sys.argv[1] if len(sys.argv) > 1 else "demo_data"
    build_demo(target)
    print(f"합성 데모 데이터 생성: {target}")
