from __future__ import annotations

import json
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Tuple
from zipfile import ZipFile, is_zipfile

from .models import FileMetadata, FileRecord, RunSummary, SkippedFile, UnifiedOutput
from .parsers import SUPPORTED_EXTENSIONS, parse_file


def ingest_input(input_path: str) -> UnifiedOutput:
    source = Path(input_path).expanduser().resolve()
    if not source.exists() or not source.is_file():
        raise FileNotFoundError(f"Input path does not exist or is not a file: {source}")

    ingestion_timestamp = _utc_timestamp()

    if is_zipfile(source):
        records, skipped, total_files = _ingest_zip(source, ingestion_timestamp)
        input_type = "zip"
    else:
        records, skipped, total_files = _ingest_single_file(source, ingestion_timestamp)
        input_type = "single_file"

    failed_files = sum(1 for record in records if record.errors)
    summary = RunSummary(
        input_path=str(source),
        input_type=input_type,
        ingestion_timestamp=ingestion_timestamp,
        total_discovered_files=total_files,
        processed_supported_files=len(records),
        skipped_unsupported_files=len(skipped),
        failed_files=failed_files,
    )

    return UnifiedOutput(run=summary, records=records, skipped=skipped)


def write_output(output: UnifiedOutput, destination: str) -> None:
    destination_path = Path(destination).expanduser().resolve()
    destination_path.parent.mkdir(parents=True, exist_ok=True)
    with destination_path.open("w", encoding="utf-8") as file_obj:
        json.dump(output.to_dict(), file_obj, indent=2, ensure_ascii=False)


def _ingest_zip(zip_path: Path, ingestion_timestamp: str) -> Tuple[List[FileRecord], List[SkippedFile], int]:
    records: List[FileRecord] = []
    skipped: List[SkippedFile] = []

    with tempfile.TemporaryDirectory(prefix="security_ingest_") as tmp_dir:
        tmp_root = Path(tmp_dir)
        with ZipFile(zip_path) as archive:
            archive.extractall(tmp_root)

        all_files = [p for p in tmp_root.rglob("*") if p.is_file()]

        for file_path in all_files:
            rel_path = file_path.relative_to(tmp_root).as_posix()
            extension = file_path.suffix.lower()

            if extension not in SUPPORTED_EXTENSIONS:
                skipped.append(SkippedFile(relative_path=rel_path, reason="unsupported_extension"))
                continue

            metadata = _build_metadata(file_path, rel_path, extension, ingestion_timestamp)
            records.append(_safe_parse_record(file_path, metadata))

    return records, skipped, len(all_files)


def _ingest_single_file(file_path: Path, ingestion_timestamp: str) -> Tuple[List[FileRecord], List[SkippedFile], int]:
    records: List[FileRecord] = []
    skipped: List[SkippedFile] = []

    rel_path = file_path.name
    extension = file_path.suffix.lower()

    if extension not in SUPPORTED_EXTENSIONS:
        skipped.append(SkippedFile(relative_path=rel_path, reason="unsupported_extension"))
        return records, skipped, 1

    metadata = _build_metadata(file_path, rel_path, extension, ingestion_timestamp)
    records.append(_safe_parse_record(file_path, metadata))
    return records, skipped, 1


def _build_metadata(file_path: Path, relative_path: str, extension: str, ingestion_timestamp: str) -> FileMetadata:
    source_folder = str(Path(relative_path).parent).replace(".", "")
    source_folder = source_folder.strip("/")
    return FileMetadata(
        original_filename=file_path.name,
        source_folder=source_folder,
        file_type=extension.lstrip("."),
        relative_path=relative_path,
        ingestion_timestamp=ingestion_timestamp,
    )


def _safe_parse_record(file_path: Path, metadata: FileMetadata) -> FileRecord:
    try:
        content = parse_file(file_path)
        return FileRecord(metadata=metadata, content=content)
    except Exception as exc:  # noqa: BLE001
        return FileRecord(
            metadata=metadata,
            content={"format": "error", "message": "Parsing failed for file."},
            errors=[str(exc)],
        )


def _utc_timestamp() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
