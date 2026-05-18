"""Compare the two translated PDFs and produce an HTML diff report.

Extracts text from output/no-glossary/<pdf> and output/with-glossary/<pdf>,
does a word-level diff, and writes output/comparison.html with an embedded
slide-out glossary drawer.

Color coding:
  - Orange / strikethrough  = word from Run 1 (no glossary) that changed
  - Green / bold            = replacement word from Run 2 (with glossary)
"""

from __future__ import annotations

import difflib
import re
import webbrowser
from pathlib import Path

try:
    from pypdf import PdfReader
except ImportError:
    raise SystemExit("pypdf is required: pip install pypdf")

from common import load_config


# ---------------------------------------------------------------------------
# HTML template – uses {diff_html}, {stats}, {gloss_rows} placeholders.
# Double-braces {{ }} are literal braces in the final HTML (f-string escaping).
# ---------------------------------------------------------------------------

_HTML_TEMPLATE = (
    "<!DOCTYPE html>\n"
    '<html lang="en">\n'
    "<head>\n"
    '  <meta charset="utf-8">\n'
    "  <title>Translation Comparison \u2013 No Glossary vs With Glossary</title>\n"
    "  <style>\n"
    "    body { font-family: Segoe UI, sans-serif; margin: 40px; background: #f8f9fa; color: #1e1e1e; }\n"
    "    h1 { color: #0078D4; }\n"
    "    .toolbar { display:flex; align-items:center; gap:20px; margin-bottom:18px; flex-wrap:wrap; }\n"
    "    .legend { display:flex; gap:16px; font-size:0.95em; flex-wrap:wrap; }\n"
    "    .legend span { padding: 2px 8px; border-radius: 3px; }\n"
    "    .del { background:#ffe0cc; color:#b84c00; text-decoration:line-through; }\n"
    "    .ins { background:#dff6dd; color:#107c10; font-weight:600; }\n"
    "    .diff-box {\n"
    "      background:#fff; border:1px solid #ddd; border-radius:6px;\n"
    "      padding:24px 28px; line-height:1.9; white-space:pre-wrap;\n"
    "      word-break:break-word; font-size:0.97em;\n"
    "    }\n"
    "    h2 { color:#333; margin-top:36px; }\n"
    "    .stats { font-size:0.9em; color:#555; margin-bottom:12px; }\n"
    "    #gloss-btn {\n"
    "      background:#0078D4; color:#fff; border:none;\n"
    "      padding:8px 18px; border-radius:5px; font-size:0.95em;\n"
    "      cursor:pointer; font-family:inherit; white-space:nowrap;\n"
    "    }\n"
    "    #gloss-btn:hover { background:#005a9e; }\n"
    "    #gloss-drawer {\n"
    "      position:fixed; top:0; right:-480px; width:460px; height:100vh;\n"
    "      background:#fff; box-shadow:-4px 0 20px rgba(0,0,0,0.15);\n"
    "      transition:right 0.28s ease; z-index:1000;\n"
    "      display:flex; flex-direction:column;\n"
    "    }\n"
    "    #gloss-drawer.open { right:0; }\n"
    "    #gloss-header {\n"
    "      background:#0078D4; color:#fff;\n"
    "      padding:14px 20px; display:flex;\n"
    "      justify-content:space-between; align-items:center;\n"
    "      font-weight:600; font-size:1.05em;\n"
    "    }\n"
    "    #gloss-close { background:transparent; border:none; color:#fff; font-size:1.4em; cursor:pointer; line-height:1; }\n"
    "    #gloss-search {\n"
    "      margin:12px 16px 8px; padding:7px 12px; border:1px solid #ccc;\n"
    "      border-radius:4px; font-size:0.93em; width:calc(100% - 32px);\n"
    "      box-sizing:border-box;\n"
    "    }\n"
    "    #gloss-table-wrap { overflow-y:auto; flex:1; padding:0 16px 16px; }\n"
    "    #gloss-table { border-collapse:collapse; width:100%; font-size:0.9em; }\n"
    "    #gloss-table th {\n"
    "      background:#f0f6fc; color:#0078D4; text-align:left; padding:7px 10px;\n"
    "      position:sticky; top:0; border-bottom:2px solid #0078D4;\n"
    "    }\n"
    "    #gloss-table td { padding:5px 10px; border-bottom:1px solid #eee; }\n"
    "    #gloss-table tr:hover td { background:#f5fbff; }\n"
    "    .hi { background:#fff3cd; }\n"
    "    #gloss-overlay {\n"
    "      display:none; position:fixed; inset:0;\n"
    "      background:rgba(0,0,0,0.25); z-index:999;\n"
    "    }\n"
    "    #gloss-overlay.open { display:block; }\n"
    "  </style>\n"
    "</head>\n"
    "<body>\n"
    "  <h1>Translation Comparison</h1>\n"
    "  <p>Run 1 (no glossary) vs Run 2 (with glossary) &mdash; differences highlighted below.</p>\n"
    "  <div class=\"toolbar\">\n"
    "    <div class=\"legend\">\n"
    "      <span class=\"del\">changed / removed (Run 1)</span>\n"
    "      <span class=\"ins\">replacement (Run 2)</span>\n"
    "      <span style=\"border:1px solid #ccc; padding:2px 8px; border-radius:3px;\">unchanged</span>\n"
    "    </div>\n"
    "    <button id=\"gloss-btn\" onclick=\"openGlossary()\">\U0001f4d6 View Glossary</button>\n"
    "  </div>\n"
    "  <div class=\"stats\">{stats}</div>\n"
    "  <h2>Word-level diff</h2>\n"
    "  <div class=\"diff-box\">{diff_html}</div>\n"
    "\n"
    "  <div id=\"gloss-overlay\" onclick=\"closeGlossary()\"></div>\n"
    "  <div id=\"gloss-drawer\">\n"
    "    <div id=\"gloss-header\">\n"
    "      <span>\U0001f4d6 EN \u2192 ES Glossary</span>\n"
    "      <button id=\"gloss-close\" onclick=\"closeGlossary()\" title=\"Close\">\u2715</button>\n"
    "    </div>\n"
    "    <input id=\"gloss-search\" type=\"text\" placeholder=\"Filter terms\u2026\" oninput=\"filterGlossary(this.value)\">\n"
    "    <div id=\"gloss-table-wrap\">\n"
    "      <table id=\"gloss-table\">\n"
    "        <thead><tr><th>English</th><th>Spanish</th></tr></thead>\n"
    "        <tbody id=\"gloss-body\">\n"
    "{gloss_rows}\n"
    "        </tbody>\n"
    "      </table>\n"
    "    </div>\n"
    "  </div>\n"
    "\n"
    "  <script>\n"
    "    function openGlossary() {\n"
    "      document.getElementById('gloss-drawer').classList.add('open');\n"
    "      document.getElementById('gloss-overlay').classList.add('open');\n"
    "      document.getElementById('gloss-search').focus();\n"
    "    }\n"
    "    function closeGlossary() {\n"
    "      document.getElementById('gloss-drawer').classList.remove('open');\n"
    "      document.getElementById('gloss-overlay').classList.remove('open');\n"
    "    }\n"
    "    function filterGlossary(q) {\n"
    "      q = q.toLowerCase();\n"
    "      document.querySelectorAll('#gloss-body tr').forEach(r => {\n"
    "        r.style.display = r.textContent.toLowerCase().includes(q) ? '' : 'none';\n"
    "        r.querySelectorAll('td').forEach(td => {\n"
    "          td.classList.toggle('hi', q !== '' && td.textContent.toLowerCase().includes(q));\n"
    "        });\n"
    "      });\n"
    "    }\n"
    "    document.addEventListener('keydown', e => { if (e.key === 'Escape') closeGlossary(); });\n"
    "  </script>\n"
    "</body>\n"
    "</html>\n"
)


