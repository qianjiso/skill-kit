#!/usr/bin/env python3
"""Shared helpers for the mysql-ops skill."""

from __future__ import annotations

import argparse
import csv
import json
import os
import re
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

DEFAULT_CONNECTION_FILE = ".ai-yy/mysql/connection.json"
DEFAULT_CHARSET = "utf8mb4"
DEFAULT_LIMIT = 200
DEFAULT_EXPORT_LIMIT = 5000
READ_ONLY_KINDS = {"select", "show", "describe", "desc", "explain"}
WRITE_KINDS = {
    "insert",
    "update",
    "delete",
    "replace",
    "truncate",
    "create",
    "alter",
    "drop",
    "rename",
    "grant",
    "revoke",
    "begin",
    "start",
    "commit",
    "rollback",
}
PRODUCTION_MARKERS = ("prod", "production", "online", "master")


class MysqlOpsError(Exception):
    """Raised when a mysql-ops helper fails."""


def build_common_parser(description: str) -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=description)
    parser.add_argument(
        "--connection-file",
        default=DEFAULT_CONNECTION_FILE,
        help=f"Path to the project connection file. Default: {DEFAULT_CONNECTION_FILE}",
    )
    parser.add_argument(
        "--name",
        help="Connection name inside the connection file. Defaults to the active connection.",
    )
    return parser


