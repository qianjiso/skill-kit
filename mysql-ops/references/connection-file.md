# Connection File

Use `.ai-yy/mysql/connection.json` as the canonical project-local registry for MySQL connections.

## Shape

```json
{
  "type": "mysql",
  "active": "local",
  "connections": {
    "local": {
      "host": "127.0.0.1",
      "port": 3306,
      "user": "root",
      "password": "secret",
      "database": "app_local",
      "charset": "utf8mb4",
      "timezone": "+08:00",
      "source": {
        "kind": "env",
        "path": ".env"
      }
    }
  }
}
```

## Rules

- `type` must be `mysql`.
- `active` must match a key inside `connections`.
- Each connection stores full credentials, including password.
- `charset` and `timezone` are optional but recommended when known.
- `source.kind` records how the connection was discovered, such as `env`, `spring-yaml`, `spring-properties`, `docker-compose`, or `config-code`.
- `source.path` should be a project-relative path whenever possible.
- Preserve unknown fields when editing the file so the user can extend the schema safely.
