# Safety Rules

These rules are mandatory for the skill.

## Read Operations

- Allow `SELECT`, `SHOW`, `DESCRIBE`, and `EXPLAIN` without write confirmation.
- Apply a default `LIMIT` to plain `SELECT` statements that do not already define one.

## Write Operations

- Require explicit user confirmation before `INSERT`, `UPDATE`, `DELETE`, `REPLACE`, `TRUNCATE`, `CREATE`, `ALTER`, `DROP`, `RENAME`, `GRANT`, `REVOKE`, `BEGIN`, `START TRANSACTION`, `COMMIT`, or `ROLLBACK`.
- Reject `UPDATE` or `DELETE` without `WHERE` unless the user clearly confirms the full-table action and the tool call includes the override flag.
- Ask for an extra confirmation round when the connection name or host suggests production.

## Exports

- Default exports to a bounded row count.
- Tell the user when the export has been truncated.

## Failure Handling

- Stop immediately on connection errors.
- Roll back open transactions on execution failure.
- Show a short explanation of the blocked safety rule instead of silently skipping SQL.
