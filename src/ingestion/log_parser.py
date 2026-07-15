"""
Log Ingestion Module — AI Pipeline Failure Analyzer
Responsibility: Read raw log files and parse them into structured LogEntry objects.
Does NOT know about databases, AI, or APIs. Single responsibility.
"""
 
import re
import os
from dataclasses import dataclass
from typing import List, Optional
from datetime import datetime
 
 
@dataclass
class LogEntry:
    """
    Structured representation of a single log line.
    Every downstream service receives LogEntry objects, not raw strings.
    """
    timestamp: str
    severity: str        # ERROR | WARN | INFO
    source: str          # e.g. Layer7-GW-01, GitLab-CI
    message: str
    raw_line: str        # original line preserved for debugging
    entry_id: Optional[str] = None   # assigned later by embedding service
 
 
# Log line pattern: 2026-07-10 09:14:32 ERROR [Layer7-GW-01] Policy assertion failed...
LOG_PATTERN = re.compile(
    r"(?P<timestamp>\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})"  # match date+time
    r"\s+"                                                       # whitespace
    r"(?P<severity>ERROR|WARN|INFO)"                             # severity level
    r"\s+"
    r"\[(?P<source>[^\]]+)\]"                                  # source in brackets
    r"\s+"
    r"(?P<message>.+)$"                                          # rest is message
)
 
 
def parse_line(line: str) -> Optional[LogEntry]:
    """
    Parse one log line into a LogEntry. Returns None if line does not match.
    This handles malformed lines gracefully — never crashes on bad input.
    """
    line = line.strip()             # remove leading/trailing whitespace
    if not line:                    # skip empty lines
        return None
 
    match = LOG_PATTERN.match(line)
    if not match:                   # line does not match our pattern
        return None                 # caller decides what to do with unmatched lines
 
    return LogEntry(
        timestamp=match.group("timestamp"),
        severity=match.group("severity"),
        source=match.group("source"),
        message=match.group("message"),
        raw_line=line,
    )
 
 
def parse_log_file(filepath: str) -> List[LogEntry]:
    """
    Read an entire log file and return all successfully parsed LogEntry objects.
    Skips lines that do not match the pattern and logs a warning for them.
    """
    if not os.path.exists(filepath):
        raise FileNotFoundError(f"Log file not found: {filepath}")
 
    entries = []
    skipped = 0
 
    with open(filepath, "r", encoding="utf-8") as f:
        for line_num, line in enumerate(f, start=1):
            entry = parse_line(line)
            if entry:
                entries.append(entry)
            else:
                skipped += 1
                # print only non-empty skipped lines to avoid noise
                if line.strip():
                    print(f"[WARN] Line {line_num} did not match pattern: {line.strip()[:60]}")
 
    print(f"[INFO] Parsed {len(entries)} entries, skipped {skipped} lines from {filepath}")
    return entries
 
 
def filter_by_severity(entries: List[LogEntry], severity: str) -> List[LogEntry]:
    """Filter entries by severity level. Case-insensitive."""
    return [e for e in entries if e.severity.upper() == severity.upper()]
 
 
def filter_by_source(entries: List[LogEntry], source_pattern: str) -> List[LogEntry]:
    """Filter entries where source contains the pattern. Useful for isolating one gateway."""
    return [e for e in entries if source_pattern.lower() in e.source.lower()]
 
 
def get_error_summary(entries: List[LogEntry]) -> dict:
    """Returns a dictionary with source names as keys and ERROR counts as values."""
    error_summary = {}

    for entry in entries:
        if hasattr(entry, "source"):
            source = entry.source
            severity = entry.severity
        elif isinstance(entry, dict):
            source = entry.get("source")
            severity = entry.get("severity")
        else:
            source = None
            severity = None

        if not source or severity != "ERROR":
            continue

        error_summary[source] = error_summary.get(source, 0) + 1

    return error_summary


# ── Quick smoke test when run directly ──────────────────────────────────────
if __name__ == "__main__":
    test_file = "data/sample_logs/layer7_failures.log"
    entries = parse_log_file(test_file)

    print(f"\nTotal entries: {len(entries)}")
    errors = filter_by_severity(entries, "ERROR")
    print(f"ERROR entries: {len(errors)}")

    layer7_entries = filter_by_source(entries, "Layer7")
    print(f"Layer7 entries: {len(layer7_entries)}")

    print("\nFirst 3 parsed entries:")
    for e in entries[:3]:
        print(f"  [{e.severity}] {e.source}: {e.message[:60]}")

    error_summary = get_error_summary(entries)
    print("\nError Summary (ERROR severity only):")
    for source, count in error_summary.items():
        print(f"  {source}: {count}")