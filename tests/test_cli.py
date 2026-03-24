from click.testing import CliRunner

import llm_sbom.gui as gui_module
from llm_sbom import __version__
from llm_sbom.cli import main


def test_version_command_prints_package_version() -> None:
    runner = CliRunner()

    result = runner.invoke(main, ["version"])

    assert result.exit_code == 0
    assert result.output.strip() == __version__


def test_scan_empty_directory_table_output() -> None:
    runner = CliRunner()

    with runner.isolated_filesystem():
        result = runner.invoke(main, ["scan", ".", "--format", "table"])

    assert result.exit_code == 0
    assert "No model files found." in result.output


def test_gui_command_dispatches_to_server_launcher(monkeypatch) -> None:
    runner = CliRunner()
    captured: dict[str, object] = {}

    def fake_run_gui(*, host: str, port: int, open_browser: bool) -> None:
        captured["host"] = host
        captured["port"] = port
        captured["open_browser"] = open_browser

    monkeypatch.setattr(gui_module, "run_gui", fake_run_gui)

    result = runner.invoke(main, ["gui", "--host", "0.0.0.0", "--port", "9001", "--no-open-browser"])

    assert result.exit_code == 0
    assert captured == {
        "host": "0.0.0.0",
        "port": 9001,
        "open_browser": False,
    }
