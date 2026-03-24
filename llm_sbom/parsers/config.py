"""Hugging Face sidecar configuration parsing."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def parse_sidecar_configs(model_path: Path) -> dict[str, Any]:

    warnings: list[str] = []
    payloads: dict[str, dict[str, Any]] = {}
    for filename in ("config.json", "tokenizer_config.json"):
        candidate = model_path.parent / filename
        payload = _load_json_file(candidate, warnings)
        if payload is not None:
            payloads[filename] = payload

    if not payloads:
        return {
            "architecture": None,
            "dtype": None,
            "license": None,
            "base_model": None,
            "training_framework": None,
            "metadata": {},
            "warnings": warnings,
        }

    config_payload = payloads.get("config.json", {})
    tokenizer_payload = payloads.get("tokenizer_config.json", {})

    architectures = _normalize_string_list(config_payload.get("architectures"))
    model_type = _as_string(config_payload.get("model_type"))
    torch_dtype = _as_string(config_payload.get("torch_dtype") or tokenizer_payload.get("torch_dtype"))
    license_name = _as_string(config_payload.get("license") or tokenizer_payload.get("license"))
    base_model = _extract_base_model(config_payload, tokenizer_payload)
    transformers_version = _as_string(
        config_payload.get("transformers_version") or tokenizer_payload.get("transformers_version")
    )
    architecture = model_type or (architectures[0] if architectures else None)
    training_framework = f"transformers {transformers_version}" if transformers_version else "transformers"

    metadata: dict[str, Any] = {}
    if model_type:
        metadata["model_type"] = model_type
    if architectures:
        metadata["architectures"] = architectures
    if torch_dtype:
        metadata["torch_dtype"] = torch_dtype
    if transformers_version:
        metadata["transformers_version"] = transformers_version

    tokenizer_class = _as_string(tokenizer_payload.get("tokenizer_class"))
    if tokenizer_class:
        metadata["tokenizer_class"] = tokenizer_class

    return {
        "architecture": architecture,
        "dtype": torch_dtype,
        "license": license_name,
        "base_model": base_model,
        "training_framework": training_framework,
        "metadata": metadata,
        "warnings": warnings,
    }


def _load_json_file(path: Path, warnings: list[str]) -> dict[str, Any] | None:

    if not path.is_file():
        return None

    try:
        with path.open("r", encoding="utf-8") as handle:
            payload = json.load(handle)
    except PermissionError as exc:
        warnings.append(f"Unable to read sidecar config '{path.name}': {exc}")
        return None
    except OSError as exc:
        warnings.append(f"Unable to read sidecar config '{path.name}': {exc}")
        return None
    except json.JSONDecodeError as exc:
        warnings.append(f"Invalid JSON in sidecar config '{path.name}': {exc}")
        return None

    if not isinstance(payload, dict):
        warnings.append(f"Sidecar config '{path.name}' did not contain a JSON object.")
        return None

    return payload


def _normalize_string_list(value: Any) -> list[str]:

    if isinstance(value, list):
        return [item for item in (_as_string(entry) for entry in value) if item]
    if isinstance(value, str):
        return [value]
    return []


def _as_string(value: Any) -> str | None:

    if isinstance(value, str):
        stripped = value.strip()
        return stripped or None
    if isinstance(value, (int, float, bool)):
        return str(value)
    return None


def _extract_base_model(*payloads: dict[str, Any]) -> str | None:

    for payload in payloads:
        for key in (
            "base_model",
            "base_model_name_or_path",
            "base_model_name",
            "base_model_repo_id",
            "_name_or_path",
            "source_model",
        ):
            value = _first_string(payload.get(key))
            if value:
                return value
    return None


def _first_string(value: Any) -> str | None:

    direct = _as_string(value)
    if direct:
        return direct
    if isinstance(value, list):
        for entry in value:
            nested = _first_string(entry)
            if nested:
                return nested
    if isinstance(value, dict):
        for entry in value.values():
            nested = _first_string(entry)
            if nested:
                return nested
    return None