def ensure_parent_dir(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def mask_secret(value: Optional[str], keep: int = 2) -> str:
    if not value:
        return ""
    if len(value) <= keep * 2:
        return "*" * len(value)
    return f"{value[:keep]}{'*' * (len(value) - keep * 2)}{value[-keep:]}"


def mask_connection(connection: Dict[str, Any]) -> Dict[str, Any]:
    masked = json.loads(json.dumps(connection))
    if "password" in masked:
        masked["password"] = mask_secret(str(masked["password"]))
    return masked


def load_connection_file(path: str | Path) -> Dict[str, Any]:
    connection_path = Path(path)
    if not connection_path.exists():
        raise MysqlOpsError(f"Connection file not found: {connection_path}")

    try:
        data = json.loads(connection_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise MysqlOpsError(f"Invalid JSON in {connection_path}: {exc}") from exc

    validate_connection_data(data)
    return data


def validate_connection_data(data: Dict[str, Any]) -> None:
    if data.get("type") != "mysql":
        raise MysqlOpsError("Connection file must set type to 'mysql'")

    connections = data.get("connections")
    if not isinstance(connections, dict) or not connections:
        raise MysqlOpsError("Connection file must define a non-empty 'connections' object")

    active = data.get("active")
    if active and active not in connections:
        raise MysqlOpsError(f"Active connection '{active}' is not present in 'connections'")

    for name, connection in connections.items():
        if not isinstance(connection, dict):
            raise MysqlOpsError(f"Connection '{name}' must be an object")
        for key in ("host", "port", "user", "password", "database"):
            if key not in connection or connection[key] in (None, ""):
                raise MysqlOpsError(f"Connection '{name}' is missing required field '{key}'")


def resolve_connection(data: Dict[str, Any], name: Optional[str] = None) -> Tuple[str, Dict[str, Any]]:
    connections = data["connections"]
    target_name = name or data.get("active")
    if not target_name:
        if len(connections) == 1:
            target_name = next(iter(connections))
        else:
            raise MysqlOpsError("No active connection is set. Pass --name or update 'active'.")
    if target_name not in connections:
        raise MysqlOpsError(f"Connection '{target_name}' not found in connection file")
    return target_name, connections[target_name]


def save_connection_file(path: str | Path, data: Dict[str, Any]) -> None:
    validate_connection_data(data)
    connection_path = Path(path)
    ensure_parent_dir(connection_path)
    connection_path.write_text(json.dumps(data, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")


def build_connection_payload(
    *,
    host: str,
    port: int,
    user: str,
    password: str,
    database: str,
    source_kind: str,
    source_path: str,
    charset: Optional[str] = None,
    timezone: Optional[str] = None,
) -> Dict[str, Any]:
    payload: Dict[str, Any] = {
        "host": host,
        "port": int(port),
        "user": user,
        "password": password,
        "database": database,
        "charset": charset or DEFAULT_CHARSET,
        "source": {
            "kind": source_kind,
            "path": source_path,
        },
    }
    if timezone:
        payload["timezone"] = timezone
    return payload


def detect_production_like(name: str, connection: Dict[str, Any]) -> bool:
    lowered_name = name.lower()
    host = str(connection.get("host", "")).lower()
    return any(marker in lowered_name or marker in host for marker in PRODUCTION_MARKERS)


def classify_sql(sql: str) -> str:
    text = strip_leading_comments(sql).strip()
    if not text:
        raise MysqlOpsError("SQL is empty")

    match = re.match(r"(?is)^(start\s+transaction|[a-z]+)", text)
    if not match:
        raise MysqlOpsError("Unable to classify SQL statement")

    keyword = re.sub(r"\s+", " ", match.group(1).lower())
    if keyword == "start transaction":
        return "start"
    return keyword


def strip_leading_comments(sql: str) -> str:
    text = sql.lstrip()
    while True:
        if text.startswith("--"):
            text = text.split("\n", 1)[1] if "\n" in text else ""
            text = text.lstrip()
            continue
        if text.startswith("#"):
            text = text.split("\n", 1)[1] if "\n" in text else ""
            text = text.lstrip()
            continue
        if text.startswith("/*"):
            end = text.find("*/")
            if end == -1:
                return ""
            text = text[end + 2 :].lstrip()
            continue
        return text


def is_read_only_sql(sql: str) -> bool:
    return classify_sql(sql) in READ_ONLY_KINDS


def requires_write_confirmation(sql: str) -> bool:
    return classify_sql(sql) in WRITE_KINDS


def has_where_clause(sql: str) -> bool:
    lowered = re.sub(r"\s+", " ", sql.lower())
    return " where " in lowered


def ensure_limit(sql: str, limit: int) -> str:
    if classify_sql(sql) != "select":
        return sql
    normalized = re.sub(r"\s+", " ", sql.lower())
    if " limit " in normalized:
        return sql
    trimmed = sql.rstrip().rstrip(";")
    return f"{trimmed} LIMIT {int(limit)}"


def split_sql_statements(sql_text: str) -> List[str]:
    statements: List[str] = []
    current: List[str] = []
    in_single = False
    in_double = False
    in_backtick = False
    escape = False

    for char in sql_text:
        current.append(char)
        if escape:
            escape = False
            continue
        if char == "\\":
            escape = True
            continue
        if char == "'" and not in_double and not in_backtick:
            in_single = not in_single
        elif char == '"' and not in_single and not in_backtick:
            in_double = not in_double
        elif char == "`" and not in_single and not in_double:
            in_backtick = not in_backtick
        elif char == ";" and not in_single and not in_double and not in_backtick:
            statement = "".join(current[:-1]).strip()
            if statement:
                statements.append(statement)
            current = []

    remainder = "".join(current).strip()
    if remainder:
        statements.append(remainder)
    return statements


def load_driver():
    errors: List[str] = []

    try:
        import pymysql  # type: ignore

        return ("pymysql", pymysql, errors)
    except Exception as exc:  # pragma: no cover - import availability varies
        errors.append(f"PyMySQL: {exc}")

    try:
        import mysql.connector  # type: ignore

        return ("mysql.connector", mysql.connector, errors)
    except Exception as exc:  # pragma: no cover - import availability varies
        errors.append(f"mysql-connector-python: {exc}")

    try:
        import MySQLdb  # type: ignore

        return ("MySQLdb", MySQLdb, errors)
    except Exception as exc:  # pragma: no cover - import availability varies
        errors.append(f"MySQLdb: {exc}")

    raise MysqlOpsError("No supported MySQL driver is installed. " + "; ".join(errors))


def connect_mysql(connection: Dict[str, Any]):
    driver_name, module, _ = load_driver()
    charset = connection.get("charset") or DEFAULT_CHARSET

    if driver_name == "pymysql":
        return driver_name, module.connect(
            host=connection["host"],
            port=int(connection["port"]),
            user=connection["user"],
            password=connection["password"],
            database=connection["database"],
            charset=charset,
            autocommit=False,
            cursorclass=module.cursors.DictCursor,
        )

    if driver_name == "mysql.connector":
        return driver_name, module.connect(
            host=connection["host"],
            port=int(connection["port"]),
            user=connection["user"],
            password=connection["password"],
            database=connection["database"],
            charset=charset,
        )

    return driver_name, module.connect(
        host=connection["host"],
        port=int(connection["port"]),
        user=connection["user"],
        passwd=connection["password"],
        db=connection["database"],
        charset=charset,
    )


def dict_rows(cursor, driver_name: str) -> List[Dict[str, Any]]:
    rows = cursor.fetchall()
    if not rows:
        return []
    if isinstance(rows[0], dict):
        return list(rows)
    if driver_name == "mysql.connector":
        columns = [column[0] for column in cursor.description]
        return [dict(zip(columns, row)) for row in rows]
    columns = [column[0] for column in cursor.description]
    return [dict(zip(columns, row)) for row in rows]


def create_cursor(connection, driver_name: str):
    if driver_name == "mysql.connector":
        return connection.cursor(dictionary=True)
    return connection.cursor()


def print_json(data: Any) -> None:
    print(json.dumps(data, indent=2, ensure_ascii=True, default=str))


def write_rows(rows: Sequence[Dict[str, Any]], output_path: str, fmt: str) -> None:
    if fmt == "json":
        Path(output_path).write_text(
            json.dumps(list(rows), indent=2, ensure_ascii=True, default=str) + "\n",
            encoding="utf-8",
        )
        return

    if fmt != "csv":
        raise MysqlOpsError(f"Unsupported export format: {fmt}")

    fieldnames: List[str] = []
    if rows:
        fieldnames = list(rows[0].keys())
    with Path(output_path).open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        if fieldnames:
            writer.writeheader()
            writer.writerows(rows)


def summarize_connection(name: str, connection: Dict[str, Any]) -> Dict[str, Any]:
    summary = mask_connection(connection)
    summary["name"] = name
    return summary


def flatten_yaml_like(text: str) -> Dict[str, str]:
    flattened: Dict[str, str] = {}
    stack: List[Tuple[int, str]] = []

    for raw_line in text.splitlines():
        if not raw_line.strip() or raw_line.lstrip().startswith("#"):
            continue
        line = raw_line.split("#", 1)[0].rstrip()
        match = re.match(r"^(\s*)([A-Za-z0-9_.-]+):(?:\s*(.*))?$", line)
        if not match:
            continue

        indent = len(match.group(1).replace("\t", "  "))
        key = match.group(2)
        value = (match.group(3) or "").strip()

        while stack and stack[-1][0] >= indent:
            stack.pop()

        if value:
            path = ".".join([part for _, part in stack] + [key])
            flattened[path] = strip_wrapping_quotes(value)
        else:
            stack.append((indent, key))

    return flattened


def parse_properties(text: str) -> Dict[str, str]:
    parsed: Dict[str, str] = {}
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or line.startswith("!"):
            continue
        if "=" in line:
            key, value = line.split("=", 1)
        elif ":" in line:
            key, value = line.split(":", 1)
        else:
            continue
        parsed[key.strip()] = strip_wrapping_quotes(value.strip())
    return parsed


def strip_wrapping_quotes(value: str) -> str:
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'"}:
        return value[1:-1]
    return value


def parse_jdbc_mysql_url(url: str) -> Optional[Dict[str, Any]]:
    match = re.match(r"^jdbc:mysql://([^/:?#]+)(?::(\d+))?/([^?]+)", url.strip(), re.IGNORECASE)
    if not match:
        return None
    return {
        "host": match.group(1),
        "port": int(match.group(2) or 3306),
        "database": match.group(3),
    }


def parse_mysql_uri(uri: str) -> Optional[Dict[str, Any]]:
    match = re.match(
        r"^mysql://([^:@/]+)(?::([^@/]*))?@([^/:?#]+)(?::(\d+))?/([^?]+)",
        uri.strip(),
        re.IGNORECASE,
    )
    if not match:
        return None
    return {
        "user": match.group(1),
        "password": match.group(2) or "",
        "host": match.group(3),
        "port": int(match.group(4) or 3306),
        "database": match.group(5),
    }


def infer_name_from_path(path: str) -> str:
    lowered = path.lower()
    for marker in ("local", "dev", "test", "staging", "prod", "production", "uat"):
        if marker in lowered:
            return "prod" if marker == "production" else marker
    if lowered.endswith(".env"):
        return "local"
    if "docker-compose" in lowered:
        return "docker"
    if "application" in lowered:
        return "application"
    return Path(path).stem.replace(".", "-") or "mysql"


def uniquify_name(name: str, existing: Iterable[str]) -> str:
    used = set(existing)
    if name not in used:
        return name
    index = 2
    while f"{name}-{index}" in used:
        index += 1
    return f"{name}-{index}"
