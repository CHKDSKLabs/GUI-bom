"""Schema definitions for L-BOM documents."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from typing import Any, Callable, Optional

try:
    from dataclasses_json import dataclass_json as _dataclass_json
except ImportError:
    def _fallback_dataclass_json(cls: type[Any]) -> type[Any]:

        def to_dict(self: Any) -> dict[str, Any]:

            return asdict(self)

        def to_json(self: Any, **kwargs: Any) -> str:

            return json.dumps(asdict(self), **kwargs)

        setattr(cls, "to_dict", to_dict)
        setattr(cls, "to_json", to_json)
        return cls

    dataclass_json: Callable[[type[Any]], type[Any]] = _fallback_dataclass_json
else:
    dataclass_json = _dataclass_json


@dataclass_json
@dataclass
class SBOMDocument:

    sbom_version: str
    generated_at: str
    tool_name: str
    tool_version: str
    model_path: str
    model_filename: str
    file_size_bytes: int
    sha256: str
    format: str
    architecture: Optional[str]
    parameter_count: Optional[int]
    quantization: Optional[str]
    dtype: Optional[str]
    context_length: Optional[int]
    vocab_size: Optional[int]
    license: Optional[str]
    base_model: Optional[str]
    training_framework: Optional[str]
    metadata: dict[str, Any] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)

