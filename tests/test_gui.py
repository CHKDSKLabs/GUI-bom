import struct
from pathlib import Path

from llm_sbom.gui import create_app


def write_tiny_gguf(path: Path) -> None:
    path.write_bytes(b"GGUF" + struct.pack("<IQQ", 3, 0, 0))


def test_gui_homepage_loads() -> None:
    client = create_app().test_client()

    response = client.get("/")

    assert response.status_code == 200
    assert "L-BOM Studio" in response.get_data(as_text=True)


def test_gui_scan_api_returns_document(tmp_path: Path) -> None:
    model_path = tmp_path / "tiny.gguf"
    write_tiny_gguf(model_path)
    client = create_app().test_client()

    response = client.post(
        "/api/scan",
        json={"path": str(model_path), "format": "json", "compute_hash": False},
    )

    payload = response.get_json()

    assert response.status_code == 200
    assert payload["summary"]["model_count"] == 1
    assert payload["documents"][0]["format"] == "gguf"
    assert "SHA256 computation skipped by request." in payload["documents"][0]["warnings"]


def test_gui_directory_browser_lists_models_and_directories(tmp_path: Path) -> None:
    models_dir = tmp_path / "models"
    nested_dir = models_dir / "nested"
    models_dir.mkdir()
    nested_dir.mkdir()
    write_tiny_gguf(models_dir / "tiny.gguf")
    client = create_app().test_client()

    response = client.get("/api/fs/list", query_string={"path": str(models_dir)})

    payload = response.get_json()

    assert response.status_code == 200
    assert payload["path"] == str(models_dir.resolve())
    assert any(entry["name"] == "nested" and entry["kind"] == "directory" for entry in payload["entries"])
    assert any(entry["name"] == "tiny.gguf" and entry["kind"] == "model" for entry in payload["entries"])
