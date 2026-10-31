import { Database, LockKeyhole, Radio, Server, ShieldCheck } from 'lucide-react';

const settings = [
  { icon: ShieldCheck, title: 'Identity and roles', detail: 'Manus OAuth, JWT-backed application session, and database-backed Student / Staff / Admin authorization.', state: 'Not connected · Phase 2' },
  { icon: Database, title: 'Application database', detail: 'External PostgreSQL via a protected SMARTATTEND_POSTGRES_URL setting. Managed MySQL remains unused.', state: 'Not configured' },
  { icon: Server, title: 'API service', detail: 'Modular Flask REST API with SQLAlchemy, migrations, validation and OpenAPI documentation.', state: 'Not started · Phase 2' },
  { icon: Radio, title: 'Raspberry Pi devices', detail: 'Authenticated HTTPS events, heartbeats, idempotency and retry queue. Sensor interface remains pluggable.', state: 'Not connected · Phase 3' },
  { icon: LockKeyhole, title: 'Data and audit policy', detail: 'Server-side ownership checks, staff assignment scope, correction workflow and audit logging.', state: 'Not active in UI preview' },
];

export function SettingsPage() {
  return <>
    <div className="page-heading"><div><p className="eyebrow">SYSTEM CONFIGURATION · ARCHITECTURE PREVIEW</p><h1>Workspace settings</h1><p className="page-subtitle">A transparent view of current connection status and approved implementation choices.</p></div></div>
    <section className="panel">
      <div className="settings-section"><h2>Implementation status</h2><p>The application is currently in Phase 1. The items below describe planned integrations, not connected services.</p></div>
      {settings.map(({ icon: Icon, title, detail, state }) => <div className="settings-section settings-row" key={title}><div style={{ display: 'flex', alignItems: 'flex-start', gap: 11 }}><span className="settings-icon"><Icon size={16} /></span><div><strong>{title}</strong><small>{detail}</small></div></div><span className="settings-state">{state}</span></div>)}
      <div className="settings-section"><h2>Data demonstration policy</h2><p>All people, attendance entries, alerts, charts and device states currently shown are fictional UI fixtures. No demonstration action writes to a server or database. The sign-in screen does not authenticate anyone.</p></div>
    </section>
  </>;
}
