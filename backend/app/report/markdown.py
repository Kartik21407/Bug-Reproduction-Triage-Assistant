"""The generated report as GitHub-flavoured Markdown (FR-21, US-25).

Rendered from the same `GeneratedReport` the page shows, so the sections,
their order and the "Not provided" wording are identical (US-23). Text a
person or the model wrote is escaped, so it renders as written rather than
as Markdown syntax; logs go into a fenced code block, unmodified, with a
fence longer than any run of backticks inside them.
"""

import re

from app.analysis.schema import Label
from app.report.template import GeneratedReport, ReportLine, ReportSection

_SPECIAL = re.compile(r"([\\`*_\[\]<>|#~])")


def escape(text: str) -> str:
    """Escapes the characters Markdown would otherwise read as syntax."""
    return _SPECIAL.sub(r"\\\1", text)


def _fence(text: str) -> str:
    longest = max((len(run) for run in re.findall(r"`+", text)), default=0)
    marker = "`" * max(3, longest + 1)
    return f"{marker}\n{text}\n{marker}"


def _line(line: ReportLine) -> str:
    if line.url and line.url.startswith(("http://", "https://")):
        text = f"[{escape(line.text)}]({line.url})"
    else:
        text = escape(line.text)
    if line.label and line.label not in (Label.EXPLICIT, Label.MISSING):
        text += f" *({line.label})*"
    if line.note:
        text += f" ({escape(line.note)})"
    return text


def _section(section: ReportSection) -> str:
    """One heading, then blocks separated by a blank line. A list is a
    single block, so it renders as a tight list."""
    blocks: list[str] = []
    if not section.provided:
        blocks.append(f"*{section.lines[0].text}*")
    elif section.key == "steps":
        blocks.append(
            "\n".join(f"{number}. {_line(line)}" for number, line in enumerate(section.lines, 1))
        )
    else:
        plain = [line for line in section.lines if not line.preformatted]
        if len(plain) == 1:
            blocks.append(_line(plain[0]))
        elif plain:
            blocks.append("\n".join(f"- {_line(line)}" for line in plain))
        blocks += [_fence(line.text) for line in section.lines if line.preformatted]
    return "\n\n".join([f"## {section.heading}", *blocks])


def render_markdown(report: GeneratedReport, include_title: bool = True) -> str:
    """The whole report. A GitHub issue carries its title separately, so
    its body leaves the Title section out (`include_title=False`)."""
    sections = [s for s in report.sections if include_title or s.key != "title"]
    return "\n\n".join(_section(s) for s in sections) + "\n"
