#!/usr/bin/env python3
"""Discover MySQL connection candidates from common project configuration files."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Dict, List, Optional

from mysql_common import (
    build_connection_payload,
    ensure_parent_dir,
    infer_name_from_path,
    parse_jdbc_mysql_url,
    parse_mysql_uri,
    parse_properties,
    flatten_yaml_like,
    print_json,
    save_connection_file,
    uniquify_name,
)

TARGET_FILES = {
    ".env",
    "application.yml",
    "application.yaml",
    "application.properties",
    "docker-compose.yml",
    "docker-compose.yaml",
}
TARGET_SUFFIXES = (".env.",)
CONFIG_CODE_SUFFIXES = {".js", ".ts", ".php"}
SKIP_DIRS = {".git", ".idea", ".vscode", "node_modules", "target", "dist", "build", ".codex", ".ai-yy"}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("project_root", nargs="?", default=".", help="Project root to scan")
    parser.add_argument("--output", help="Write the discovered connections to a connection file")
    parser.add_argument("--active", help="Explicit active connection name")
    args = parser.parse_args()

    root = Path(args.project_root).resolve()
    candidates = discover(root)
    payload = {
        "type": "mysql",
        "active": args.active,
        "connections": candidates,
    }
    if not payload["active"] and len(candidates) == 1:
        payload["active"] = next(iter(candidates))

    if args.output:
        save_connection_file(args.output, payload)

    print_json(payload)
    return 0


def discover(root: Path) -> Dict[str, Dict[str, object]]:
    results: Dict[str, Dict[str, object]] = {}

    for path in root.rglob("*"):
        if not path.is_file():
            continue
        if should_skip(path):
            continue
        relative_path = path.relative_to(root).as_posix()
        name = path.name

        discovered: List[Dict[str, object]] = []
        if name in TARGET_FILES or name.startswith(".env."):
            text = path.read_text(encoding="utf-8", errors="ignore")
            if name.startswith(".env"):
                discovered = discover_from_env(text, relative_path)
            elif name.endswith(".properties"):
                discovered = discover_from_properties(text, relative_path)
            elif name.endswith((".yml", ".yaml")) and "docker-compose" not in name:
                discovered = discover_from_yaml(text, relative_path)
            elif "docker-compose" in name:
                discovered = discover_from_docker_compose(text, relative_path)

        elif path.suffix in CONFIG_CODE_SUFFIXES and "config" in path.parts:
            text = path.read_text(encoding="utf-8", errors="ignore")
            discovered = discover_from_code(text, relative_path)

        for candidate in discovered:
            base_name = str(candidate.pop("_name"))
            final_name = uniquify_name(base_name, results.keys())
            results[final_name] = candidate

    return results


def should_skip(path: Path) -> bool:
    return any(part in SKIP_DIRS for part in path.parts)


def discover_from_env(text: str, relative_path: str) -> List[Dict[str, object]]:
    parsed = parse_properties(text)
    candidates: List[Dict[str, object]] = []

    url_keys = ["DATABASE_URL", "MYSQL_URL", "DB_URL", "SPRING_DATASOURCE_URL"]
    for key in url_keys:
        if key in parsed:
            uri_candidate = parse_mysql_uri(parsed[key]) or parse_jdbc_mysql_url(parsed[key])
            if uri_candidate:
                candidate = merge_candidate(
                    uri_candidate,
                    parsed,
                    source_kind="env",
                    source_path=relative_path,
                    name_hint=infer_name_from_path(relative_path),
                )
                if candidate:
                    candidates.append(candidate)

    direct_candidate = merge_candidate(
        {},
        parsed,
        source_kind="env",
        source_path=relative_path,
        name_hint=infer_name_from_path(relative_path),
    )
    if direct_candidate:
        candidates.append(direct_candidate)

    return dedupe_candidates(candidates)


def discover_from_properties(text: str, relative_path: str) -> List[Dict[str, object]]:
    parsed = parse_properties(text)
    candidate = merge_candidate(
        parse_jdbc_mysql_url(parsed.get("spring.datasource.url", "")) or {},
        {
            "SPRING_DATASOURCE_USERNAME": parsed.get("spring.datasource.username", ""),
            "SPRING_DATASOURCE_PASSWORD": parsed.get("spring.datasource.password", ""),
        },
        source_kind="spring-properties",
        source_path=relative_path,
        name_hint=infer_name_from_path(relative_path),
    )
    return [candidate] if candidate else []


def discover_from_yaml(text: str, relative_path: str) -> List[Dict[str, object]]:
    flattened = flatten_yaml_like(text)
    candidate = merge_candidate(
        parse_jdbc_mysql_url(flattened.get("spring.datasource.url", "")) or {},
        {
            "SPRING_DATASOURCE_USERNAME": flattened.get("spring.datasource.username", ""),
            "SPRING_DATASOURCE_PASSWORD": flattened.get("spring.datasource.password", ""),
        },
        source_kind="spring-yaml",
        source_path=relative_path,
        name_hint=infer_name_from_path(relative_path),
    )
    return [candidate] if candidate else []


def discover_from_docker_compose(text: str, relative_path: str) -> List[Dict[str, object]]:
    parsed = {}
    for key in ("MYSQL_HOST", "MYSQL_PORT", "MYSQL_USER", "MYSQL_PASSWORD", "MYSQL_DATABASE"):
        match = re.search(rf"{re.escape(key)}\s*[:=]\s*['\"]?([^'\"\n]+)", text)
        if match:
            parsed[key] = match.group(1).strip()

    if "MYSQL_HOST" not in parsed:
        parsed["MYSQL_HOST"] = "127.0.0.1"

    port_match = re.search(r"(\d+)\s*:\s*3306", text)
    if port_match:
        parsed["MYSQL_PORT"] = port_match.group(1)

    candidate = merge_candidate(
        {},
        parsed,
        source_kind="docker-compose",
        source_path=relative_path,
        name_hint=infer_name_from_path(relative_path),
    )
    return [candidate] if candidate else []


def discover_from_code(text: str, relative_path: str) -> List[Dict[str, object]]:
    candidates: List[Dict[str, object]] = []

    for pattern in (
        r"jdbc:mysql://[^'\"`\s]+",
        r"mysql://[^'\"`\s]+",
    ):
        for match in re.finditer(pattern, text, re.IGNORECASE):
            parsed = parse_mysql_uri(match.group(0)) or parse_jdbc_mysql_url(match.group(0))
            if parsed:
                candidate = merge_candidate(
                    parsed,
                    extract_code_keys(text),
                    source_kind="config-code",
                    source_path=relative_path,
                    name_hint=infer_name_from_path(relative_path),
                )
                if candidate:
                    candidates.append(candidate)

    direct_candidate = merge_candidate(
        {},
        extract_code_keys(text),
        source_kind="config-code",
        source_path=relative_path,
        name_hint=infer_name_from_path(relative_path),
    )
    if direct_candidate:
        candidates.append(direct_candidate)

    return dedupe_candidates(candidates)


def extract_code_keys(text: str) -> Dict[str, str]:
    parsed: Dict[str, str] = {}
    patterns = {
        "MYSQL_HOST": r"(?:host)\s*[:=]\s*['\"]([^'\"]+)['\"]",
        "MYSQL_PORT": r"(?:port)\s*[:=]\s*(\d+)",
        "MYSQL_USER": r"(?:user|username)\s*[:=]\s*['\"]([^'\"]+)['\"]",
        "MYSQL_PASSWORD": r"(?:password)\s*[:=]\s*['\"]([^'\"]*)['\"]",
        "MYSQL_DATABASE": r"(?:database|db|schema)\s*[:=]\s*['\"]([^'\"]+)['\"]",
    }
    for key, pattern in patterns.items():
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            parsed[key] = match.group(1)
    return parsed


def merge_candidate(
    parsed_url: Dict[str, object],
    values: Dict[str, str],
    *,
    source_kind: str,
    source_path: str,
    name_hint: str,
) -> Optional[Dict[str, object]]:
    host = (
        parsed_url.get("host")
        or pick_first(values, "MYSQL_HOST", "DB_HOST", "DATABASE_HOST", "SPRING_DATASOURCE_HOST")
    )
    port = (
        parsed_url.get("port")
        or pick_first(values, "MYSQL_PORT", "DB_PORT", "DATABASE_PORT", "SPRING_DATASOURCE_PORT")
        or 3306
    )
    user = (
        parsed_url.get("user")
        or pick_first(values, "MYSQL_USER", "DB_USER", "DATABASE_USER", "SPRING_DATASOURCE_USERNAME")
    )
    password = (
        parsed_url.get("password")
        or pick_first(values, "MYSQL_PASSWORD", "DB_PASSWORD", "DATABASE_PASSWORD", "SPRING_DATASOURCE_PASSWORD")
    )
    database = (
        parsed_url.get("database")
        or pick_first(values, "MYSQL_DATABASE", "DB_NAME", "DATABASE_NAME", "SPRING_DATASOURCE_DATABASE")
    )

    if not all((host, port, user is not None, password is not None, database)):
        return None

    candidate = build_connection_payload(
        host=str(host),
        port=int(port),
        user=str(user),
        password=str(password),
        database=str(database),
        source_kind=source_kind,
        source_path=source_path,
    )
    candidate["_name"] = name_hint
    return candidate


def pick_first(values: Dict[str, str], *keys: str):
    for key in keys:
        value = values.get(key)
        if value not in (None, ""):
            return value
    return None


def dedupe_candidates(candidates: List[Dict[str, object]]) -> List[Dict[str, object]]:
    deduped: List[Dict[str, object]] = []
    seen = set()
    for candidate in candidates:
        fingerprint = json.dumps(
            {
                "host": candidate.get("host"),
                "port": candidate.get("port"),
                "user": candidate.get("user"),
                "database": candidate.get("database"),
                "source_path": candidate.get("source", {}).get("path"),
            },
            sort_keys=True,
        )
        if fingerprint in seen:
            continue
        seen.add(fingerprint)
        deduped.append(candidate)
    return deduped


if __name__ == "__main__":
    raise SystemExit(main())
