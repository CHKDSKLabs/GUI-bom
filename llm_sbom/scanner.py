"""Scanning helpers shared by the CLI and GUI."""

from __future__ import annotations

import hashlib
import os
import struct
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, TypedDict, cast

from . import __version__
from .parsers.config import parse_sidecar_configs
from .parsers.gguf import parse_gguf
from .parsers.safetensors import parse_safetensors
from .schema import SBOMDocument

HASH_CHUNK_SIZE = 8 * 1024 * 1024
MODEL_SUFFIXES = {".gguf", ".safetensors"}


class ParsedModelData(TypedDict):
    architecture: str | None
    parameter_count: int | None
    quantization: str | None
    dtype: str | None
    context_length: int | None
    vocab_size: int | None
    training_framework: str | None
    metadata: dict[str, Any]
    warnings: list[str]


class SidecarModelData(TypedDict):
    architecture: str | None
    dtype: str | None
    license: str | None
    base_model: str | None
    training_framework: str | None
    metadata: dict[str, Any]
    warnings: list[str]


def scan_path(target_path: Path, compute_hash: bool) -> list[SBOMDocument]:

    if target_path.is_dir():
        files = discover_model_files(target_path)
    else:
        files = [target_path]

    return [build_sbom_document(model_path, compute_hash=compute_hash) for model_path in files]


def discover_model_files(directory: Path) -> list[Path]:

    discovered: list[Path] = []
    for root, _, filenames in os.walk(directory):
        root_path = Path(root)
        for filename in filenames:
            candidate = root_path / filename
            if candidate.suffix.lower() in MODEL_SUFFIXES:
                discovered.append(candidate)
    return sorted(discovered, key=lambda path: str(path).lower())


def build_sbom_document(model_path: Path, compute_hash: bool) -> SBOMDocument:

    warnings: list[str] = []
    absolute_path = model_path.resolve()
    file_size = safe_file_size(absolute_path, warnings)
    sha256 = compute_sha256(absolute_path, warnings) if compute_hash else ""
    if not compute_hash:
        warnings.append("SHA256 computation skipped by request.")

    format_name = detect_model_format(absolute_path, warnings)
    parsed: ParsedModelData = _empty_parsed_result()
    sidecar: SidecarModelData = _empty_sidecar_result()

    if format_name == "gguf":
        parsed = cast(ParsedModelData, parse_gguf(absolute_path))
        sidecar = cast(SidecarModelData, parse_sidecar_configs(absolute_path))
    elif format_name == "safetensors":
        parsed = cast(ParsedModelData, parse_safetensors(absolute_path))
        sidecar = cast(SidecarModelData, parse_sidecar_configs(absolute_path))

    warnings.extend(parsed["warnings"])
    warnings.extend(sidecar["warnings"])
    metadata = merge_metadata(parsed["metadata"], sidecar["metadata"])

    return SBOMDocument(
        sbom_version="1.0",
        generated_at=datetime.now(timezone.utc).isoformat(),
        tool_name="L-BOM",
        tool_version=__version__,
        model_path=str(absolute_path),
        model_filename=absolute_path.name,
        file_size_bytes=file_size,
        sha256=sha256,
        format=format_name,
        architecture=parsed["architecture"] or sidecar["architecture"],
        parameter_count=parsed["parameter_count"],
        quantization=parsed["quantization"],
        dtype=parsed["dtype"] or sidecar["dtype"],
        context_length=parsed["context_length"],
        vocab_size=parsed["vocab_size"],
        license=sidecar["license"],
        base_model=sidecar["base_model"],
        training_framework=sidecar["training_framework"] or parsed["training_framework"],
        metadata=metadata,
        warnings=_deduplicate_strings(warnings),
    )


def detect_model_format(model_path: Path, warnings: list[str]) -> str:

    try:
        with model_path.open("rb") as handle:
            magic = handle.read(4)
    except PermissionError as exc:
        warnings.append(f"Unable to inspect file format: {exc}")
        return "unknown"
    except OSError as exc:
        warnings.append(f"Unable to inspect file format: {exc}")
        return "unknown"

    if magic == b"GGUF":
        return "gguf"
    if is_probable_safetensors(model_path, warnings):
        return "safetensors"
    return "unknown"


def is_probable_safetensors(model_path: Path, warnings: list[str]) -> bool:

    try:
        file_size = model_path.stat().st_size
        with model_path.open("rb") as handle:
            header_length_bytes = handle.read(8)
            if len(header_length_bytes) != 8:
                return False
            header_length = struct.unpack("<Q", header_length_bytes)[0]
            if header_length <= 0 or header_length + 8 > file_size:
                return False
            first_header_byte = handle.read(1)
    except PermissionError as exc:
        warnings.append(f"Unable to inspect safetensors header: {exc}")
        return False
    except OSError as exc:
        warnings.append(f"Unable to inspect safetensors header: {exc}")
        return False

    return first_header_byte == b"{"


def safe_file_size(model_path: Path, warnings: list[str]) -> int:

    try:
        return model_path.stat().st_size
    except PermissionError as exc:
        warnings.append(f"Unable to read file size: {exc}")
        return 0
    except OSError as exc:
        warnings.append(f"Unable to read file size: {exc}")
        return 0


def compute_sha256(model_path: Path, warnings: list[str]) -> str:

    digest = hashlib.sha256()
    try:
        with model_path.open("rb") as handle:
            while True:
                chunk = handle.read(HASH_CHUNK_SIZE)
                if not chunk:
                    break
                digest.update(chunk)
    except PermissionError as exc:
        warnings.append(f"Unable to compute SHA256: {exc}")
        return ""
    except OSError as exc:
        warnings.append(f"Unable to compute SHA256: {exc}")
        return ""

    return digest.hexdigest()


def merge_metadata(model_metadata: dict[str, Any], sidecar_metadata: dict[str, Any]) -> dict[str, Any]:

    merged = dict(model_metadata)
    if sidecar_metadata:
        merged["sidecar_config"] = sidecar_metadata
    return merged


def _empty_parsed_result() -> ParsedModelData:

    return {
        "architecture": None,
        "parameter_count": None,
        "quantization": None,
        "dtype": None,
        "context_length": None,
        "vocab_size": None,
        "training_framework": None,
        "metadata": {},
        "warnings": [],
    }


def _empty_sidecar_result() -> SidecarModelData:

    return {
        "architecture": None,
        "dtype": None,
        "license": None,
        "base_model": None,
        "training_framework": None,
        "metadata": {},
        "warnings": [],
    }


def _deduplicate_strings(values: list[str]) -> list[str]:

    seen: set[str] = set()
    deduplicated: list[str] = []
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        deduplicated.append(value)
    return deduplicated
