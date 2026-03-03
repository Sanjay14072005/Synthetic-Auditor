from __future__ import annotations

import csv
import json
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any, Dict, List


SUPPORTED_EXTENSIONS = {".csv", ".xml", ".json", ".txt"}


def parse_file(path: Path) -> Dict[str, Any]:
    extension = path.suffix.lower()
    if extension == ".csv":
        return parse_csv(path)
    if extension == ".json":
        return parse_json(path)
    if extension == ".xml":
        return parse_xml(path)
    if extension == ".txt":
        return parse_txt(path)
    raise ValueError(f"Unsupported file extension: {extension}")


def parse_csv(path: Path) -> Dict[str, Any]:
    with path.open("r", encoding="utf-8", errors="replace", newline="") as file_obj:
        sample = file_obj.read(2048)
        file_obj.seek(0)

        has_header = csv.Sniffer().has_header(sample) if sample.strip() else False
        if has_header:
            reader = csv.DictReader(file_obj)
            rows = [dict(row) for row in reader]
            headers = reader.fieldnames or []
        else:
            reader = csv.reader(file_obj)
            rows = list(reader)
            max_width = max((len(row) for row in rows), default=0)
            headers = [f"column_{index + 1}" for index in range(max_width)]
            rows = [
                {headers[index]: value for index, value in enumerate(row)}
                for row in rows
            ]

    return {
        "format": "table",
        "headers": headers,
        "rows": rows,
    }


def parse_json(path: Path) -> Dict[str, Any]:
    with path.open("r", encoding="utf-8", errors="replace") as file_obj:
        data = json.load(file_obj)
    return {
        "format": "json",
        "data": data,
    }


def parse_xml(path: Path) -> Dict[str, Any]:
    tree = ET.parse(path)
    root = tree.getroot()
    return {
        "format": "xml",
        "root_tag": root.tag,
        "data": _element_to_dict(root),
    }


def parse_txt(path: Path) -> Dict[str, Any]:
    with path.open("r", encoding="utf-8", errors="replace") as file_obj:
        text = file_obj.read()

    lines: List[str] = text.splitlines()
    return {
        "format": "text",
        "text": text,
        "line_count": len(lines),
    }


def _element_to_dict(element: ET.Element) -> Dict[str, Any]:
    node: Dict[str, Any] = {}

    if element.attrib:
        node["@attributes"] = dict(element.attrib)

    children = list(element)
    if children:
        grouped: Dict[str, List[Any]] = {}
        for child in children:
            grouped.setdefault(child.tag, []).append(_element_to_dict(child))

        for key, values in grouped.items():
            node[key] = values[0] if len(values) == 1 else values

    text = (element.text or "").strip()
    if text:
        node["#text"] = text

    return node
