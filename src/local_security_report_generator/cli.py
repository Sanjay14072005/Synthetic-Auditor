from __future__ import annotations

import argparse

from .ingestor import ingest_input, write_output


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Offline local security report ingestion pipeline."
    )
    parser.add_argument("--input", required=True, help="Path to input ZIP or single file")
    parser.add_argument(
        "--output",
        required=True,
        help="Path to write unified JSON output",
    )
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    output = ingest_input(args.input)
    write_output(output, args.output)

    print(f"Ingestion complete: {args.output}")


if __name__ == "__main__":
    main()
