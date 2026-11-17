from .factcheck import unverified_numbers
from .facts import AuditFacts, build_facts
from .narrative import ReportNarrative, deterministic_narrative, generate_narrative
from .render import markdown_to_html, render_html, render_markdown
from .scoring import CompatibilityScore, compute_score

__all__ = [
    "AuditFacts",
    "CompatibilityScore",
    "ReportNarrative",
    "build_facts",
    "compute_score",
    "deterministic_narrative",
    "generate_narrative",
    "markdown_to_html",
    "render_html",
    "render_markdown",
    "unverified_numbers",
]
