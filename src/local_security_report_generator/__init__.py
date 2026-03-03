"""Offline ingestion pipeline for local security report generation."""

from .ingestor import ingest_input
from .transformer import build_findings_payload

__all__ = ["ingest_input", "build_findings_payload"]
