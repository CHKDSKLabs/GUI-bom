"""Safetensors header parsing."""

from __future__ import annotations

import json
import math
import struct
from pathlib import Path
from typing import Any


def parse_safetensors(path: Path) -> dict[str, Any]:

    warnings: list[str] = []
    metadata: dict[str, Any] = {}
    tensor_dtypes: dict[str, str] = {}
    layer_names: list[str] = []
    total_parameters = 0
    unique_dtypes: set[str] = set()
    training_framework: str | None = None

    try:
        with path.open("rb") as handle:
            length_bytes = handle.read(8)
            if len(length_bytes) != 8:
                warnings.append("Safetensors header was truncated before the length prefix.")
                return _empty_result(metadata, warnings)

            header_length = struct.unpack("<Q", length_bytes)[0]
            header_bytes = handle.read(header_length)
            if len(header_bytes) != header_length:
                warnings.append("Safetensors header was truncated before the JSON block completed.")
                return _empty_result(metadata, warnings)
    except PermissionError as exc:
        warnings.append(f"Unable to read safetensors file: {exc}")
        return _empty_result(metadata, warnings)
    except OSError as exc:
        warnings.append(f"Unable to read safetensors file: {exc}")
        return _empty_result(metadata, warnings)

    try:
        payload = json.loads(header_bytes.decode("utf-8"))
    except UnicodeDecodeError as exc:
        warnings.append(f"Safetensors header was not valid UTF-8: {exc}")
        return _empty_result(metadata, warnings)
    except json.JSONDecodeError as exc:
        warnings.append(f"Safetensors header did not contain valid JSON: {exc}")
        return _empty_result(metadata, warnings)

    if not isinstance(payload, dict):
        warnings.append("Safetensors header did not contain a JSON object.")
        return _empty_result(metadata, warnings)

    metadata_block = payload.get("__metadata__", {})
    if isinstance(metadata_block, dict):
        metadata.update(metadata_block)
    elif metadata_block is not None:
        warnings.append("Safetensors metadata block was present but not a JSON object.")

    framework_hint = metadata.get("format")
    training_framework = _map_framework(framework_hint)

    for layer_name, descriptor in payload.items():
        if layer_name == "__metadata__":
            continue
        if not isinstance(descriptor, dict):
            warnings.append(f"Tensor descriptor '{layer_name}' was not a JSON object.")
            continue

        layer_names.append(layer_name)
        dtype = descriptor.get("dtype")
        if isinstance(dtype, str):
            unique_dtypes.add(dtype)
            tensor_dtypes[layer_name] = dtype

        shape = descriptor.get("shape")
        parameter_count = _shape_parameter_count(shape)
        if parameter_count is None:
            warnings.append(f"Tensor descriptor '{layer_name}' contained an invalid shape.")
            continue

        total_parameters += parameter_count

    metadata["layer_names"] = layer_names
    metadata["tensor_dtypes"] = tensor_dtypes

    dtype_value: str | None = None
    if len(unique_dtypes) == 1:
        dtype_value = next(iter(unique_dtypes))
    elif len(unique_dtypes) > 1:
        dtype_value = "mixed"

    return {
        "architecture": None,
        "parameter_count": total_parameters if total_parameters else None,
        "quantization": None,
        "dtype": dtype_value,
        "context_length": None,
        "vocab_size": None,
        "training_framework": training_framework,
        "metadata": metadata,
        "warnings": warnings,
    }


def _empty_result(metadata: dict[str, Any], warnings: list[str]) -> dict[str, Any]:

    return {
        "architecture": None,
        "parameter_count": None,
        "quantization": None,
        "dtype": None,
        "context_length": None,
        "vocab_size": None,
        "training_framework": None,
        "metadata": metadata,
        "warnings": warnings,
    }


def _shape_parameter_count(shape: Any) -> int | None:

    if not isinstance(shape, list):
        return None
    if any(not isinstance(dimension, int) or dimension < 0 for dimension in shape):
        return None
    return math.prod(shape) if shape else 1


def _map_framework(value: Any) -> str | None:

    if not isinstance(value, str):
        return None

    normalized = value.strip().lower()
    framework_map = {
        "pt": "pytorch",
        "torch": "pytorch",
        "pytorch": "pytorch",
        "tf": "tensorflow",
        "tensorflow": "tensorflow",
        "flax": "flax",
    }
    return framework_map.get(normalized, normalized or None)

