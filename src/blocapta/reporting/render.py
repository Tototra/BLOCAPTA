"""Rendu du rapport en Markdown et en HTML autonome."""

from __future__ import annotations

import html
import re

from jinja2 import Environment, FileSystemLoader, StrictUndefined

from ..settings import DATA_DIR
from .facts import AuditFacts
from .narrative import ReportNarrative

_env = Environment(
    loader=FileSystemLoader(DATA_DIR / "templates"),
    undefined=StrictUndefined,
    trim_blocks=True,
    lstrip_blocks=True,
    autoescape=False,
)


def _num(value: float, digits: int = 2) -> str:
    """Format numérique sans « -0.00 »."""
    v = round(float(value), digits)
    if v == 0:
        v = 0.0
    return f"{v:.{digits}f}"


def _signed(value: float, digits: int = 1) -> str:
    v = round(float(value), digits)
    if v == 0:
        return f"{0:.{digits}f}"
    return f"{v:+.{digits}f}"


_env.filters["num"] = _num
_env.filters["signed"] = _signed


def render_markdown(facts: AuditFacts, narrative: ReportNarrative) -> str:
    md = _env.get_template("report.md.j2").render(f=facts, n=narrative)
    return re.sub(r"\n{3,}", "\n\n", md).strip() + "\n"


def _inline(s: str) -> str:
    s = html.escape(s)
    s = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", s)
    s = re.sub(r"\*(.+?)\*", r"<em>\1</em>", s)
    return s


def markdown_to_html(md: str, title: str = "Rapport BLOCAPTA") -> str:
    """Convertisseur Markdown minimal (titres, listes, tableaux, gras) sans dépendance."""
    out: list[str] = []
    lines = md.splitlines()
    i = 0
    while i < len(lines):
        line = lines[i]
        if line.startswith("|") and i + 1 < len(lines) and re.match(r"^\|[-:| ]+\|$", lines[i + 1]):
            header = [c.strip() for c in line.strip("|").split("|")]
            out.append("<table><thead><tr>" + "".join(f"<th>{_inline(c)}</th>" for c in header) + "</tr></thead><tbody>")
            i += 2
            while i < len(lines) and lines[i].startswith("|"):
                cells = [c.strip() for c in lines[i].strip("|").split("|")]
                out.append("<tr>" + "".join(f"<td>{_inline(c)}</td>" for c in cells) + "</tr>")
                i += 1
            out.append("</tbody></table>")
            continue
        m = re.match(r"^(#{1,4})\s+(.*)", line)
        if m:
            lvl = len(m.group(1))
            out.append(f"<h{lvl}>{_inline(m.group(2))}</h{lvl}>")
        elif re.match(r"^\s*[-*]\s+", line) or re.match(r"^\s*\d+\.\s+", line):
            ordered = bool(re.match(r"^\s*\d+\.", line))
            tag = "ol" if ordered else "ul"
            out.append(f"<{tag}>")
            while i < len(lines) and (re.match(r"^\s*[-*]\s+", lines[i]) or re.match(r"^\s*\d+\.\s+", lines[i])):
                item = re.sub(r"^\s*([-*]|\d+\.)\s+", "", lines[i])
                out.append(f"<li>{_inline(item)}</li>")
                i += 1
            out.append(f"</{tag}>")
            continue
        elif line.strip() == "---":
            out.append("<hr>")
        elif line.strip():
            out.append(f"<p>{_inline(line)}</p>")
        i += 1
    body = "\n".join(out)
    return f"""<!DOCTYPE html>
<html lang="fr"><head><meta charset="utf-8"><title>{html.escape(title)}</title>
<style>
body{{font-family:system-ui,-apple-system,Segoe UI,sans-serif;max-width:1000px;margin:2rem auto;padding:0 1rem;color:#1d2433;line-height:1.5}}
h1{{border-bottom:3px solid #2b6cb0;padding-bottom:.4rem}} h2{{margin-top:2rem;color:#2b6cb0}}
table{{border-collapse:collapse;width:100%;margin:1rem 0;font-size:.9rem}}
th,td{{border:1px solid #d5dbe5;padding:.4rem .6rem;text-align:left}} th{{background:#eef3fa}}
tr:nth-child(even) td{{background:#fafbfd}} em{{color:#5a6475}}
</style></head><body>
{body}
</body></html>"""


def render_html(facts: AuditFacts, narrative: ReportNarrative) -> str:
    return markdown_to_html(render_markdown(facts, narrative), title=f"Audit {facts.software.get('name') or ''}")
