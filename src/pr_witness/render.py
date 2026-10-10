"""Turn evidence into something a person will actually read."""

from __future__ import annotations

from pr_witness.compare import Severity
from pr_witness.witness import Evidence

_MARK = {Severity.HIGH: "!!", Severity.MEDIUM: " !", Severity.LOW: " ?", Severity.INFO: "  "}


def _counts_table(counts: dict) -> list[str]:
    if not counts:
        return []
    rows = ["collected", "ran", "passed", "failed", "skipped"]
    cols = [c for c in ("base", "head", "crossrun") if c in counts]
    lines = ["  " + "".join(["".ljust(11)] + [c.rjust(10) for c in cols])]
    for row in rows:
        cells = [row.ljust(11)]
        for c in cols:
            cells.append(str(counts[c].get(row, "-")).rjust(10))
        line = "  " + "".join(cells)
        # Mark the deltas worth looking at rather than making the reader
        # subtract columns in their head.
        if "base" in counts and "head" in counts:
            d = counts["head"].get(row, 0) - counts["base"].get(row, 0)
            if d and row in ("ran", "collected", "skipped"):
                line += f"   {d:+d}"
        lines.append(line)
    return lines


def to_text(ev: Evidence) -> str:
    out = [
        f"pr-witness — {ev.base_sha[:7]}..{ev.head_sha[:7]} via {ev.runner}",
        "",
    ]
    out += _counts_table(ev.counts)
    out.append("")

    if not ev.findings:
        out.append("  nothing to report: the base branch's tests still pass, and")
        out.append("  no test stopped running.")
    for f in ev.findings:
        out.append(f"{_MARK[f.severity]} [{f.signal}] {f.summary}")
        for t in f.tests[:10]:
            out.append(f"       {t}")
        if len(f.tests) > 10:
            out.append(f"       … and {len(f.tests) - 10} more")
        if f.innocent_explanation:
            out.append(f"       ↳ {f.innocent_explanation}")
        out.append("")

    for note in ev.notes:
        out.append(f"  note: {note}")
    return "\n".join(out).rstrip() + "\n"


def to_markdown(ev: Evidence) -> str:
    """The pull-request comment."""
    out = [f"**pr-witness** — evidence for `{ev.base_sha[:7]}..{ev.head_sha[:7]}` ({ev.runner})", ""]

    if ev.counts:
        cols = [c for c in ("base", "head", "crossrun") if c in ev.counts]
        out.append("| | " + " | ".join(cols) + " |")
        out.append("|---|" + "---|" * len(cols))
        for row in ("collected", "ran", "passed", "failed", "skipped"):
            cells = [str(ev.counts[c].get(row, "–")) for c in cols]
            out.append(f"| {row} | " + " | ".join(cells) + " |")
        out.append("")

    if not ev.findings:
        out.append("No findings. Every test that passed on the base branch still "
                   "passes against this code, and nothing stopped running.")
        return "\n".join(out) + "\n"

    for f in ev.findings:
        icon = {"high": "🔴", "medium": "🟡", "low": "🔵", "info": "⚪"}[f.severity.value]
        out.append(f"{icon} **{f.signal}** — {f.summary}")
        if f.tests:
            out.append("")
            for t in f.tests[:10]:
                out.append(f"  - `{t}`")
            if len(f.tests) > 10:
                out.append(f"  - … and {len(f.tests) - 10} more")
        if f.innocent_explanation:
            out.append("")
            out.append(f"  > {f.innocent_explanation}")
        out.append("")

    out.append("---")
    out.append("If these changes are intentional, a maintainer can add "
               "`test-change-approved`.")
    return "\n".join(out) + "\n"
