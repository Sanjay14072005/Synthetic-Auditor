from __future__ import annotations

import argparse

from .ingestor import ingest_input, write_output
from .transformer import build_findings_payload
import json


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Offline local security report ingestion pipeline."
    )
    parser.add_argument("--input", required=True, help="Path to input ZIP or single file")
    parser.add_argument(
        "--output",
        required=True,
        help="Path to write JSON output",
    )
    parser.add_argument(
        "--output-mode",
        choices=["findings", "unified"],
        default="findings",
        help="Output expected structure for downstream pipeline.",
    )
    parser.add_argument(
        "--min-severity",
        choices=["low", "medium", "high", "critical"],
        default="low",
        help="Minimum severity to include when output-mode=findings.",
    )
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    unified_output = ingest_input(args.input)

    if args.output_mode == "unified":
        write_output(unified_output, args.output)
    else:
        payload = build_findings_payload(
            unified_output.to_dict().get("records", []),
            min_severity=args.min_severity,
            include_findings_alias=True,
        )
        with open(args.output, "w", encoding="utf-8") as file_obj:
            json.dump(payload, file_obj, indent=2, ensure_ascii=False)

    print(f"Ingestion complete ({args.output_mode}): {args.output}")


if __name__ == "__main__":
    main()
