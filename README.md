# Local Security Report Generator (Offline Ingestion + Filter + Scrub)

This project handles your part of the pipeline:

Raw XML/JSON/CSV/TXT → **Python Filter** → **Scrub Sensitive Data** → output JSON for your friend's AI stage.

## Dependencies

- Python 3.10+
- No third-party pip packages required (standard library only)

## What it does

- Detects ZIP vs single-file input
- Extracts ZIP files (nested folders supported)
- Parses supported files: `.csv`, `.json`, `.xml`, `.txt`
- Skips unsupported files safely
- Continues processing if one file fails
- Normalizes findings into this output shape (compatible with your friend's uploader):

```json
{
  "critical_findings": [
    {
      "vulnerability_id": "VULN-2026-001",
      "name": "Exposed Administrative Interface",
      "severity": "Critical",
      "description": "...",
      "evidence": "..."
    }
  ],
  "findings": [
    {
      "vulnerability_id": "VULN-2026-001",
      "name": "Exposed Administrative Interface",
      "severity": "Critical",
      "description": "...",
      "evidence": "..."
    }
  ]
}
```

## Data scrubbing

Sensitive tokens are redacted in `description` and `evidence` fields:
- IP addresses → `[REDACTED_IP]`
- emails → `[REDACTED_EMAIL]`
- inline secrets like `token=...`, `password: ...` → `[REDACTED_SECRET]`

## Recommended structure

```text
Synthetic-Auditor/
├── README.md
└── src/local_security_report_generator/
    ├── __init__.py
    ├── cli.py
    ├── ingestor.py
    ├── models.py
    ├── parsers.py
    └── transformer.py
```

## Usage

### Default (friend-compatible output)

```bash
python -m src.local_security_report_generator.cli \
  --input /path/to/input.zip \
  --output /path/to/findings.json
```

This mode writes both `critical_findings` and `findings` keys for maximum compatibility with your friend's Streamlit loader.

Optional filtering:

```bash
python -m src.local_security_report_generator.cli \
  --input /path/to/input.zip \
  --output /path/to/high_and_critical.json \
  --min-severity high
```

### Full unified output (debug/audit)

```bash
python -m src.local_security_report_generator.cli \
  --input /path/to/input.zip \
  --output /path/to/unified.json \
  --output-mode unified
```

## Architecture

- `ingestor.py`: detect input, extract ZIP, parse files, attach metadata
- `parsers.py`: file-type parsers for csv/json/xml/txt
- `transformer.py`: normalize findings + scrub sensitive data + emit `critical_findings`
- `cli.py`: orchestrates pipeline and output mode

