# SmartAttend AI — Implementation Plan

## Approved scope and architecture

The user has changed the infrastructure direction: keep the full API and application database inside Manus. This supersedes the earlier external-PostgreSQL approval. The project already has Manus `server:true` and `database:true`; the Manus-managed database is MySQL-compatible, not PostgreSQL. Flask will use the platform-injected `DATABASE_URL`, and the React frontend, Flask API and managed database will all be served/hosted within this Manus project. Do not request or use an external database URL, do not use an external API host, and do not treat managed MySQL as PostgreSQL. The database is shared by development and the published app, so tests use an isolated SQLite fixture/database and never delete or reset managed data.

The initialized flexible Web project is empty and uses React + TypeScript + Vite, Tailwind CSS, Axios, React Router and Recharts for the frontend; Python Flask + Flask blueprints + SQLAlchemy/Flask-Migrate for the API; and the Manus-managed MySQL-compatible database for durable state. During development, Vite listens on the declared Preview port 3000 and proxies relative `/api` calls to Flask on an internal port. In production, a Docker build compiles the frontend and runs Flask/Gunicorn on `PORT` (default 3000), serving the SPA and API from the same Manus-hosted container. Read the platform `DATABASE_URL` at runtime only; never require it during compilation or expose it to browser code/logs.

Authentication defaults to Manus OAuth because no other identity provider was requested. The application will validate the supported Preview/platform JWT and establish its own application session. Map each authenticated identity to database-backed Student, Staff or Admin permissions. No hard-coded demo identities or development-auth bypass. Authorization is enforced on the server: students can access only their own records, and staff can manage only assigned subjects/classes. Privileged actions and attendance corrections are auditable. Each Pi receives an independently issued credential stored as a one-way verifier; device endpoints require authenticated HTTPS.

## Phases and implementation decisions

### Phase 1 — Architecture and functional UI (delivered)

Implement the responsive shell, sign-in entry, role-aware navigation, Student/Staff/Admin dashboard views, attendance history/marking, prediction, reports/analytics and IoT device-management screens. Fictional fixture values appear only in conspicuously labeled demo/preview views; no sample attendance, prediction, notification or device state is represented as live. Replace demo-only interactions with backend data only after the respective API exists. Keep reusable forms/tables/charts/metrics/filters, clear empty/loading/offline/error states and accessible controls.

### Phase 2 — Manus-hosted backend and managed database

Organize Flask into modules for authentication, students, staff, admin, attendance, subjects, devices, predictions, notifications and reports. Validate request schemas, use consistent JSON errors and request IDs, enforce JWT-backed sessions and role/ownership checks, and document the REST surface with OpenAPI. Use SQLAlchemy models and versioned Alembic migrations with the Manus-managed MySQL-compatible `DATABASE_URL`. Required entities: Users, Students, Staff, Departments, Subjects, Class sections, Staff subject assignments, Class sessions, Attendance records, Raspberry Pi devices, Device credentials, Device events, ML predictions, Notifications and Audit logs. Add a classroom mapping entity, attendance-correction workflow and durable model-version/artifact registry where needed. Add foreign keys, unique event/idempotency constraints, indexes and timestamps. Do not seed live tables with fictional attendance.

### Phase 3 — Raspberry Pi integration

Implement secure device registration and activation, unique device credentials, device-to-classroom mapping, heartbeat/status/health monitoring, event submission and auditable failed events. Required routes: `POST /api/device/register`, `POST /api/device/heartbeat`, `POST /api/device/attendance`, `GET /api/device/status`, and `GET /api/admin/devices`. Requests are JSON and carry authenticated device identity, event IDs, timestamps and idempotency keys. Prevent duplicate records even if requests are replayed. A hardware-neutral Pi client persists failed events locally and retries with backoff using the same event identity. Provide an adapter/protocol for future RFID, QR, fingerprint or camera sensors without assuming the sensor or including sensor-specific wiring.

### Phase 4 — ML and documentation

Build a Pandas/NumPy/scikit-learn pipeline starting with a Random Forest Regressor for future attendance percentage; optional risk classification remains optional. Features: historical attendance, total classes, present classes, recent attendance trends and subject-wise attendance. Avoid leakage, evaluate chronologically, retain metrics and limitations, and report predicted percentage, risk category and important features. Confidence stays null unless calibrated and evaluated. Store model versions/artifacts/metrics and predictions durably in the Manus-managed database; distinguish predictions from attendance facts.

Deliver system and architecture diagrams, a relational ER diagram for the managed database, source folder structure, OpenAPI documentation, schema/migrations, Pi integration module, ML train/predict/evaluation modules, device dashboard, deployment/operations instructions, test strategy and README. Explain env vars, HTTPS, CORS, managed-database constraints, backups/exports, logging and monitoring. Do not claim a database backup API or restore service that the platform does not expose.

