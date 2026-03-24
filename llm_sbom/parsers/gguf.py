"""GGUF header parsing."""

from __future__ import annotations

import math
import struct
from pathlib import Path
from typing import Any, BinaryIO

GGUF_MAGIC = b"GGUF"
ARRAY_PREVIEW_LIMIT = 16

GGUF_VALUE_TYPE_NAMES: dict[int, str] = {
    0: "UINT8",
    1: "INT8",
    2: "UINT16",
    3: "INT16",
    4: "UINT32",
    5: "INT32",
    6: "FLOAT32",
    7: "BOOL",
    8: "STRING",
    9: "ARRAY",
    10: "UINT64",
    11: "INT64",
    12: "FLOAT64",
}

GGUF_FILE_TYPE_LABELS: dict[int, str] = {
    0: "F32",
    1: "F16",
    2: "Q4_0",
    3: "Q4_1",
    6: "Q5_0",
    7: "Q5_1",
    8: "Q8_0",
    9: "Q2_K",
    10: "Q3_K_S",
    11: "Q3_K_M",
    12: "Q3_K_L",
    13: "Q4_K_S",
    14: "Q4_K_M",
    15: "Q5_K_S",
    16: "Q5_K_M",
    17: "Q6_K",
    18: "IQ2_XXS",
    19: "IQ2_XS",
    20: "IQ3_XXS",
    21: "IQ1_S",
    22: "IQ4_NL",
    23: "IQ3_S",
    24: "IQ2_S",
    25: "IQ4_XS",
    26: "I8",
    27: "I16",
    28: "I32",
    29: "I64",
    30: "F64",
    31: "IQ1_M",
    32: "BF16",
    33: "Q4_0_4_4",
    34: "Q4_0_4_8",
    35: "Q4_0_8_8",
    36: "TQ1_0",
    37: "TQ2_0",
}

GGML_TENSOR_TYPE_LABELS: dict[int, str] = {
    0: "F32",
    1: "F16",
    2: "Q4_0",
    3: "Q4_1",
    4: "Q4_2",
    5: "Q4_3",
    6: "Q5_0",
    7: "Q5_1",
    8: "Q8_0",
    9: "Q8_1",
    10: "Q2_K",
    11: "Q3_K",
    12: "Q4_K",
    13: "Q5_K",
    14: "Q6_K",
    15: "Q8_K",
    16: "IQ2_XXS",
    17: "IQ2_XS",
    18: "IQ3_XXS",
    19: "IQ1_S",
    20: "IQ4_NL",
    21: "IQ3_S",
    22: "IQ2_S",
    23: "IQ4_XS",
    24: "I8",
    25: "I16",
    26: "I32",
    27: "I64",
    28: "F64",
    29: "IQ1_M",
    30: "BF16",
    34: "TQ1_0",
    35: "TQ2_0",
}


