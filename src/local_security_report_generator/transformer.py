from __future__ import annotations

import re
from typing import Any, Dict, Iterable, List


SEVERITY_ORDER = {"critical": 4, "high": 3, "medium": 2, "low": 1}
DEFAULT_MIN_SEVERITY = "low"

KEY_ALIASES = {
    "vulnerability_id": ["vulnerability_id", "vuln_id", "id", "alert_id"],
    "name": ["name", "title", "vulnerability", "finding", "issue"],
    "severity": ["severity", "risklevel", "risk", "priority"],
    "description": ["description", "details", "summary", "desc"],
    "evidence": ["evidence", "proof", "observation", "notes"],
}


SENSITIVE_PATTERNS = [
    (re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b"), "[REDACTED_IP]"),
    (re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b"), "[REDACTED_EMAIL]"),
    (re.compile(r"\b(?i)(api[_-]?key|token|password|secret)\b\s*[:=]\s*[^\s,;]+"), "[REDACTED_SECRET]"),
]


def build_findings_payload(
    records: Iterable[Dict[str, Any]],
    min_severity: str = DEFAULT_MIN_SEVERITY,
    include_findings_alias: bool = True,
) -> Dict[str, Any]:
    findings: List[Dict[str, Any]] = []

    for record in records:
        content = record.get("content", {})
        format_type = content.get("format")

        if format_type == "table":
            rows = content.get("rows", [])
            findings.extend(_extract_from_items(rows))
        elif format_type == "json":
            findings.extend(_extract_from_json(content.get("data")))
        elif format_type == "xml":
            findings.extend(_extract_from_json(content.get("data")))
        elif format_type == "text":
            findings.extend(_extract_from_text(content.get("text", "")))

    min_level = SEVERITY_ORDER.get(str(min_severity).lower(), SEVERITY_ORDER[DEFAULT_MIN_SEVERITY])
    filtered = [
        f for f in findings
        if SEVERITY_ORDER.get(str(f.get("severity", "")).lower(), 0) >= min_level
    ]

    deduped = _dedupe_findings(filtered)
    payload: Dict[str, Any] = {"critical_findings": deduped}
    if include_findings_alias:
        payload["findings"] = deduped
    return payload



def _dedupe_findings(findings: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    seen = set()
    unique: List[Dict[str, Any]] = []
    for finding in findings:
        key = (
            str(finding.get("vulnerability_id", "")).strip().lower(),
            str(finding.get("name", "")).strip().lower(),
            str(finding.get("severity", "")).strip().lower(),
        )
        if key in seen:
            continue
        seen.add(key)
        unique.append(finding)
    return unique

def _extract_from_json(data: Any) -> List[Dict[str, Any]]:
    if isinstance(data, list):
        return _extract_from_items(data)
    if isinstance(data, dict):
        # If this dict itself looks like a finding
        direct = _normalize_finding(data)
        findings = [direct] if direct else []

        for value in data.values():
            findings.extend(_extract_from_json(value))
        return findings
    return []


def _extract_from_items(items: Iterable[Any]) -> List[Dict[str, Any]]:
    findings: List[Dict[str, Any]] = []
    for item in items:
        if isinstance(item, dict):
            normalized = _normalize_finding(item)
            if normalized:
                findings.append(normalized)
    return findings


def _extract_from_text(text: str) -> List[Dict[str, Any]]:
    findings: List[Dict[str, Any]] = []
    blocks = [block.strip() for block in text.split("\n\n") if block.strip()]
    for index, block in enumerate(blocks, start=1):
        lower = block.lower()
        if "critical" in lower or "high" in lower:
            severity = "Critical" if "critical" in lower else "High"
            findings.append(
                {
                    "vulnerability_id": f"TXT-{index:04d}",
                    "name": block.splitlines()[0][:120],
                    "severity": severity,
                    "description": _scrub_sensitive(block),
                    "evidence": _scrub_sensitive(block),
                }
            )
    return findings


def _normalize_finding(item: Dict[str, Any]) -> Dict[str, Any] | None:
    normalized: Dict[str, Any] = {}

    for target_key, source_keys in KEY_ALIASES.items():
        for key in item.keys():
            if key.lower() in source_keys:
                normalized[target_key] = item[key]
                break

    if not normalized:
        return None

    if "severity" in normalized:
        normalized["severity"] = _normalize_severity(normalized["severity"])

    result = {
        "vulnerability_id": str(normalized.get("vulnerability_id", "UNKNOWN-ID")),
        "name": str(normalized.get("name", "Unnamed Finding")),
        "severity": str(normalized.get("severity", "Medium")),
        "description": _scrub_sensitive(str(normalized.get("description", "No description provided."))),
        "evidence": _scrub_sensitive(str(normalized.get("evidence", "No evidence provided."))),
    }
    return result


def _normalize_severity(raw: Any) -> str:
    value = str(raw).strip().lower()
    if value in {"critical", "crit", "sev1", "p1"}:
        return "Critical"
    if value in {"high", "sev2", "p2"}:
        return "High"
    if value in {"medium", "moderate", "sev3", "p3"}:
        return "Medium"
    if value in {"low", "sev4", "p4"}:
        return "Low"
    return str(raw)


def _scrub_sensitive(text: str) -> str:
    scrubbed = text
    for pattern, replacement in SENSITIVE_PATTERNS:
        scrubbed = pattern.sub(replacement, scrubbed)
    return scrubbed
