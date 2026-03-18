#!/usr/bin/env python3
"""Test connectivity for the active or named MySQL connection."""

from __future__ import annotations

import time

from mysql_common import (
    MysqlOpsError,
    build_common_parser,
    create_cursor,
    load_connection_file,
    resolve_connection,
    connect_mysql,
    print_json,
)


def main() -> int:
    parser = build_common_parser(__doc__ or "Test MySQL connectivity")
    args = parser.parse_args()

    try:
        data = load_connection_file(args.connection_file)
        name, connection_info = resolve_connection(data, args.name)
        start = time.perf_counter()
        driver_name, connection = connect_mysql(connection_info)
        cursor = create_cursor(connection, driver_name)
        cursor.execute("SELECT VERSION() AS version, DATABASE() AS current_database")
        row = cursor.fetchone()
        elapsed_ms = round((time.perf_counter() - start) * 1000, 2)
        cursor.close()
        connection.close()
        print_json(
            {
                "ok": True,
                "connection": name,
                "driver": driver_name,
                "latency_ms": elapsed_ms,
                "server": row,
            }
        )
        return 0
    except MysqlOpsError as exc:
        print(f"ERROR: {exc}")
        return 1
    except Exception as exc:
        print(f"ERROR: Failed to connect: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
