from __future__ import annotations

from jinja2 import Environment

from pii_scanner.core.models import ScanResult, Status
from pii_scanner.reporters.summary import summarize

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
</style></head><body>
<h1>PII 스캔 리포트</h1>
<div class="cards">
  <div class="card">스캔 파일<div class="v">{{ s.total_files }}</div></div>
  <div class="card">노출 건수<div class="v">{{ s.exposed }}</div></div>
  <div class="card">마스킹률<div class="v">{{ "%.1f"|format(s.masking_rate) }}%</div></div>
  <div class="card">추출 실패<div class="v">{{ s.error_files }}</div></div>
</div>
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
<table><tr><th>파일</th><th>종류</th><th>마스킹값</th><th>상태</th></tr>
{% for path, ptype, masked, status in hits %}
<tr><td>{{ path }}</td><td>{{ ptype }}</td><td>{{ masked }}</td><td>{{ status }}</td></tr>
{% endfor %}
</table>
</body></html>"""
)


def write_html(result: ScanResult, out_path: str) -> None:
    s = summarize(result)
    top = []
    hits = []
    for fr in result.files:
        n = sum(1 for h in fr.hits if h.status is Status.EXPOSED)
        if n:
            top.append((fr.path, n))
        for h in fr.hits:
            hits.append((fr.path, h.pii_type.value, h.snippet, h.status.value))
    top.sort(key=lambda x: x[1], reverse=True)
    html = _TEMPLATE.render(
        s=s,
        by_type=[(t.value, b) for t, b in s.by_type.items()],
        top=top[:20],
        hits=hits,
    )
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(html)