def parse_gguf(path: Path) -> dict[str, Any]:

    warnings: list[str] = []
    raw_metadata: dict[str, Any] = {}
    total_parameters = 0
    tensor_type_counts: dict[str, int] = {}
    tensor_type_parameters: dict[str, int] = {}

    try:
        with path.open("rb") as handle:
            magic = handle.read(4)
            if magic != GGUF_MAGIC:
                warnings.append("File did not start with the GGUF magic bytes.")
                return _empty_result(raw_metadata, warnings)

            version_bytes = _read_exact(handle, 4)
            endian_prefix, endian_name, version = _determine_endianness(version_bytes)
            tensor_count = _read_struct(handle, endian_prefix, "Q")
            metadata_count = _read_struct(handle, endian_prefix, "Q")

            for _ in range(metadata_count):
                key = _read_gguf_string(handle, endian_prefix)
                value_type = _read_struct(handle, endian_prefix, "I")
                raw_metadata[key] = _read_metadata_value(handle, value_type, endian_prefix)

            for _ in range(tensor_count):
                _ = _read_gguf_string(handle, endian_prefix)
                dimension_count = _read_struct(handle, endian_prefix, "I")
                dimensions = [_read_struct(handle, endian_prefix, "Q") for _ in range(dimension_count)]
                tensor_type = _read_struct(handle, endian_prefix, "I")
                _ = _read_struct(handle, endian_prefix, "Q")

                parameter_count = math.prod(dimensions) if dimensions else 1
                total_parameters += parameter_count

                tensor_label = GGML_TENSOR_TYPE_LABELS.get(tensor_type, f"UNKNOWN_{tensor_type}")
                tensor_type_counts[tensor_label] = tensor_type_counts.get(tensor_label, 0) + 1
                tensor_type_parameters[tensor_label] = tensor_type_parameters.get(tensor_label, 0) + parameter_count
    except PermissionError as exc:
        warnings.append(f"Unable to read GGUF file: {exc}")
        return _empty_result(raw_metadata, warnings)
    except OSError as exc:
        warnings.append(f"Unable to read GGUF file: {exc}")
        return _empty_result(raw_metadata, warnings)
    except (EOFError, struct.error, ValueError) as exc:
        warnings.append(f"Unable to parse GGUF header cleanly: {exc}")
        return _empty_result(raw_metadata, warnings)

    architecture = _as_string(raw_metadata.get("general.architecture"))
    context_length = _extract_metadata_int(raw_metadata, exact_keys=("general.context_length",), suffixes=(".context_length",))
    vocab_size = _extract_vocab_size(raw_metadata)
    quantization = _infer_quantization(raw_metadata, tensor_type_parameters)
    dtype = quantization if quantization in {"F16", "F32", "F64", "BF16"} else None

    metadata: dict[str, Any] = dict(raw_metadata)
    metadata["gguf_version"] = version
    metadata["endianness"] = endian_name
    metadata["metadata_keys"] = list(raw_metadata.keys())
    metadata["tensor_count"] = sum(tensor_type_counts.values())
    metadata["tensor_type_counts"] = tensor_type_counts
    metadata["tensor_type_parameter_counts"] = tensor_type_parameters

    return {
        "architecture": architecture,
        "parameter_count": total_parameters or None,
        "quantization": quantization,
        "dtype": dtype,
        "context_length": context_length,
        "vocab_size": vocab_size,
        "training_framework": None,
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


def _determine_endianness(version_bytes: bytes) -> tuple[str, str, int]:

    if len(version_bytes) != 4:
        raise EOFError("Missing GGUF version field.")

    little_version = struct.unpack("<I", version_bytes)[0]
    big_version = struct.unpack(">I", version_bytes)[0]

    if little_version in {1, 2, 3}:
        return "<", "little", little_version
    if big_version in {1, 2, 3}:
        return ">", "big", big_version
    return "<", "little", little_version


def _read_struct(handle: BinaryIO, endian_prefix: str, fmt: str) -> Any:

    size = struct.calcsize(fmt)
    return struct.unpack(f"{endian_prefix}{fmt}", _read_exact(handle, size))[0]


def _read_exact(handle: BinaryIO, size: int) -> bytes:

    data = handle.read(size)
    if len(data) != size:
        raise EOFError(f"Expected {size} bytes but reached the end of file early.")
    return data


def _read_gguf_string(handle: BinaryIO, endian_prefix: str) -> str:

    length = _read_struct(handle, endian_prefix, "Q")
    data = _read_exact(handle, length)
    return data.decode("utf-8", errors="replace")


def _read_metadata_value(handle: BinaryIO, value_type: int, endian_prefix: str) -> Any:

    if value_type == 0:
        return _read_struct(handle, endian_prefix, "B")
    if value_type == 1:
        return _read_struct(handle, endian_prefix, "b")
    if value_type == 2:
        return _read_struct(handle, endian_prefix, "H")
    if value_type == 3:
        return _read_struct(handle, endian_prefix, "h")
    if value_type == 4:
        return _read_struct(handle, endian_prefix, "I")
    if value_type == 5:
        return _read_struct(handle, endian_prefix, "i")
    if value_type == 6:
        return _read_struct(handle, endian_prefix, "f")
    if value_type == 7:
        return bool(_read_struct(handle, endian_prefix, "B"))
    if value_type == 8:
        return _read_gguf_string(handle, endian_prefix)
    if value_type == 9:
        return _read_metadata_array(handle, endian_prefix)
    if value_type == 10:
        return _read_struct(handle, endian_prefix, "Q")
    if value_type == 11:
        return _read_struct(handle, endian_prefix, "q")
    if value_type == 12:
        return _read_struct(handle, endian_prefix, "d")
    raise ValueError(f"Unsupported GGUF metadata value type: {value_type}")


def _read_metadata_array(handle: BinaryIO, endian_prefix: str) -> Any:

    element_type = _read_struct(handle, endian_prefix, "I")
    element_count = _read_struct(handle, endian_prefix, "Q")
    preview: list[Any] = []
    for index in range(element_count):
        item = _read_metadata_value(handle, element_type, endian_prefix)
        if index < ARRAY_PREVIEW_LIMIT:
            preview.append(item)

    if element_count <= ARRAY_PREVIEW_LIMIT:
        return preview

    return {
        "type": "array",
        "element_type": GGUF_VALUE_TYPE_NAMES.get(element_type, f"UNKNOWN_{element_type}"),
        "count": element_count,
        "preview": preview,
        "truncated": True,
    }


def _extract_metadata_int(
    metadata: dict[str, Any],
    exact_keys: tuple[str, ...] = (),
    suffixes: tuple[str, ...] = (),
) -> int | None:

    for key in exact_keys:
        coerced = _coerce_int(metadata.get(key))
        if coerced is not None:
            return coerced
    for metadata_key, value in metadata.items():
        if any(metadata_key.endswith(suffix) for suffix in suffixes):
            coerced = _coerce_int(value)
            if coerced is not None:
                return coerced
    return None


def _extract_vocab_size(metadata: dict[str, Any]) -> int | None:

    token_array = metadata.get("tokenizer.ggml.tokens")
    if isinstance(token_array, list):
        return len(token_array)
    if isinstance(token_array, dict):
        count = token_array.get("count")
        if isinstance(count, int):
            return count

    return _extract_metadata_int(
        metadata,
        exact_keys=("tokenizer.ggml.n_vocab", "general.vocab_size"),
        suffixes=(".vocab_size",),
    )


def _infer_quantization(metadata: dict[str, Any], tensor_type_parameters: dict[str, int]) -> str | None:

    file_type = _coerce_int(metadata.get("general.file_type"))
    if file_type is not None:
        quantization = GGUF_FILE_TYPE_LABELS.get(file_type)
        if quantization:
            return quantization

    if not tensor_type_parameters:
        return None

    return max(tensor_type_parameters.items(), key=lambda item: item[1])[0]


def _coerce_int(value: Any) -> int | None:

    if isinstance(value, bool):
        return int(value)
    if isinstance(value, int):
        return value
    if isinstance(value, float) and value.is_integer():
        return int(value)
    return None


def _as_string(value: Any) -> str | None:

    if isinstance(value, str):
        stripped = value.strip()
        return stripped or None
    return None

