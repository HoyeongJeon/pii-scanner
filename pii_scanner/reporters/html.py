from __future__ import annotations

from jinja2 import Environment

from pii_scanner.core.models import ScanResult, Status
from pii_scanner.reporters.budget import RowBudget
from pii_scanner.reporters.summary import Summary, summarize

# 탐지 목록 표 행 상한 — 대형 스캔(hit 수천만 건)에서 HTML 이 수 GB 로 커지는 것 방지.
# 초과분은 생략 안내만 남긴다(전체 데이터는 report.xlsx findings / state JSONL).
MAX_HTML_HITS = 10_000

# 읽지 못한 폴더 목록 상한 — 이 목록만 파일 수에 비례해 늘어나므로 램을 유계로 묶는다.
MAX_HTML_UNREADABLE = 200

# autoescape=True: 스캔된 파일경로/스니펫에 포함될 수 있는 <, >, &, " 를
# 자동 이스케이프해 리포트 HTML 인젝션(XSS)·레이아웃 깨짐을 방지한다.
_TEMPLATE = Environment(autoescape=True).from_string(
    """<!doctype html>
<html lang="ko"><head><meta charset="utf-8"><title>PII 스캔 리포트</title>
<style>
body{font-family:sans-serif;margin:2rem}
.cards{display:flex;gap:1rem}
.card{border:1px solid #ddd;border-radius:8px;padding:1rem;min-width:140px}
.card .v{font-size:2rem;font-weight:700}
table{border-collapse:collapse;margin-top:1rem;width:100%}
th,td{border:1px solid #ddd;padding:.4rem .6rem;text-align:left}
.meta{color:#555;margin:.2rem 0}
.warn{background:#fff4e5;border-left:4px solid #e08a00;padding:.6rem .8rem;margin:.6rem 0}
</style></head><body>
<h1>PII 스캔 리포트</h1>
{% if s.scanned_at %}
<p class="meta">스캔 일시 {{ s.scanned_at }} · 도구 버전 {{ s.tool_version }}</p>
{% endif %}
{% if s.active_types %}
<p class="meta">검사한 종류(이번 실행): {{ s.active_types|join(", ") }}</p>
{% endif %}
{% if s.inactive_types %}
<p class="warn">⚠ 검사하지 <b>않은</b> 종류(이번 실행): {{ s.inactive_types|join(", ") }}
 — 이 종류는 "없음"이 아니라 "확인하지 않음"입니다.</p>
{% endif %}
<div class="cards">
  <div class="card">스캔 파일<div class="v">{{ s.total_files }}</div></div>
  <div class="card">노출 건수<div class="v">{{ s.exposed }}</div></div>
  <div class="card">마스킹률<div class="v">{{ "%.1f"|format(s.masking_rate) }}%</div></div>
  <div class="card">추출 실패<div class="v">{{ s.error_files }}</div></div>
  <div class="card">암호화 건너뜀<div class="v">{{ s.encrypted_files }}</div></div>
  <div class="card">법인번호 오탐 제거<div class="v">{{ s.corp_filtered }}</div></div>
{% if s.unreadable_paths %}
  <div class="card">읽지 못한 폴더<div class="v">{{ s.unreadable_paths }}</div></div>
{% endif %}
</div>
{% if unreadable %}
<h2>⛔ 읽지 못한 폴더 (스캔 범위에서 빠짐)</h2>
<p>아래 경로는 순회 자체가 실패해 <b>내용을 확인하지 못했습니다</b> — "개인정보 없음"이 아닙니다.</p>
<table><tr><th>경로</th><th>사유</th></tr>
{% for path, reason in unreadable %}
<tr><td>{{ path }}</td><td>{{ reason }}</td></tr>
{% endfor %}
</table>
{% if unreadable_skipped %}
<p>표시 한도 초과로 {{ unreadable_skipped }}건 생략 — 전체는 report.xlsx(errors)를 참조.</p>
{% endif %}
{% endif %}
<h2>PII 종류별</h2>
<table><tr><th>종류</th><th>노출</th><th>마스킹</th></tr>
{% for t, b in by_type %}
<tr><td>{{ t }}</td><td>{{ b.exposed }}</td><td>{{ b.masked }}</td></tr>
{% endfor %}
</table>
<h2>Top 위험 파일</h2>
<table><tr><th>파일</th><th>노출 건수</th></tr>
{% for path, n in top %}
<tr><td>{{ path }}</td><td>{{ n }}</td></tr>
{% endfor %}
</table>
<h2>탐지 목록 (마스킹됨)</h2>
<table><tr><th>파일</th><th>종류</th><th>마스킹값</th><th>상태</th><th>위치</th></tr>
{% for path, ptype, masked, status, loc in hits %}
<tr><td>{{ path }}</td><td>{{ ptype }}</td><td>{{ masked }}</td><td>{{ status }}</td><td>{{ loc }}</td></tr>
{% endfor %}
</table>
{% if hits_skipped %}
<p>표시 한도 초과로 {{ hits_skipped }}건 생략 — 전체 목록은 report.xlsx(findings)를 참조.</p>
{% endif %}
{% if encrypted %}
<h2>🔒 암호화로 건너뛴 파일 (스캔 못 함)</h2>
<table><tr><th>파일</th></tr>
{% for path in encrypted %}
<tr><td>{{ path }}</td></tr>
{% endfor %}
</table>
{% endif %}
</body></html>"""
)


def write_html_stream(files, out_path: str, summary: Summary,
                      max_hits: int = MAX_HTML_HITS) -> None:
    """FileResult 이터러블을 1회 순회하며 report.html 을 쓴다(T-014).

    RAM 에 쌓는 것은 상한 이하의 탐지 목록 행·파일별 노출 건수·암호화 목록뿐이라
    대형 스캔에서도 메모리가 유계다. 집계는 summarize_iter 결과를 summary 로 받는다
    (이터러블이 1회성 제너레이터일 수 있어 내부에서 재순회하지 않는다).
    """
    budget = RowBudget(summary, max_hits)   # 엑셀과 같은 우선순위 규칙을 공유한다
    top = []
    hits = []
    encrypted = []
    unreadable = []
    unreadable_total = 0
    for fr in files:
        if fr.unreadable:
            unreadable_total += 1
            if len(unreadable) < MAX_HTML_UNREADABLE:
                unreadable.append((fr.path, fr.error or ""))
            continue
        if fr.encrypted:
            encrypted.append(fr.path)
        n = sum(1 for h in fr.hits if h.status is Status.EXPOSED)
        if n:
            top.append((fr.path, n))
        for h in fr.hits:
            if not budget.allow(h):
                continue
            hits.append((fr.path, h.pii_type.value, h.snippet, h.status.value,
                         h.location or ""))
    top.sort(key=lambda x: x[1], reverse=True)
    html = _TEMPLATE.render(
        s=summary,
        by_type=[(t.value, b) for t, b in summary.by_type.items()],
        top=top[:20],
        hits=hits,
        hits_skipped=budget.skipped,
        encrypted=encrypted,
        unreadable=unreadable,
        unreadable_skipped=unreadable_total - len(unreadable),
    )
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(html)


def write_html(result: ScanResult, out_path: str, summary: Summary | None = None) -> None:
    """소형 스캔용 래퍼. summary 를 주면 그것을 쓴다 — excel 과 같은 집계·출처를 쓰도록."""
    write_html_stream(result.files, out_path, summary or summarize(result))
