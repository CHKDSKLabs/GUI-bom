"""Local browser-based GUI for L-BOM."""

from __future__ import annotations

import os
import string
import threading
import webbrowser
from dataclasses import asdict
from pathlib import Path
from typing import Any, TypedDict

from flask import Flask, jsonify, render_template, request

from . import __version__
from .output import render_output
from .scanner import MODEL_SUFFIXES, scan_path
from .schema import SBOMDocument

OUTPUT_FORMATS = {"json", "spdx", "table"}


class DirectoryEntry(TypedDict):
    name: str
    path: str
    kind: str


def create_app() -> Flask:

    app = Flask(__name__, template_folder="web/templates", static_folder="web/static")
    app.config["JSON_SORT_KEYS"] = False

    @app.get("/")
    def index() -> str:

        return render_template("index.html", version=__version__)

    @app.get("/health")
    def health() -> dict[str, str]:

        return {"status": "ok"}

    @app.get("/api/fs/roots")
    def list_roots() -> Any:

        return jsonify({"roots": _list_roots()})

    @app.get("/api/fs/list")
    def list_directory() -> Any:

        raw_path = request.args.get("path", type=str)
        if not raw_path:
            return _error("A directory path is required.", 400)

        directory = Path(raw_path).expanduser()
        if not directory.exists():
            return _error(f"The path '{directory}' does not exist.", 404)
        if not directory.is_dir():
            return _error(f"The path '{directory}' is not a directory.", 400)

        try:
            resolved = directory.resolve()
        except OSError as exc:
            return _error(f"Unable to resolve '{directory}': {exc}", 400)

        try:
            entries = _list_directory_entries(resolved)
        except PermissionError as exc:
            return _error(f"Unable to browse '{resolved}': {exc}", 403)
        except OSError as exc:
            return _error(f"Unable to browse '{resolved}': {exc}", 500)

        parent = None if resolved.parent == resolved else str(resolved.parent)
        return jsonify(
            {
                "path": str(resolved),
                "parent": parent,
                "entries": entries,
            }
        )

    @app.post("/api/scan")
    def scan_models() -> Any:

        payload = request.get_json(silent=True)
        if not isinstance(payload, dict):
            return _error("The request body must be a JSON object.", 400)

        raw_path = payload.get("path")
        output_format = payload.get("format", "json")
        compute_hash = payload.get("compute_hash", True)

        if not isinstance(raw_path, str) or not raw_path.strip():
            return _error("A model file or directory path is required.", 400)
        if not isinstance(output_format, str) or output_format.lower() not in OUTPUT_FORMATS:
            return _error("Output format must be one of: json, spdx, table.", 400)
        if not isinstance(compute_hash, bool):
            return _error("The compute_hash value must be true or false.", 400)

        target_path = Path(raw_path.strip()).expanduser()
        if not target_path.exists():
            return _error(f"The path '{target_path}' does not exist.", 404)

        try:
            resolved = target_path.resolve()
        except OSError as exc:
            return _error(f"Unable to resolve '{target_path}': {exc}", 400)

        documents = scan_path(resolved, compute_hash=compute_hash)
        normalized_format = output_format.lower()
        rendered_output = render_output(documents, normalized_format, color=False)

        return jsonify(
            {
                "selected_path": str(resolved),
                "format": normalized_format,
                "compute_hash": compute_hash,
                "summary": _build_summary(documents),
                "documents": [asdict(document) for document in documents],
                "rendered_output": rendered_output,
            }
        )

    return app


def run_gui(host: str, port: int, open_browser: bool) -> None:

    app = create_app()
    browser_host = "127.0.0.1" if host in {"0.0.0.0", "::"} else host
    url = f"http://{browser_host}:{port}"

    if open_browser:
        threading.Timer(0.8, lambda: webbrowser.open(url, new=2)).start()

    app.run(host=host, port=port, debug=False, use_reloader=False, threaded=True)


def _build_summary(documents: list[SBOMDocument]) -> dict[str, Any]:

    formats = sorted({document.format for document in documents if document.format})
    total_size_bytes = sum(document.file_size_bytes for document in documents)
    warning_count = sum(len(document.warnings) for document in documents)

    return {
        "model_count": len(documents),
        "total_size_bytes": total_size_bytes,
        "warning_count": warning_count,
        "formats": formats,
    }


def _list_roots() -> list[str]:

    if os.name == "nt":
        roots = [f"{drive}:\\" for drive in string.ascii_uppercase if Path(f"{drive}:\\").exists()]
        if roots:
            return roots

    return [str(Path("/"))]


def _list_directory_entries(directory: Path) -> list[DirectoryEntry]:

    entries: list[DirectoryEntry] = []
    for child in directory.iterdir():
        try:
            if child.is_dir():
                entries.append({"name": child.name, "path": str(child), "kind": "directory"})
                continue

            if child.is_file() and child.suffix.lower() in MODEL_SUFFIXES:
                entries.append({"name": child.name, "path": str(child), "kind": "model"})
        except OSError as exc:
            raise OSError(f"Unable to inspect '{child}': {exc}") from exc

    return sorted(entries, key=lambda entry: (entry["kind"] != "directory", entry["name"].lower()))


def _error(message: str, status_code: int) -> tuple[Any, int]:

    return jsonify({"error": message}), status_code
