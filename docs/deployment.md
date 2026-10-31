# Deployment and Operations

## Manus project resources

SmartAttend is configured as a Manus Web project with its server and managed database enabled. The API and application database remain inside Manus, as requested. The managed database is MySQL-compatible, not PostgreSQL. Flask accepts only a compatible MySQL/MariaDB `DATABASE_URL`, normalizes it to PyMySQL and applies the TLS policy carried by the Manus URL. The URL is consumed at runtime and is never compiled into the frontend or image.

The React SPA and API share one browser origin. In development the Vite server listens on Preview port `3000` and proxies relative `/api` calls to Flask on `5001`. The production Docker image compiles React, then serves `dist/` and the Flask REST API in one Gunicorn container. Gunicorn binds `0.0.0.0:${PORT:-3000}`. The unauthenticated deployment readiness path is `/api/health/ready`; liveness is `/_app/health`.

## Image build

The root `Dockerfile` uses a pinned pnpm release to install from the committed lockfile and build the React application, then installs only `backend/requirements.txt` in a Python runtime image with CA certificates. It copies the API, ML package and compiled SPA into the runtime image. It does not copy `.env`, `.venv`, local `node_modules` or the development test dependency set. No database credentials or Manus secret is needed during compilation.

The production image honors the platform `PORT` and uses `PORT=3000` as its default. The Flask app serves API and SPA from the same origin, so no separate static/backend path router or browser-facing absolute API URL is needed. Keep all frontend requests relative.

## Required runtime configuration

Set these through the protected Manus project secret workflow—not in source, chat, browser-visible build variables or logs:

- `SMARTATTEND_JWT_SECRET`: independent, high-entropy application JWT signing key (recommend at least 32 random bytes).
- `SMARTATTEND_BOOTSTRAP_TOKEN`: independent high-entropy secret for the one-time first Admin setup. It is not the user's login credential and is never returned by the API.

Manus supplies `DATABASE_URL`, `MANUS_JWT_SECRET`, `MANUS_PROJECT_ID`, and the OAuth portal/API values when project features are enabled. Do not create a second database credential or replace the platform URL. `DATABASE_URL` and OAuth material remain server-side.

Optional runtime settings:

| Variable | Default | Use |
| --- | --- | --- |
| `PORT` | `3000` | Published Gunicorn listener; platform supplied. |
| `SMARTATTEND_ALLOWED_ORIGINS` | empty | Comma-separated exact HTTPS origins when cross-origin browser access is truly required; same-origin is preferred. |
| `SMARTATTEND_COOKIE_SECURE` | `true` | Keep true in public HTTPS Preview/production; only set false for private plain-HTTP local development. |
| `SMARTATTEND_REQUIRE_HTTPS` | `true` | Require TLS for Pi APIs; only disable for loopback/local tests. |
| `SMARTATTEND_HEARTBEAT_OFFLINE_SECONDS` | `300` | Heartbeat age after which the device is shown offline. |
| `SMARTATTEND_OAUTH_TIMEOUT_SECONDS` | `10` | Timeout for server-side Manus OAuth calls. |

`SESSION_COOKIE_SECURE` and `SameSite=None` are derived from the explicit cookie configuration, not from the container's internal HTTP request. For public HTTPS Preview, preserve `webdev_app_session; SameSite=None; Secure; HttpOnly`. The CSRF cookie is secure and same-site compatible; writes from an authenticated browser require matching cookie/header tokens. Browser third-party-cookie controls can still block cross-site iframe cookies; offer the normal same-origin sign-in route if Preview policy prevents use.

## First administrator bootstrap

The first Admin flow is intentionally explicit. The user signs in through Manus OAuth, which writes a pending application user. They submit the protected `SMARTATTEND_BOOTSTRAP_TOKEN` from the signed-in `/login` setup screen. Flask requires that same signed-in pending account to have no role and requires the token. The API and the protected operator-only `provision-admin` CLI both create the same unique, durable `bootstrap_state` row atomically; later attempts are rejected even if that Admin is eventually disabled. The first-use action is audit logged. Keep the bootstrap secret private; do not share it with a Pi or normal user.

## Schema changes

The current managed database is at Alembic revision `565b089e2a03`. Check ORM/model alignment with:

```bash
.venv/bin/python -m flask --app backend.wsgi:app db check
```

For future schema changes, generate and review an additive migration in the Manus project environment, then apply once with `flask db upgrade`. Do not run schema generation against guessed metadata and do not apply a migration that unexpectedly drops/renames a table or column. The development and published project share the same database, so API/Pi/ML tests must always use their isolated SQLite fixture. Do not seed demo rows, reset the live database, or run `drop_all` against `DATABASE_URL`.

## TLS, API, CORS and device security

Terminate public TLS at the Manus hosting edge and use relative `/api` URLs. Same-origin deployment needs no permissive CORS configuration. If an independently hosted client becomes necessary, set only its exact HTTPS origin in `SMARTATTEND_ALLOWED_ORIGINS`; never use `*` with credentialed cookies. Pi endpoints independently enforce HTTPS, device bearer credentials and server-side classroom/session/student checks.

Each Pi credential is generated independently, returned one time and stored server-side only as a SHA-256 verifier; an Admin can revoke/rotate it. Enrollment codes are generated for an Admin-selected classroom, hashed in the database, expire within 1–60 minutes and can be redeemed once. Idempotency keys and unique constraints prevent event replay from creating duplicate attendance. Do not log OAuth codes, cookies, bootstrap/enrollment tokens, device bearer values, student payloads or database URLs.

## Health, logging and monitoring

- `GET /_app/health` is liveness and does not reveal credentials.
- `GET /api/health/ready` executes a read-only `SELECT 1` against the managed database and returns `200` only when ready.
- `GET /api/system/status` returns booleans/provider labels—not secret values—for database and authentication configuration.
- Each application response includes `X-Request-ID`; structured failure logs include request IDs but omit request bodies and connection details.
- Monitor readiness, DB connection/error rates, Alembic revision, API status-code distribution, device heartbeat age, rejected device events, local Pi queue failures and ML candidate/evaluation status.

## Backup and export limits

The Manus database capability used here does not expose a separate application-facing backup, point-in-time-recovery, snapshot or restore API. No full database backup was created by this project. Treat durability/retention guarantees as a hosting-provider question; do not infer backup completion from successful migration or publication. If an authorized operator needs an export, use the supported database-management/export process provided by Manus when available and independently validate the restore procedure before relying on it. SmartAttend's CSV/PDF attendance reports are scoped business reports, **not** full database backups. No unattended export schedule has been configured.

## Release steps

1. Build/test locally with the pinned lockfiles and isolated DB tests.
2. Check route manifest and managed-schema alignment.
3. Inspect any generated migration; apply only planned, non-destructive migrations to Manus's shared DB.
4. Confirm both protected application secrets are configured before expecting the OAuth or first-Admin path to work.
5. Keep Manus server/database enabled; deploy configuration uses root `Dockerfile` and `/api/health/ready`.
6. Check health after deployment and complete real Admin provisioning before onboarding a college; do not treat the demo preview as production data.
