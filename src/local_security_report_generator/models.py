from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List


@dataclass
class FileMetadata:
    original_filename: str
    source_folder: str
    file_type: str
    relative_path: str
    ingestion_timestamp: str


@dataclass
class FileRecord:
    metadata: FileMetadata
    content: Dict[str, Any]
    errors: List[str] = field(default_factory=list)


@dataclass
class SkippedFile:
    relative_path: str
    reason: str


@dataclass
class RunSummary:
    input_path: str
    input_type: str
    ingestion_timestamp: str
    total_discovered_files: int
    processed_supported_files: int
    skipped_unsupported_files: int
    failed_files: int


@dataclass
class UnifiedOutput:
    run: RunSummary
    records: List[FileRecord] = field(default_factory=list)
    skipped: List[SkippedFile] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
