---
name: mysql-ops
description: MySQL connection discovery, connection-file maintenance, and basic database operations for project workspaces. Use when the user needs to detect MySQL settings from project files, create or update `.ai-yy/mysql/connection.json`, switch between saved MySQL connections, test connectivity, inspect databases or tables, run SELECT or export queries, or execute INSERT, UPDATE, DELETE, DDL, and transaction-driven SQL with explicit safety checks.
---

# Mysql Ops

## Overview

Use this skill to standardize MySQL work around a project-local connection registry at `.ai-yy/mysql/connection.json`. Prefer the bundled Python scripts over ad hoc shell commands so connection discovery, safety checks, and connection switching stay consistent across projects.

## Workflow

1. Read `.ai-yy/mysql/connection.json` with `scripts/load_mysql_connection.py show`.
2. If the file is missing, stale, or the user asks to refresh it, run `scripts/discover_mysql_config.py` against the project root.
3. Show the discovered or saved candidates to the user with passwords masked.
4. Ask the user to confirm which connection should be active.
5. Persist the result in `.ai-yy/mysql/connection.json`.
6. Test the active connection with `scripts/test_mysql_connection.py` before running SQL.
7. Run SQL through `scripts/run_mysql_query.py` so write operations and unsafe statements are gated consistently.

## Connection File Rules

- Store all connections in `.ai-yy/mysql/connection.json`.
- Use the `active` field to pick the default connection.
- Keep every discovered candidate in the `connections` map instead of discarding alternates.
- Show masked passwords in conversation, but keep full values in the JSON file because the user asked for complete connection storage.
- If multiple candidates exist and no active connection is set, ask the user which name to activate before proceeding.
- If the user says "switch to dev" or similar, update only the `active` field unless they explicitly ask to edit credentials.
- Read [references/connection-file.md](references/connection-file.md) before changing the JSON structure.

## Discovery Workflow

Run `scripts/discover_mysql_config.py <project-root> --output .ai-yy/mysql/connection.json` when the connection file does not exist or the user wants to rebuild it.

- The discovery script scans `.env`, `.env.*`, `application.yml`, `application.yaml`, `application.properties`, `docker-compose.yml`, `docker-compose.yaml`, and common `config/*.js|ts|php` files.
- Discovery prefers project configuration files over manual user entry.
- The script writes every candidate it can infer and picks an active connection only when one can be inferred safely or the caller passes `--active`.
- Read [references/discovery-sources.md](references/discovery-sources.md) if you need to explain where candidates came from or extend support.

## Operational Workflow

Run database work through the bundled scripts instead of hand-writing connection logic.

- Show or validate the saved file:
  - `python3 scripts/load_mysql_connection.py show --connection-file .ai-yy/mysql/connection.json`
  - `python3 scripts/load_mysql_connection.py validate --connection-file .ai-yy/mysql/connection.json`
- Switch the default connection:
  - `python3 scripts/load_mysql_connection.py switch --connection-file .ai-yy/mysql/connection.json --name dev`
- Test connectivity:
  - `python3 scripts/test_mysql_connection.py --connection-file .ai-yy/mysql/connection.json`
- Run a safe read query:
  - `python3 scripts/run_mysql_query.py --connection-file .ai-yy/mysql/connection.json --sql "SELECT * FROM user LIMIT 20"`
- Export a read query:
  - `python3 scripts/run_mysql_query.py --connection-file .ai-yy/mysql/connection.json --sql "SELECT * FROM user" --output users.csv --format csv`
- Run a write query only after explicit user confirmation:
  - `python3 scripts/run_mysql_query.py --connection-file .ai-yy/mysql/connection.json --sql "UPDATE user SET status='inactive' WHERE id=1" --confirm-write`
- Run a transaction from a file:
  - `python3 scripts/run_mysql_query.py --connection-file .ai-yy/mysql/connection.json --sql-file change.sql --transaction --confirm-write`

## Safety Rules

Always enforce the following rules:

- `SELECT`, `SHOW`, `DESCRIBE`, and `EXPLAIN` are read-only and may run without write confirmation.
- `INSERT`, `UPDATE`, `DELETE`, `REPLACE`, `TRUNCATE`, `CREATE`, `ALTER`, `DROP`, `RENAME`, `GRANT`, `REVOKE`, and transaction control require explicit user confirmation.
- Reject `UPDATE` and `DELETE` statements without `WHERE` unless the user clearly confirms the full-table write and you pass the dedicated override flag.
- Apply a default `LIMIT` to plain `SELECT` queries that do not already contain one.
- Cap exports by row count unless the user explicitly approves a larger export.
- Treat connections named `prod`, `production`, `online`, or hosts containing obvious production markers as high risk and ask for an extra confirmation round before writes.
- Read [references/safety-rules.md](references/safety-rules.md) before relaxing any guardrail.

## Driver Fallback

Prefer `PyMySQL`. If it is unavailable, the scripts fall back to `mysql-connector-python` and then `MySQLdb`.

- If no supported driver is installed, tell the user which import attempts failed and recommend installing `PyMySQL` first.
- Do not silently switch to raw socket code or shell out to `mysql`.

## Bundled Files

- `scripts/discover_mysql_config.py`: discover candidates from project files and optionally write the connection file.
- `scripts/load_mysql_connection.py`: inspect, validate, and switch the active connection.
- `scripts/test_mysql_connection.py`: test the active or named connection.
- `scripts/run_mysql_query.py`: execute SQL with read/write classification, export support, and transaction support.
- `references/connection-file.md`: canonical JSON structure for `.ai-yy/mysql/connection.json`.
- `references/discovery-sources.md`: supported project file sources and discovery heuristics.
- `references/safety-rules.md`: required guardrails for writes and production-like targets.

Delete the empty `assets/` directory if you later confirm the skill never needs templates.
