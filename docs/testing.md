# Testing Strategy

## Safe test boundary

The Manus-managed database is shared across Cloud development and the published app. Test writes/deletions against it would affect live project data. All automated API integration tests use a fresh in-memory SQLite database configured through Flask's `TESTING` mode. ML feature and Pi queue tests use local Python objects/files under temporary test directories. Tests must never set `DATABASE_URL` as a fixture target, call `db.drop_all()` on a non-test app, seed fictional attendance into Manus, or use a real Raspberry Pi credential.

## Automated checks

Run from the project root:

```bash
.venv/bin/python -m pytest backend/tests smartattend_ml/tests iot/tests -q
.venv/bin/python -m compileall -q backend iot smartattend_ml
pyright --project pyrightconfig.json
pnpm typecheck
pnpm build
```

Coverage includes:

- Flask liveness/readiness and database-backed authentication role resolution.
- Student own-record-only behavior, Staff section/assignment scope and inaccessible-record behavior.
- One-time first-Admin setup and protection against unprovisioned role escalation.
- One-time, classroom-scoped Pi enrollment; secure credential storage; device HTTPS rules; heartbeat payload; queue idempotency/backoff/permanent failure recording.
- Accepted/retried device attendance, server idempotency and a single persisted notification for a duplicate retry.
- PDF report response format without writing report data to the managed DB.
- ML future-feature causality, target window and purged chronological split behavior.
- React compile/build with separate authenticated live workspace and visibly labeled demo fixtures.

## Read-only Manus environment checks

These operations are safe for routine inspection:

```bash
curl -i http://127.0.0.1:5001/api/health/ready
.venv/bin/python -m flask --app backend.wsgi:app db check
curl -i http://127.0.0.1:3000/manus-routes.json
```

The `ready` endpoint performs `SELECT 1`; `db check` compares model metadata with the managed schema but applies no migration; the route request only reads the static JSON manifest.

## Migration procedure

A `flask db migrate` command compares metadata and the current managed schema to write a local revision. Review the full generated migration before running `flask db upgrade`. A planned additive upgrade creates/alters the intended managed schema; never apply a generated destructive drop/rename as an incidental test. The current database schema is at `565b089e2a03`, aligned with ORM metadata.

## Manual product checks

Use the Manus Preview for the actual website. Guests must see the preview/sample-data disclosure; selecting a demo role must not authorize API access. Authenticated views appear only after Flask verifies Manus identity, database role/profile and account status. A failed session check must hide live records, not substitute example data. Verify first-Admin setup with a protected token only in the secure application form and retire/rotate the secret under the normal project secret workflow after bootstrap if policy requires it.

For Pi validation, use a test enrollment token and local mock server/controlled test device. Verify HTTPS, no token/credential in output, one-time enrollment, explicit Admin activation, classroom mapping, unique event identifiers, duplicate retries and terminal failure messages. Do not use real biometric material or issue a real attendance event during automated tests.

## Current validation evidence

The implementation suite has passed 14 isolated Python tests after adding schema-valid Pi heartbeat coverage. Strict TypeScript typecheck and Vite production build have passed; the build leaves only a chunk-size advisory for the compressed Recharts bundle. API readiness has returned `200` from a read-only managed-database `SELECT 1`, route-manifest fetch has returned `200` JSON, and Alembic reports no model/schema drift after the reviewed additive bootstrap-state migration.
