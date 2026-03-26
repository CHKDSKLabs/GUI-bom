"""Output rendering helpers for L-BOM."""

from __future__ import annotations

import json
import re
from dataclasses import asdict
from pathlib import Path
from typing import Any, Sequence
from urllib.parse import quote
from uuid import uuid4

from rich.console import Console
from rich.table import Table

from .schema import SBOMDocument


def render_output(documents: Sequence[SBOMDocument], output_format: str, color: bool = True) -> str:

    normalized_format = output_format.lower()
    if normalized_format == "json":
        return render_json(documents)
    if normalized_format == "spdx":
        return render_spdx(documents)
    if normalized_format == "table":
        return render_table(documents, color=color)
    raise ValueError(f"Unsupported output format: {output_format}")


def render_json(documents: Sequence[SBOMDocument]) -> str:

    payload: Any
    if len(documents) == 1:
        payload = asdict(documents[0])
    else:
        payload = [asdict(document) for document in documents]
    return json.dumps(payload, indent=2, ensure_ascii=False)


def render_spdx(documents: Sequence[SBOMDocument]) -> str:

    blocks = [_render_spdx_document(document) for document in documents]
    return "\n\n".join(blocks)


def render_table(documents: Sequence[SBOMDocument], color: bool = True) -> str:

    if not documents:
        return "No model files found."

    console = Console(record=True, force_terminal=color, width=120)
    for document in documents:
        title = document.model_filename if len(documents) > 1 else "L-BOM 💘"
        table = Table(title=title, header_style="bold cyan")
        table.add_column("Field", style="bold")
        table.add_column("Value")
        for field_name, value in asdict(document).items():
            if value is None:
                continue
            table.add_row(field_name, _format_table_value(value))
        console.print(table)

    return console.export_text(styles=color).rstrip()


def _render_spdx_document(document: SBOMDocument) -> str:

    package_name, package_version = _derive_package_identity(document.model_filename)
    package_ref = f"SPDXRef-Package-{_sanitize_spdx_id(document.model_filename)}"
    document_name = f"l-bom-{document.model_filename}"
    created = _normalize_spdx_timestamp(document.generated_at)
    namespace = f"https://spdx.org/spdxdocs/{_sanitize_spdx_id(document_name)}-{uuid4()}"
    license_value = document.license or "NOASSERTION"

    lines = [
        "SPDXVersion: SPDX-2.3",
        "DataLicense: CC0-1.0",
        "SPDXID: SPDXRef-DOCUMENT",
        f"DocumentName: {document_name}",
        f"DocumentNamespace: {namespace}",
        f"Creator: Tool: {document.tool_name}-{document.tool_version}",
        f"Created: {created}",
        f"Relationship: SPDXRef-DOCUMENT DESCRIBES {package_ref}",
        f"PackageName: {package_name}",
        f"SPDXID: {package_ref}",
        f"PackageVersion: {package_version}",
        f"PackageFileName: {document.model_filename}",
        "PackageDownloadLocation: NOASSERTION",
        f"PackageLicenseConcluded: {license_value}",
    ]

    if document.sha256:
        lines.append(f"PackageChecksum: SHA256: {document.sha256}")

    for external_ref in _build_external_refs(document):
        lines.append(f"ExternalRef: {external_ref}")

    return "\n".join(lines)


def _build_external_refs(document: SBOMDocument) -> list[str]:

    refs: list[str] = []
    if document.architecture:
        architecture_value = quote(document.architecture, safe="._-")
        refs.append(f"PACKAGE-MANAGER purl pkg:generic/llm-architecture@{architecture_value}")
    if document.quantization:
        quantization_value = quote(document.quantization, safe="._-")
        refs.append(f"PACKAGE-MANAGER purl pkg:generic/llm-quantization@{quantization_value}")
    return refs


def _derive_package_identity(filename: str) -> tuple[str, str]:

    stem = Path(filename).stem
    package_name = stem or filename
    version_match = re.search(r"(?:^|[-_])(v?\d+(?:\.\d+)+(?:[-_A-Za-z0-9]+)?)", stem)
    if version_match:
        package_version = version_match.group(1).lstrip("-_")
    else:
        package_version = package_name
    return package_name, package_version


def _sanitize_spdx_id(value: str) -> str:

    sanitized = re.sub(r"[^A-Za-z0-9.\-]+", "-", value)
    return sanitized.strip("-") or "artifact"


def _normalize_spdx_timestamp(timestamp: str) -> str:

    if timestamp.endswith("+00:00"):
        return f"{timestamp[:-6]}Z"
    return timestamp


def _format_table_value(value: Any) -> str:

    if isinstance(value, (dict, list)):
        return json.dumps(value, indent=2, ensure_ascii=False)
    return str(value)