def _extract_text(pdf_path: Path) -> str:
    reader = PdfReader(str(pdf_path))
    return "\n".join(page.extract_text() or "" for page in reader.pages)


def _tokenize(text: str) -> list[str]:
    """Split into alternating word/whitespace tokens to preserve spacing in output."""
    return re.split(r"(\s+)", text)


def _html_escape(s: str) -> str:
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _build_diff_html(no_gloss_text: str, with_gloss_text: str) -> tuple[str, int, int]:
    a = _tokenize(no_gloss_text)
    b = _tokenize(with_gloss_text)
    matcher = difflib.SequenceMatcher(None, a, b, autojunk=False)
    parts: list[str] = []
    changed_words = 0
    inserted_words = 0

    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        a_chunk = "".join(a[i1:i2])
        b_chunk = "".join(b[j1:j2])
        if tag == "equal":
            parts.append(_html_escape(a_chunk))
        elif tag == "replace":
            changed_words += sum(1 for t in a[i1:i2] if t.strip())
            inserted_words += sum(1 for t in b[j1:j2] if t.strip())
            parts.append(f'<span class="del">{_html_escape(a_chunk)}</span>')
            parts.append(f'<span class="ins">{_html_escape(b_chunk)}</span>')
        elif tag == "delete":
            changed_words += sum(1 for t in a[i1:i2] if t.strip())
            parts.append(f'<span class="del">{_html_escape(a_chunk)}</span>')
        elif tag == "insert":
            inserted_words += sum(1 for t in b[j1:j2] if t.strip())
            parts.append(f'<span class="ins">{_html_escape(b_chunk)}</span>')

    return "".join(parts), changed_words, inserted_words


def _load_glossary_rows(tsv_path: Path) -> str:
    rows: list[str] = []
    for line in tsv_path.read_text(encoding="utf-8").splitlines():
        parts = line.split("\t")
        if len(parts) >= 2:
            en = _html_escape(parts[0].strip())
            es = _html_escape(parts[1].strip())
            if en:
                rows.append(f"          <tr><td>{en}</td><td>{es}</td></tr>")
    return "\n".join(rows)


def _find_pdf(directory: Path) -> Path:
    pdfs = list(directory.glob("*.pdf"))
    if not pdfs:
        raise FileNotFoundError(
            f"No PDF found in {directory}. Run the translation scripts first."
        )
    return pdfs[0]


def main(open_browser: bool = True) -> Path:
    cfg = load_config()

    no_gloss_pdf = _find_pdf(cfg.local_output_dir / "no-glossary")
    with_gloss_pdf = _find_pdf(cfg.local_output_dir / "with-glossary")

    print(f"Comparing:\n  Run 1: {no_gloss_pdf}\n  Run 2: {with_gloss_pdf}")

    diff_html, changed, inserted = _build_diff_html(
        _extract_text(no_gloss_pdf),
        _extract_text(with_gloss_pdf),
    )
    stats = (
        f"{changed} word(s) changed / removed from Run 1 &nbsp;|&nbsp; "
        f"{inserted} word(s) added / changed in Run 2"
    )
    gloss_rows = _load_glossary_rows(cfg.local_glossary_tsv)

    output_path = cfg.local_output_dir / "comparison.html"
    output_path.write_text(
        _HTML_TEMPLATE
        .replace("{diff_html}", diff_html)
        .replace("{stats}", stats)
        .replace("{gloss_rows}", gloss_rows),
        encoding="utf-8",
    )
    print(f"Comparison report written to: {output_path}")

    if open_browser:
        webbrowser.open(output_path.as_uri())

    return output_path


if __name__ == "__main__":
    main()
