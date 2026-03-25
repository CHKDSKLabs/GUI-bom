---
title: GUI-BOM
emoji: 📚
colorFrom: red
colorTo: pink
sdk: static
app_file: index.html
pinned: true
---

# GUI-BOM

`GUI-BOM` is a local browser-based wrapper around `L-BOM`, a Python tool that inspects local LLM model artifacts such as `.gguf` and `.safetensors` files and emits a lightweight Software Bill of Materials with file identity, format details, model metadata, and parsing warnings.

The project now supports both a CLI workflow and a polished local GUI for people who would rather click through a browser than work in a command prompt.

## Install

```bash
pip install .
```

For editable local development:

```bash
pip install -e ".[dev]"
```

## GUI usage

Start the local web app:

```bash
l-bom gui
```

By default the GUI binds to `127.0.0.1:7860` and opens a browser tab automatically.

To expose it from Docker or another machine-friendly environment:

```bash
l-bom gui --host 0.0.0.0 --port 7860 --no-open-browser
```

The GUI includes:

- a local file browser for folders and supported model files
- one-click scanning for a single file or an entire directory
- summary cards, document details, and warning views
- copy and download actions for JSON, SPDX, and table output

## One-click Windows launch

After extracting the project zip, double-click `start-gui.bat`.

The launcher creates a local virtual environment if needed, installs the package, and starts the GUI in your browser.

## Docker usage

Build the image:

```bash
docker build -t l-bom-gui .
```

Run the GUI and mount a host folder of models into the container:

```bash
docker run --rm -p 7860:7860 -v C:\models:/models l-bom-gui
```

Then open `http://127.0.0.1:7860` and browse to `/models` inside the app.

## CLI usage

Show the installed version:

```bash
l-bom version
```

Scan a single model file and emit JSON:

```bash
l-bom scan .\models\Llama-3.1-8B-Instruct-Q4_K_M.gguf
```

Scan a single model file and emit SPDX tag-value:

```bash
l-bom scan .\models\Llama-3.1-8B-Instruct-Q4_K_M.gguf --format spdx
```

Scan a directory recursively and render a table:

```bash
l-bom scan .\models --format table
```

Skip SHA256 hashing for very large files and write the result to disk:

```bash
l-bom scan .\models --no-hash --output .\model-sbom.json
```

## Sample JSON output

```json
{
  "sbom_version": "1.0",
  "generated_at": "2026-03-24T14:08:22.118000+00:00",
  "tool_name": "L-BOM",
  "tool_version": "0.1.0",
  "model_path": "C:\\models\\Llama-3.1-8B-Instruct-Q4_K_M.gguf",
  "model_filename": "Llama-3.1-8B-Instruct-Q4_K_M.gguf",
  "file_size_bytes": 4682873912,
  "sha256": "8b0b3cb15be2e0a0f4b474230ef326f6180fc76efad1d761bf9ce949f6e785b4",
  "format": "gguf",
  "architecture": "llama",
  "parameter_count": 8030261248,
  "quantization": "Q4_K_M",
  "dtype": null,
  "context_length": 8192,
  "vocab_size": 128256,
  "license": "llama3.1",
  "base_model": "meta-llama/Llama-3.1-8B-Instruct",
  "training_framework": "transformers 4.43.2",
  "metadata": {
    "general.name": "Llama 3.1 8B Instruct",
    "general.file_type": 14,
    "gguf_version": 3,
    "endianness": "little",
    "metadata_keys": [
      "general.architecture",
      "general.file_type",
      "llama.context_length",
      "tokenizer.ggml.tokens"
    ],
    "sidecar_config": {
      "model_type": "llama",
      "architectures": [
        "LlamaForCausalLM"
      ],
      "torch_dtype": "bfloat16",
      "transformers_version": "4.43.2"
    }
  },
  "warnings": []
}
```

## License

This project is licensed under the MIT License. See `LICENSE` for the full text.
