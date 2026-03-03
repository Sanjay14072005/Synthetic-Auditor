# Local Security Report Generator (Offline Ingestion Layer)

This project provides an **offline-first ingestion pipeline** for cybersecurity scan exports. It accepts either:

- a ZIP archive (with nested folders), or
- a single file

and normalizes supported data files (`.csv`, `.xml`, `.json`, `.txt`) into one standardized JSON output suitable for downstream local LLM report generation (e.g., LLaMA 3).

## Clean Architecture Overview

The implementation follows a layered design:

1. **Interface Layer (`cli.py`)**
   - Parses CLI arguments.
   - Invokes application service.
   - Writes unified JSON to disk.

2. **Application Layer (`ingestor.py`)**
   - Detects input type (ZIP vs single file).
   - Extracts ZIP archives safely into a temp directory.
   - Discovers files recursively.
   - Dispatches files to format-specific parsers.
   - Handles failures per-file without crashing the run.

3. **Domain/Schema Layer (`models.py`)**
   - Defines the normalized output schema for ingestion runs, file records, metadata, and errors.

4. **Infrastructure/Parser Layer (`parsers.py`)**
   - Implements file-type parsing for CSV/XML/JSON/TXT.
   - Converts each source format into a unified, structured payload.

## Recommended Folder Structure

```text
Synthetic-Auditor/
├── README.md
├── src/
│   └── local_security_report_generator/
│       ├── __init__.py
│       ├── cli.py
│       ├── ingestor.py
│       ├── models.py
│       └── parsers.py
└── sample-output.json (generated at runtime)
```

## Normalized JSON Schema

Each run writes one JSON document:

```json
{
  "run": {
    "input_path": "...",
    "input_type": "zip|single_file",
    "ingestion_timestamp": "2026-03-03T10:00:00Z",
    "total_discovered_files": 12,
    "processed_supported_files": 9,
    "skipped_unsupported_files": 3,
    "failed_files": 1
  },
  "records": [
    {
      "metadata": {
        "original_filename": "scan_hosts.csv",
        "source_folder": "exports/weekly",
        "file_type": "csv",
        "relative_path": "exports/weekly/scan_hosts.csv",
        "ingestion_timestamp": "2026-03-03T10:00:00Z"
      },
      "content": {
        "format": "table",
        "headers": ["host", "service", "severity"],
        "rows": [{"host": "10.0.0.1", "service": "ssh", "severity": "low"}]
      },
      "errors": []
    }
  ],
  "skipped": [
    {"relative_path": "notes/image.png", "reason": "unsupported_extension"}
  ]
}
```

### Schema Design Principles

- **Stable envelope** (`run`, `records`, `skipped`) for predictable downstream prompting.
- **Per-file metadata** retained for provenance and auditability.
- **Format-agnostic `content` payload** with a `format` discriminator (`table`, `json`, `xml`, `text`).
- **Per-record error isolation** to prevent one bad file from failing the entire pipeline.

## Best Practices for Large-Scale Ingestion

1. **Stream ZIP extraction and avoid loading everything into RAM**.
2. **Keep per-file parsing isolated with exception boundaries**.
3. **Emit deterministic timestamps (UTC ISO-8601)**.
4. **Record skip/failure reasons for observability and debugging**.
5. **Use chunked processing for very large CSV/TXT files** (extend parser with generators if needed).
6. **Add integrity checks** (size limits, optional checksum logging) for large archives.
7. **Version your schema** once integrated with downstream LLM pipelines.

## Usage

```bash
python -m src.local_security_report_generator.cli \
  --input /path/to/input.zip \
  --output /path/to/unified-output.json
```

or for a single file:

```bash
python -m src.local_security_report_generator.cli \
  --input /path/to/scan.json \
  --output /path/to/unified-output.json
```

## Offline Compatibility

- Uses only Python standard library.
- No cloud services.
- No network dependency.