## Project structure

```text
smartattend/
├── src/                         # React + TypeScript SPA
│   ├── App.tsx                  # Browser routes and authenticated role gates
│   ├── components/              # Brand mark, app layout, charts and shared UI
│   ├── lib/                     # Axios client, OAuth session context and demo fixtures
│   └── pages/                   # Login, role dashboard, attendance, forecasts, reports, devices
├── public/                      # Favicon, route manifest and static files
├── backend/
│   ├── app/api/                 # Flask auth/student/staff/admin/attendance/subjects/device/ML/report routes
│   ├── app/models.py            # SQLAlchemy managed-MySQL-compatible models
│   ├── app/services/            # Authorization, audits and business logic
│   ├── app/config.py            # Runtime-only settings and MySQL URL normalization
│   ├── migrations/versions/     # Alembic migration history
│   ├── tests/                   # Isolated SQLite/API tests
│   └── wsgi.py                  # Production Flask/Gunicorn entrypoint
├── iot/                         # Hardware-neutral Pi client, durable retry queue, sensor protocol
├── smartattend_ml/              # Feature engineering, chronological evaluation and train/predict
├── docs/                        # Architecture, diagrams, ERD, OpenAPI, deployment/operations
├── Dockerfile                   # Multi-stage frontend build + Flask runtime
├── .env.example                 # Safe local variable names/examples only
├── plan.md                      # Approved approach and design system
├── TODO.md                      # Full request criteria and delivery status
└── README.md                    # Setup, usage, deployment and limitations
```

## Design system

Three distinct directions considered (tail-sampled estimates, each under 0.10): **Swiss editorial campus ledger** (0.07), **instrument-panel neo-brutalism** (0.04), **quiet botanical academic modernism** (0.06). Chosen: **Swiss editorial campus ledger**, a precise, calm data-product aesthetic that makes attendance status legible without decorative noise.

- **Design Movement:** Swiss International Typographic Style adapted to a contemporary academic information system.
- **Core Principles:** Legibility before ornament; status is explicit and never inferred only from color; dense records remain scannable; interactions are direct and reversible where possible.
- **Color Philosophy:** Warm porcelain surfaces evoke a clean academic record, deep ink anchors navigation and hierarchy, a distinctive cobalt marks active navigation and primary actions, and restrained teal/amber/red are reserved for positive, cautionary and critical status. Demo and live states have separate labels, not just color.
- **Layout Paradigm:** A persistent narrow navigation rail beside a broad, left-aligned working canvas; dashboard pages use a compact orientation/header band, a non-uniform row of key metrics, then a wide primary record/chart with a secondary context panel. Responsive layouts collapse the rail and reflow data tables into accessible card/list presentations.
- **Signature Elements:** Fine ruled separators like a modern registrar ledger; compact subject/status tags with explicit words; a cobalt “active record” marker repeated in navigation and table selection.
- **Interaction Philosophy:** Filters update predictable views, destructive/corrective operations require a visible review step and audit context, keyboard focus is clear, and loading/empty/error/demo states explain what is happening.
- **Animation:** Short 140–200 ms fades/slides for navigation and panel transitions; subtle metric/chart entrance only on initial load; respect reduced-motion preferences; no looping or attention-seeking motion.
- **Typography System:** Inter for interface and dense data; Newsreader for occasional editorial page titles only. Use tabular numerals for percentages/counts, restrained weight/size hierarchy, and avoid tiny metadata.
- **Brand Essence:** “A trustworthy attendance record and early-warning workspace for college communities”; personality: precise, supportive, accountable.
- **Brand Voice:** Clear and calm, never alarmist. Example lines: “Attendance, recorded with context.” “This forecast is an estimate—not an attendance record.”
- **Wordmark & Logo:** Custom “SmartAttend” wordmark paired with a compact ledger/check mark: three ruled rows with one cobalt check intersecting a fine circular attendance ring; use an original inline SVG/CSS mark rather than a stock logo.
- **Signature Brand Color:** Registrar Cobalt `#3156C8`.


### Supplied identity integration

The user-provided `SmartAttendAIEmblemLogo.png` is the source of truth for branded surfaces. Use the processed `public/smartattend-icon.png` as the compact app/shell emblem and `public/smartattend-lockup.png` on the loading splash and in platform project-logo metadata. Preserve the exact creator credit present in the supplied lockup: “Developed by Simbu AI/ML from ESEC.” This supersedes the illustrative inline-SVG/CSS mark concept above; do not redraw or replace the user’s identity.
