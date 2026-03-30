#!/usr/bin/env python3
"""Merge pause_report.json and full_qa_report.json into a consolidated report.

Hard rules:
  - No PASS if pause coverage is incomplete
  - No PASS if pause pass blocks PASS
  - Final severity = max(pause severity, full-QA severity)
  - If full QA says PASS but pause pass blocks PASS, final severity >= MINOR
"""

import json
import sys
from pathlib import Path

SEVERITY_ORDER = ["PASS", "MINOR", "MODERATE", "MAJOR", "CRITICAL"]


def severity_rank(sev: str) -> int:
    s = sev.upper().strip()
    if s in SEVERITY_ORDER:
        return SEVERITY_ORDER.index(s)
    return len(SEVERITY_ORDER)  # unknown severities rank highest


def max_severity(*sevs: str) -> str:
    return max(sevs, key=severity_rank)


def merge_session(pause_entry: dict | None, qa_entry: dict | None) -> dict:
    """Merge a single session's pause report and full-QA report."""
    session_id = (pause_entry or qa_entry or {}).get("session_id", "UNKNOWN")

    pause_pass = pause_entry.get("pass", True) if pause_entry else True
    pause_severity = pause_entry.get("severity", "PASS") if pause_entry else "PASS"
    pause_coverage_complete = pause_entry.get("coverage_complete", True) if pause_entry else False
    pause_issues = pause_entry.get("issues", []) if pause_entry else []

    qa_pass = qa_entry.get("pass", True) if qa_entry else True
    qa_severity = qa_entry.get("severity", "PASS") if qa_entry else "PASS"
    qa_issues = qa_entry.get("issues", []) if qa_entry else []

    # Start with max of both severities
    final_severity = max_severity(pause_severity, qa_severity)

    # Hard rule: if full QA says PASS but pause blocks PASS, severity >= MINOR
    if qa_pass and not pause_pass:
        final_severity = max_severity(final_severity, "MINOR")

    # Determine final pass
    final_pass = True

    # Hard rule: no PASS if pause coverage is incomplete
    if not pause_coverage_complete:
        final_pass = False
        final_severity = max_severity(final_severity, "MINOR")

    # Hard rule: no PASS if pause pass blocks PASS
    if not pause_pass:
        final_pass = False

    # No PASS if QA itself failed
    if not qa_pass:
        final_pass = False

    # If severity is above PASS, can't be a pass
    if severity_rank(final_severity) > severity_rank("PASS"):
        final_pass = False

    all_issues = []
    for issue in pause_issues:
        all_issues.append({**issue, "source": "pause_report"})
    for issue in qa_issues:
        all_issues.append({**issue, "source": "full_qa_report"})

    return {
        "session_id": session_id,
        "pass": final_pass,
        "severity": final_severity,
        "pause_coverage_complete": pause_coverage_complete,
        "pause_pass": pause_pass,
        "qa_pass": qa_pass,
        "issues": all_issues,
    }


def build_batch_summary(merged: list[dict]) -> dict:
    total = len(merged)
    passed = sum(1 for m in merged if m["pass"])
    failed = total - passed

    severity_counts: dict[str, int] = {}
    for m in merged:
        sev = m["severity"]
        severity_counts[sev] = severity_counts.get(sev, 0) + 1

    coverage_incomplete = sum(1 for m in merged if not m["pause_coverage_complete"])

    return {
        "total_sessions": total,
        "passed": passed,
        "failed": failed,
        "pass_rate": round(passed / total, 4) if total else 0.0,
        "severity_counts": severity_counts,
        "coverage_incomplete": coverage_incomplete,
        "all_passed": failed == 0,
    }


def main():
    if len(sys.argv) < 3:
        sys.exit("Usage: python run_merge.py <pause_report.json> <full_qa_report.json> [output_dir]")

    pause_path = Path(sys.argv[1])
    qa_path = Path(sys.argv[2])
    output_dir = Path(sys.argv[3]) if len(sys.argv) > 3 else Path(".")
    output_dir.mkdir(parents=True, exist_ok=True)

    pause_data = json.loads(pause_path.read_text(encoding="utf-8"))
    qa_data = json.loads(qa_path.read_text(encoding="utf-8"))

    # Index by session_id
    pause_by_id = {e["session_id"]: e for e in pause_data}
    qa_by_id = {e["session_id"]: e for e in qa_data}

    all_ids = sorted(set(pause_by_id) | set(qa_by_id))

    merged = [merge_session(pause_by_id.get(sid), qa_by_id.get(sid)) for sid in all_ids]

    summary = build_batch_summary(merged)

    merged_path = output_dir / "merged_report.json"
    summary_path = output_dir / "batch_summary.json"

    merged_path.write_text(json.dumps(merged, indent=2, ensure_ascii=False))
    summary_path.write_text(json.dumps(summary, indent=2, ensure_ascii=False))

    print(f"Wrote {len(merged)} entries to {merged_path}")
    print(f"Wrote batch summary to {summary_path}")
    print(f"  {summary['passed']}/{summary['total_sessions']} passed "
          f"({summary['pass_rate']:.1%}), {summary['coverage_incomplete']} with incomplete coverage")


if __name__ == "__main__":
    main()
