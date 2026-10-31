# SmartAttend AI — Delivery TODO

Items remain open until there is implementation evidence for the stated outcome. UI-only demonstration work does not complete live API, database, IoT or ML outcomes.

## 1. Responsive React application and role dashboards

- [x] Build the frontend with React.js, Tailwind CSS, Axios, React Router and Recharts.
- [x] Create a modern, professional, responsive web dashboard with reusable React components and a consistent design system.
- [x] Build a Login page; Student dashboard; Staff dashboard; Admin dashboard; Attendance history; Attendance marking interface; ML prediction dashboard; Reports and analytics; and IoT Device Management dashboard. Login clearly states authentication is not connected; dashboard figures are clearly identified as fictional examples.
- [x] Include responsive sidebar, top navigation, statistics cards, charts, data tables, filters, search, pagination, notifications and device status indicators. Browser-only actions are disclosed as demo-only.
- [x] Use realistic sample data only for UI demonstrations. Never present simulated attendance or device status as real live data.

## 2. Student privacy and attendance views

- [ ] Display the student profile, roll number, department and year, overall attendance percentage, subject-wise attendance, attendance history, AI attendance prediction and attendance notifications.
- [ ] Students must only access their own records.

## 3. Staff attendance and assignment-scoped access

- [ ] Display assigned subjects, student lists, daily attendance, Present/Absent marking, attendance correction workflow, subject-wise attendance reports and attendance trends.
- [ ] Staff can only manage assigned classes and subjects.

## 4. Admin analytics and management

- [ ] Display total students, total staff, department-wise attendance, year-wise attendance, subject analytics, low-attendance risk reports and ML prediction analytics.
- [ ] Include student and staff management, CSV/PDF export, and an IoT Device Management section.

## 5. Manus-hosted Flask API, authentication and authorization

- [ ] Build modular Flask REST APIs inside the Manus-hosted server with separate modules for Authentication, Students, Staff, Admin, Attendance, Subjects, IoT devices, ML predictions, Notifications and Reports.
- [ ] Implement JWT authentication, role-based authorization, input validation, error handling, SQLAlchemy ORM, database migrations and API documentation.
- [ ] React communicates with the Manus-hosted Flask API using Axios and a centralized API service.
- [ ] Implement authentication token/session handling, protected routes, role-based navigation, API loading states, API error handling and dashboard data fetching.
- [ ] Enforce student self-record access and staff assigned-class/subject access on server APIs, not only in client navigation.

## 6. Manus-managed relational database and migrations

- [ ] Use the already-enabled Manus-managed MySQL-compatible database through its runtime `DATABASE_URL`; keep the application database and API hosted in Manus. This supersedes the earlier external-PostgreSQL direction; do not request or use an external DSN.
- [ ] Create relational tables for Users, Students, Staff, Departments, Subjects, Class sections, Staff subject assignments, Class sessions, Attendance records, Raspberry Pi devices, Device credentials, Device events, ML predictions, Notifications and Audit logs. Add only the supporting classroom, correction-review and ML-model-version entities needed for the requested features.
- [ ] Add foreign keys, unique constraints, indexes and appropriate timestamps.
- [ ] Commit repeatable schema migrations and read the platform connection at runtime; do not put credentials in source, frontend code, logs or documentation.
- [ ] Treat development and published use as the same managed database. Do not reset or run destructive tests against it; use an isolated test database.

## 7. Raspberry Pi device operations and API

- [ ] Design modular Raspberry Pi integration. Raspberry Pi communicates with the Manus-hosted Flask API through secure HTTPS REST APIs.
- [ ] Every device must have a unique device ID and credential. Provide device registration and activation, device-to-classroom mapping, attendance event submission, heartbeat monitoring, online/offline device status, failed event logging, offline event queue and automatic retry, duplicate event prevention, and device health monitoring.
- [ ] Do not assume attendance sensor type. Create a pluggable sensor interface supporting future RFID, QR, fingerprint or camera integration. Do not implement sensor-specific hardware wiring until the actual sensor is confirmed.
- [ ] Implement JSON endpoints: `POST /api/device/register`; `POST /api/device/heartbeat`; `POST /api/device/attendance`; `GET /api/device/status`; `GET /api/admin/devices`.
- [ ] Device API requests use device authentication, event IDs, timestamps and idempotency.

## 8. ML attendance prediction and evaluation

- [ ] Build an attendance prediction pipeline using Python, Pandas, NumPy and Scikit-learn.
- [ ] Start with a Random Forest Regressor for future attendance prediction. Include optional risk classification model.
- [ ] Use features: historical attendance, total classes, present classes, recent attendance trends and subject-wise attendance.
- [ ] Output predicted attendance percentage, attendance risk category, prediction confidence when properly calibrated, and important influencing features.
- [ ] Avoid data leakage. Use chronological train/test evaluation. Document model metrics and limitations.

## 9. Architecture, API and operating documentation

- [ ] Produce complete system architecture and architecture diagrams; a relational ER diagram for the Manus-managed database; complete folder structure; API documentation; managed-database schema and migrations; Raspberry Pi integration module; ML training and prediction module; device management dashboard; deployment instructions; testing strategy; and README documentation.
- [ ] Provide deployment architecture for React frontend, Flask backend, Manus-managed database and Raspberry Pi devices.
- [ ] Include environment variables, HTTPS, CORS, database backup/export limitations, logging and monitoring.
- [ ] Keep the application modular, secure, maintainable and ready for future hardware expansion.

## 10. Phased delivery and honest data state

- [ ] Build the application in phases: first create architecture and functional UI; then implement backend and managed database; next integrate Raspberry Pi communication; finally implement and evaluate ML prediction system.
- [ ] Keep sample attendance, sample predictions, sample notifications and sample device data visibly identified as demonstration-only wherever shown. Never present simulated attendance or device status as real live data.
