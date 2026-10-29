# bdpan-cli

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](https://opensource.org/licenses/MIT)
[![Python 3.12+](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/downloads/)
[![uv](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/uv/main/assets/badge/v0.json)](https://github.com/astral-sh/uv)

[English](README_en.md) | [中文](README.md)

Engineering CLI management tool for Baidu Netdisk (百度网盘). Built on top of the official [Baidu Netdisk Open Platform](https://pan.baidu.com/union/doc/) Python SDK and protocol standards, offering robust file operations, chunked upload with resume, rapid second-pass upload, conflict duplicate cleanup, operation audit & reverse rollback, multi-account isolation, and movie media library automated scraping & foldering.

---

## Installation

### Method 1: uv tool (Recommended, Isolated Environment)
```bash
uv tool install bdpan-cli
```

### Method 2: On-demand execution with uvx (No installation required)
```bash
uvx bdpan-cli --help
```

### Method 3: Standard pip installation
```bash
pip install bdpan-cli
```

### Method 4: Standalone Binary Releases (Zero Python Runtime Required)
Download platform-specific standalone single-file binaries directly from [GitHub Releases](https://github.com/CodingRookie98/bdpan-cli/releases), add it to your `PATH`, and run:
- `bdpan-linux-amd64` (Linux x86_64)
- `bdpan-macos-arm64` (macOS Apple Silicon)
- `bdpan-windows-amd64.exe` (Windows x86_64)

### Quickstart

```bash
# 1. Configure Baidu Open Platform credentials (once, saved to ~/.config/bdpan/.env)
bdpan auth config --app-key <YOUR_APP_KEY> --secret-key <YOUR_SECRET_KEY>

# 2. Authorize and login netdisk account (automatically pops up default browser)
bdpan auth login

# 3. Ready to use
bdpan whoami
bdpan ls /
```

---

## CLI Command Quick Reference

```bash
# Display general help
bdpan --help

# File and Directory Operations
bdpan ls /videos/movies                      # List directory contents
bdpan mkdir /new_folder                      # Create a new directory
bdpan mv <src>... <dest_dir>                 # Move files/directories (audit logged)
bdpan cp <src>... <dest_dir|dest_dir/name>   # Copy files/directories
bdpan rename <path> <new_name>               # In-place rename (audit logged)
bdpan rm <path>... [-y]                      # Delete items (interactive or -y, moved to Recycle Bin)
bdpan quota [--check-expire] [--check-free]  # Inspect storage capacity and quota
bdpan whoami                                 # Show current account and VIP tier
bdpan search <keyword> [--dir <dir>]         # Search netdisk files by keyword
bdpan tree <path> [--depth N] [--index f.json] # Recursive tree traversal & JSON index

# High-speed File Transfer
bdpan upload <local_file> <remote_dest> [--overwrite]  # Chunked upload with resume & rapid second-pass
bdpan download <remote_file>... [--dest ./] [--overwrite] # Resumable chunked download
bdpan dlink <remote_file>... [--aria2 | --curl]         # Extract direct high-speed links

# Duplicate Cleanup & Media Library Scraping
bdpan dedup /videos/movies --staging-dir /quarantine   # Quarantine or clean up (1)/(2) duplicate files
bdpan scrape foldering /videos/unscraped               # Collect scattered media into Scheme A directories
bdpan scrape preview /videos/movies/unscraped          # Preview movie renaming against TMDB/IMDb
bdpan scrape apply preview.csv                         # Batch apply scraped renaming mapping

# Safety Audit Trail & Operation Undo
bdpan ops list [--limit 20]                  # Inspect audit logs of mutating operations
bdpan ops show <op_id>                       # View detailed mapping for an operation
bdpan undo <op_id> [--dry-run] [-y]          # Reverse rollback an operation batch

# Multi-Account Authentication & Configuration
bdpan auth config --app-key <key> --secret-key <secret> # Save credentials to global config (~/.config/bdpan/.env)
bdpan auth config --show                      # Inspect current config source and masked credentials
bdpan auth config --path                      # Print path to global config file
bdpan auth login [--account <alias>]         # Authorize via device flow (auto-launches default browser)
bdpan auth list                              # List saved netdisk accounts and token status
bdpan auth switch <alias>                    # Switch default active account
bdpan --account <alias> <subcommand>         # Run command under a specific account tenant

# Media Observability & Global Options
bdpan info /videos/movies/Inception.mkv       # Probe 4K/1080P resolution, duration, HEVC codec & audio tracks
bdpan stats /videos/movies [--depth N]       # Recursive storage breakdown and media category stats
bdpan -V / --version                         # Display CLI version
bdpan --json <subcommand>                    # Machine-readable standardized JSON envelope for scripting
bdpan --debug <subcommand>                   # Detailed diagnostic debug logs (stderr & ~/.config/bdpan/logs/)
bdpan -q <subcommand>                        # Quiet mode (only ERROR level)


# AI Agent Integration (Model Context Protocol / MCP)
bdpan mcp                                    # Launch standard stdio MCP Server for AI coding assistants
```

> **Safety Invariants**: `mv` and `cp` enforce strict destination path checking; `rm` defaults to interactive confirmation; netdisk deletions are safely placed in the cloud Recycle Bin; mutating batch operations are structured and logged under `.bdpan_ops/` for zero-loss reverse rollback.

---

## Configuration & Credentials

Copy the configuration template and fill in your AppKey and SecretKey from the [Baidu Netdisk Open Platform](https://pan.baidu.com/union/doc/) (`.env` is git-ignored and never committed):

```bash
cp .env.example .env
```

Environment variables:
- `BAIDU_PAN_APP_KEY`: Your Open Platform App Key.
- `BAIDU_PAN_SECRET_KEY`: Your Open Platform Secret Key.
- `BAIDU_PAN_SIGN_KEY`: (Optional) Your Sign Key if signature verification is enabled.

When executing commands for the first time, `bdpan` will open your default browser (or prompt an authorization link in headless environments) to authenticate via OAuth 2.0. The acquired tokens are securely stored in `~/.config/bdpan/tokens.json` (chmod 0600). Diagnostic execution logs are persisted under `~/.config/bdpan/logs/bdpan.log`.

---

## Local Development

```bash
# Clone the repository
git clone https://github.com/CodingRookie98/bdpan-cli.git
cd bdpan-cli

# Install dependencies in isolated virtualenv
uv sync

# Run CLI locally
uv run bdpan --help

# Run full test suite
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 uv run pytest
```

---

## Project Structure

```
├── docs/                     # Documentation following the Diátaxis framework (see docs/GOVERNANCE.md)
│   ├── index.md              # Knowledge base root index
│   ├── llms.txt              # Machine-readable AI agent sitemap
│   ├── project/              # Roadmap (roadmap.md), Backlog (backlog.md), Plans (plans/)
│   └── reference/api/        # SDK API specification reference
├── pyproject.toml            # Python package metadata and CLI entrypoints
├── src/bdpan_cli/            # Core CLI source code and commands
│   └── _vendor/              # Vendored self-contained OpenAPI Client SDK
├── tests/                    # Unit and regression test suite (180+ tests passing)
└── .python-version           # 3.12
```

## Contributing & License

For development guidelines, test gates, and commit conventions, see [CONTRIBUTING.md](./CONTRIBUTING.md).
This project is licensed under the [MIT License](./LICENSE).
