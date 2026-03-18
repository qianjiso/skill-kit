#!/usr/bin/env python3
"""Execute SQL with mysql-ops safety rules and optional export support."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import List

from mysql_common import (
    DEFAULT_CONNECTION_FILE,
    DEFAULT_EXPORT_LIMIT,
    DEFAULT_LIMIT,
    MysqlOpsError,
    READ_ONLY_KINDS,
    classify_sql,
    connect_mysql,
    create_cursor,
    detect_production_like,
    dict_rows,
    ensure_limit,
    has_where_clause,
    load_connection_file,
    print_json,
    requires_write_confirmation,
    resolve_connection,
    split_sql_statements,
    write_rows,
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--connection-file", default=DEFAULT_CONNECTION_FILE)
    parser.add_argument("--name", help="Connection name inside the connection file")
    parser.add_argument("--sql", help="Inline SQL to execute")
    parser.add_argument("--sql-file", help="Read SQL from a file")
    parser.add_argument("--transaction", action="store_true", help="Execute all statements in one transaction")
    parser.add_argument("--confirm-write", action="store_true", help="Required for write or DDL statements")
    parser.add_argument(
        "--allow-full-table-write",
        action="store_true",
        help="Allow UPDATE or DELETE without WHERE after explicit user confirmation",
    )
    parser.add_argument("--limit", type=int, default=DEFAULT_LIMIT, help=f"Default LIMIT for SELECT. Default: {DEFAULT_LIMIT}")
    parser.add_argument(
        "--export-limit",
        type=int,
        default=DEFAULT_EXPORT_LIMIT,
        help=f"Maximum rows to export or print from SELECT results. Default: {DEFAULT_EXPORT_LIMIT}",
    )
    parser.add_argument("--output", help="Write SELECT results to a file")
    parser.add_argument("--format", default="json", choices=["json", "csv"], help="Export format when --output is set")
    args = parser.parse_args()

    try:
        sql_text = load_sql(args.sql, args.sql_file)
        statements = split_sql_statements(sql_text)
        if not statements:
            raise MysqlOpsError("No SQL statements were found")

        data = load_connection_file(args.connection_file)
        connection_name, connection_info = resolve_connection(data, args.name)

        write_needed = any(requires_write_confirmation(statement) for statement in statements)
        if write_needed and not args.confirm_write:
            raise MysqlOpsError("Write or DDL SQL requires --confirm-write after explicit user confirmation")

        for statement in statements:
            sql_kind = classify_sql(statement)
            if sql_kind in {"update", "delete"} and not has_where_clause(statement) and not args.allow_full_table_write:
                raise MysqlOpsError(f"{sql_kind.upper()} without WHERE is blocked unless --allow-full-table-write is set")

        if detect_production_like(connection_name, connection_info) and write_needed and not args.confirm_write:
            raise MysqlOpsError("Production-like connections require explicit write confirmation")

        driver_name, connection = connect_mysql(connection_info)
        cursor = create_cursor(connection, driver_name)
        try:
            if args.transaction:
                result = execute_in_transaction(cursor, driver_name, statements, args.limit, args.export_limit)
                connection.commit()
            else:
                result = execute_statements(cursor, driver_name, statements, args.limit, args.export_limit)
                if write_needed:
                    connection.commit()

            if args.output:
                rows = result.get("rows", [])
                write_rows(rows, args.output, args.format)
                result["output"] = str(Path(args.output))
                result["format"] = args.format

            print_json(result)
            return 0
        except Exception:
            connection.rollback()
            raise
        finally:
            cursor.close()
            connection.close()

    except MysqlOpsError as exc:
        print(f"ERROR: {exc}")
        return 1
    except Exception as exc:
        print(f"ERROR: Query execution failed: {exc}")
        return 1


def load_sql(inline_sql: str | None, file_path: str | None) -> str:
    if bool(inline_sql) == bool(file_path):
        raise MysqlOpsError("Provide exactly one of --sql or --sql-file")
    if inline_sql:
        return inline_sql
    return Path(file_path).read_text(encoding="utf-8")


def execute_in_transaction(cursor, driver_name: str, statements: List[str], limit: int, export_limit: int):
    result = execute_statements(cursor, driver_name, statements, limit, export_limit)
    result["transaction"] = True
    return result


def execute_statements(cursor, driver_name: str, statements: List[str], limit: int, export_limit: int):
    executed = []
    last_rows = []
    for statement in statements:
        sql = ensure_limit(statement, limit)
        cursor.execute(sql)
        sql_kind = classify_sql(statement)
        entry = {
            "kind": sql_kind,
            "statement": sql,
        }
        if sql_kind in READ_ONLY_KINDS:
            rows = dict_rows(cursor, driver_name)
            if len(rows) > export_limit:
                rows = rows[:export_limit]
                entry["truncated"] = True
            last_rows = rows
            entry["row_count"] = len(rows)
        else:
            entry["row_count"] = cursor.rowcount
        executed.append(entry)

    return {
        "ok": True,
        "statements": executed,
        "rows": last_rows,
    }


if __name__ == "__main__":
    raise SystemExit(main())
