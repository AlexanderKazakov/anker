# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Ankify converts arbitrary text into Anki vocabulary decks with text-to-speech audio. It operates as both a CLI tool and an MCP (Model Context Protocol) server compatible with Claude Desktop, Cursor, and other AI clients.

**Data flow:** Input Text → LLM → Vocabulary Table (TSV) → TTS → Audio Files → Anki Deck (.apkg)

## Development Commands

```bash
# Install for development
uv pip install -e .[local-all,dev]

# Linting and formatting
ruff check src/
ruff format src/

# Type checking
mypy src/ankify/

# Run tests
pytest tests/
```

Python 3.12+ required. Always use the `.venv` virtual environment.

## Architecture

### Core Components

#### MCP Server
- **MCP Server** (`src/ankify/mcp/`) - FastMCP server exposing prompts and tools to AI clients

#### MCP and CLI common components
- **TTS** (`src/ankify/tts/`) - `TTSManager` orchestrating Azure, AWS Polly, and Edge TTS providers via abstract base
- **Anki** (`src/ankify/anki/`) - Deck creation with `genanki`, supports forward_only and forward_and_backward note types

#### CLI only components
- **Pipeline** (`src/ankify/pipeline.py`) - Main orchestrator coordinating vocabulary generation, TTS, and Anki packaging
- **Settings** (`src/ankify/settings.py`) - Pydantic v2 configuration with CLI parsing, env vars, YAML config files
- **LLM** (`src/ankify/llm/`) - Abstract `LLMClient` base with `OpenAIClient` implementation, Jinja2 prompt templating


### Configuration Priority

CLI args > Environment vars > .env file > YAML config > defaults

Environment variable prefix: `ANKIFY__` (double underscore for nesting)

### Key Patterns

- Factory pattern for LLM and TTS provider creation
- Abstract base classes for pluggable providers (`LLMClient`, `TTSSingleLanguageClient`)
- Lazy loading of provider libraries (allows partial installations)
- Tenacity for API retry logic

## Code Style Requirements

- Use modern Python typing: `list[str]` not `List[str]`
- Use relative imports: `from ..logging import get_logger`
- All files must use UTF-8 encoding
- Avoid `from __future__ import ...`
- Handle errors gracefully; use `tenacity` for connection retries
- Respect library choices in `pyproject.toml`

## Protected Files

Do not edit without explicit permission: README.md, pyproject.toml, .env, git configuration files
