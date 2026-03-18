#!/usr/bin/env python3
"""Inspect, validate, and switch the active MySQL connection file."""

from __future__ import annotations

import argparse

from mysql_common import (
    DEFAULT_CONNECTION_FILE,
    MysqlOpsError,
    load_connection_file,
    mask_connection,
    print_json,
    save_connection_file,
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    show_parser = subparsers.add_parser("show", help="Show the saved connections with masked passwords")
    show_parser.add_argument("--connection-file", default=DEFAULT_CONNECTION_FILE)

    validate_parser = subparsers.add_parser("validate", help="Validate the connection file structure")
    validate_parser.add_argument("--connection-file", default=DEFAULT_CONNECTION_FILE)

    switch_parser = subparsers.add_parser("switch", help="Switch the active connection")
    switch_parser.add_argument("--connection-file", default=DEFAULT_CONNECTION_FILE)
    switch_parser.add_argument("--name", required=True, help="Connection name to activate")

    args = parser.parse_args()

    try:
        if args.command == "show":
            data = load_connection_file(args.connection_file)
            masked = {
                "type": data["type"],
                "active": data.get("active"),
                "connections": {name: mask_connection(conn) for name, conn in data["connections"].items()},
            }
            print_json(masked)
            return 0

        if args.command == "validate":
            load_connection_file(args.connection_file)
            print(f"Connection file is valid: {args.connection_file}")
            return 0

        if args.command == "switch":
            data = load_connection_file(args.connection_file)
            if args.name not in data["connections"]:
                raise MysqlOpsError(f"Connection '{args.name}' not found")
            data["active"] = args.name
            save_connection_file(args.connection_file, data)
            print(f"Active connection switched to '{args.name}'")
            return 0

    except MysqlOpsError as exc:
        print(f"ERROR: {exc}")
        return 1

    return 1


if __name__ == "__main__":
    raise SystemExit(main())
