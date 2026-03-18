# Discovery Sources

The discovery script should scan these sources in the project tree:

- `.env`
- `.env.*`
- `application.yml`
- `application.yaml`
- `application.properties`
- `docker-compose.yml`
- `docker-compose.yaml`
- `config/*.js`
- `config/*.ts`
- `config/*.php`

## Heuristics

- Parse JDBC URLs such as `jdbc:mysql://host:3306/db?...`.
- Parse MySQL URIs such as `mysql://user:pass@host:3306/db`.
- Read common key names like `DB_HOST`, `MYSQL_HOST`, `DB_PORT`, `MYSQL_PORT`, `DB_USER`, `MYSQL_USER`, `DB_PASSWORD`, `MYSQL_PASSWORD`, `DB_NAME`, and `MYSQL_DATABASE`.
- For Spring YAML and properties, look for `spring.datasource.url`, `spring.datasource.username`, and `spring.datasource.password`.
- For Docker Compose, inspect `environment`, `env_file`, and obvious MySQL service port mappings if present.
- For `config/*.js|ts|php`, use conservative regex matching for `host`, `port`, `user`, `username`, `password`, `database`, and connection URLs.

## Naming

- Prefer environment-like names such as `local`, `dev`, `test`, `staging`, and `prod`.
- Derive names from file suffixes when possible. Example: `.env.production` becomes `production`.
- If a name collides, append a numeric suffix.
