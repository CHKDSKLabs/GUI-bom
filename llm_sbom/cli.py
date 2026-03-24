"""Command-line interface for L-BOM."""

from __future__ import annotations

from pathlib import Path

import click

from . import __version__
from .output import render_output
from .scanner import scan_path


@click.group(help="Generate a Software Bill of Materials for local LLM model files.")
def main() -> None:
    pass

@main.command("scan")
@click.argument("path", type=click.Path(exists=True, path_type=Path))
@click.option(
    "--format",
    "output_format",
    type=click.Choice(["json", "spdx", "table"], case_sensitive=False),
    default="json",
    show_default=True,
    help="Choose the output format.",
)
@click.option(
    "--output",
    type=click.Path(path_type=Path, dir_okay=False),
    help="Write the rendered SBOM to a file instead of stdout.",
)
@click.option(
    "--no-hash",
    is_flag=True,
    help="Skip SHA256 computation for very large model files.",
)
def scan(path: Path, output_format: str, output: Path | None, no_hash: bool) -> None:

    documents = scan_path(path, compute_hash=not no_hash)
    rendered = render_output(documents, output_format, color=output is None)

    if output is not None:
        write_output_file(output, rendered)
        return

    if rendered.endswith("\n"):
        click.echo(rendered, nl=False, color=True)
        click.echo("Contribute to L-BOM 💘 development: https://github.com/CHKDSKLabs/l-bom", color=True)
    else:
        click.echo(rendered, color=True)


@main.command("gui")
@click.option(
    "--host",
    default="127.0.0.1",
    show_default=True,
    help="Host interface to bind the local web server to.",
)
@click.option(
    "--port",
    default=7860,
    type=click.IntRange(1, 65535),
    show_default=True,
    help="Port for the local web server.",
)
@click.option(
    "--no-open-browser",
    is_flag=True,
    help="Start the local web server without opening a browser tab.",
)
def gui_command(host: str, port: int, no_open_browser: bool) -> None:

    from .gui import run_gui

    run_gui(host=host, port=port, open_browser=not no_open_browser)


@main.command("version")
def version_command() -> None:

    click.echo(__version__)

def write_output_file(destination: Path, content: str) -> None:

    try:
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(content, encoding="utf-8")
    except PermissionError as exc:
        raise click.ClickException(f"Unable to write output file '{destination}': {exc}") from exc
    except OSError as exc:
        raise click.ClickException(f"Unable to write output file '{destination}': {exc}") from exc


if __name__ == "__main__":
    main()
