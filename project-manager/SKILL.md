---
name: project-manager
description: Manage and switch between projects, or launch tools (VS Code, Gemini, Codex) in project contexts. Use when the user wants to "open project X", "switch to project Y", "list projects", or "add this project".
---

# Project Manager

## Overview

This skill provides a project management utility (`pm`) that allows users to register project paths with aliases and quickly launch them in new terminal windows, optionally starting specific tools like VS Code, Gemini CLI, or Codex.

## Usage

Use the bundled `scripts/pm.py` script to perform all operations.

### 1. List Projects

When the user asks to "list projects", "show my projects", or "what projects do I have?":

```bash
python3 scripts/pm.py list
```

### 2. Register Current Directory

When the user asks to "add this project", "register this folder as 'foo'", or "save project":

**Syntax:** `python3 scripts/pm.py add <alias> [description]`

**Examples:**
- "Register this as 'backend'": `python3 scripts/pm.py add backend`
- "Add project 'api' described as 'Main API'": `python3 scripts/pm.py add api "Main API"`

### 3. Open Project / Launch Tool

When the user asks to "open project X", "switch to X", or "open X with VS Code":

**Syntax:** `python3 scripts/pm.py open <alias> [--tool <tool_name>] [--terminal <terminal_name>]`

**Supported Tools (`--tool`):**
- **VS Code**: `opencode` (triggers `code .`)
- **Gemini**: `gemini` (triggers `gemini`)
- **Codex**: `codex` (triggers `codex`)
- **Shell**: `shell` (just opens terminal)

**Supported Terminals (`--terminal`):**
- `Terminal` (macOS 默认，缺省值)
- `Warp` (Warp 终端)

**Examples:**
- "Open project 'blog' in Warp": `python3 scripts/pm.py open blog --terminal Warp`
- "Open 'blog' in VS Code using Warp": `python3 scripts/pm.py open blog --tool opencode --terminal Warp`
- "Launch Gemini in 'infra' project": `python3 scripts/pm.py open infra --tool gemini`

## Configuration

The project configuration is stored in `~/.pm_config.json`. The script handles loading and saving this configuration automatically.