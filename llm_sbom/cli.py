"""Command-line interface for L-BOM."""

from __future__ import annotations

from pathlib import Path

import click

from . import __version__
from .output import render_output
from .scanner import scan_path

from .huggingface import HuggingFaceReadmeOptions, render_huggingface_readme

@click.group(help="Generate a Software Bill of Materials for local LLM model files.", epilog="Use --help with any command (for example, l-bom scan --help) for additional information and parameters.")
def main() -> None:
    pass

@main.command("scan")
@click.argument("path", type=click.Path(exists=True, path_type=Path))
@click.option(
    "--format",
    "output_format",
    type=click.Choice(["json", "spdx", "table", "hf-readme"], case_sensitive=False),
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
@click.option(
    "--hf-title",
    type=str,
    help="Override the inferred title when exporting a Hugging Face README.",
)
@click.option(
    "--hf-sdk",
    type=click.Choice(["gradio", "docker", "static"], case_sensitive=False),
    help="Add the Space SDK field to a Hugging Face README export.",
)
@click.option(
    "--hf-app-file",
    type=str,
    help="Add the app_file field to a Hugging Face README export.",
)
@click.option(
    "--hf-app-port",
    type=int,
    help="Add the app_port field to a Hugging Face README export.",
)
@click.option(
    "--hf-short-description",
    type=str,
    help="Override the inferred short_description in a Hugging Face README export.",
)
def scan(
    path: Path,
    output_format: str,
    output: Path | None,
    no_hash: bool,
    hf_title: str | None,
    hf_sdk: str | None,
    hf_app_file: str | None,
    hf_app_port: int | None,
    hf_short_description: str | None,
) -> None:

    documents = scan_path(path, compute_hash=not no_hash)
    if output_format.lower() == "hf-readme":
        if len(documents) != 1:
            raise click.ClickException(
                "Hugging Face README export currently supports scanning a single model file at a time."
            )
        if hf_app_port is not None and hf_sdk not in {None, "docker"}:
            raise click.ClickException("--hf-app-port can only be used with --hf-sdk docker.")

        rendered = render_huggingface_readme(
            documents[0],
            HuggingFaceReadmeOptions(
                title=hf_title,
                sdk=hf_sdk.lower() if hf_sdk else None,
                app_file=hf_app_file,
                app_port=hf_app_port,
                short_description=hf_short_description,
            ),
        )
    else:
        rendered = render_output(documents, output_format, color=output is None)

    if output is not None:
        write_output_file(output, rendered)
        return

    if rendered.endswith("\n"):
        click.echo(rendered, nl=False, color=True)
        click.echo("Generated with L-BOM: SBOM generator for gguf and safetensors files: https://github.com/CHKDSKLabs/l-bom", color=False)
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
