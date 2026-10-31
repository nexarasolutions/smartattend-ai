import { useCallback, useEffect, useMemo, useState, type FormEvent, type ReactNode } from 'react';
import { Download, RefreshCw, ShieldCheck, Wifi, WifiOff } from 'lucide-react';
import { useLocation } from 'react-router-dom';
import { api, toApiFailure } from '../lib/api';
import { useAuth } from '../lib/auth';
import type { PreviewRole } from '../types';

interface Envelope<T> { data: T }
type Row = Record<string, unknown>;
type Bundle = Record<string, unknown>;
interface Column { key: string; label: string }

const columns: Record<string, Column[]> = {
  attendance: [{ key: 'date', label: 'Session (UTC)' }, { key: 'student', label: 'Student' }, { key: 'roll_number', label: 'Roll number' }, { key: 'subject', label: 'Subject' }, { key: 'section', label: 'Section' }, { key: 'status', label: 'Status' }, { key: 'source', label: 'Source' }],
  students: [{ key: 'name', label: 'Student' }, { key: 'roll_number', label: 'Roll number' }, { key: 'department', label: 'Department' }, { key: 'academic_year', label: 'Year' }, { key: 'section', label: 'Section' }, { key: 'email', label: 'Email' }, { key: 'status', label: 'Status' }],
  staff: [{ key: 'name', label: 'Staff member' }, { key: 'staff_number', label: 'Staff number' }, { key: 'department', label: 'Department' }, { key: 'email', label: 'Email' }, { key: 'status', label: 'Status' }],
  devices: [{ key: 'device_id', label: 'Device ID' }, { key: 'classroom', label: 'Classroom' }, { key: 'status', label: 'Lifecycle' }, { key: 'connection_status', label: 'Connection' }, { key: 'firmware_version', label: 'Firmware' }, { key: 'last_heartbeat_at', label: 'Last heartbeat (UTC)' }],
  predictions: [{ key: 'generated_at', label: 'Generated (UTC)' }, { key: 'subject', label: 'Subject' }, { key: 'predicted_percentage', label: 'Predicted attendance' }, { key: 'risk_category', label: 'Risk' }, { key: 'calibrated_confidence', label: 'Calibrated confidence' }, { key: 'model_version', label: 'Model version' }],
  lowAttendance: [{ key: 'name', label: 'Student' }, { key: 'roll_number', label: 'Roll number' }, { key: 'department', label: 'Department' }, { key: 'attendance_percentage', label: 'Attendance' }, { key: 'records', label: 'Records' }],
  sessions: [{ key: 'starts_at', label: 'Start (UTC)' }, { key: 'subject', label: 'Subject' }, { key: 'section', label: 'Section' }, { key: 'status', label: 'State' }, { key: 'id', label: 'Session ID' }],
  assignments: [{ key: 'subject_code', label: 'Subject' }, { key: 'subject', label: 'Subject name' }, { key: 'section', label: 'Section' }, { key: 'valid_from', label: 'Valid from' }, { key: 'valid_to', label: 'Valid to' }],
  corrections: [{ key: 'student', label: 'Student' }, { key: 'roll_number', label: 'Roll number' }, { key: 'subject', label: 'Subject' }, { key: 'section', label: 'Section' }, { key: 'prior_status', label: 'Current status' }, { key: 'requested_status', label: 'Requested' }, { key: 'reason', label: 'Reason' }, { key: 'requested_by', label: 'Requested by' }],
  departments: [{ key: 'code', label: 'Code' }, { key: 'name', label: 'Department' }],
  classrooms: [{ key: 'building', label: 'Building' }, { key: 'room_code', label: 'Classroom' }, { key: 'description', label: 'Description' }],
  sections: [{ key: 'department', label: 'Department' }, { key: 'code', label: 'Section' }, { key: 'academic_year', label: 'Year' }, { key: 'term', label: 'Term' }, { key: 'classroom', label: 'Room' }],
  users: [{ key: 'display_name', label: 'Account' }, { key: 'email', label: 'Email' }, { key: 'role', label: 'Role' }, { key: 'status', label: 'Account status' }],
  notifications: [{ key: 'created_at', label: 'Created (UTC)' }, { key: 'title', label: 'Notification' }, { key: 'body', label: 'Details' }, { key: 'read_at', label: 'Read' }],
  studentSubjectAttendance: [{ key: 'subject_code', label: 'Code' }, { key: 'subject', label: 'Subject' }, { key: 'classes_attended', label: 'Attended' }, { key: 'classes_held', label: 'Classes held' }, { key: 'attendance_percentage', label: 'Attendance' }],
};

function obj(value: unknown): Row { return value && typeof value === 'object' && !Array.isArray(value) ? value as Row : {}; }
function list(value: unknown): Row[] { return Array.isArray(value) ? value.filter((item): item is Row => Boolean(item) && typeof item === 'object') : []; }
function text(value: unknown): string {
  if (value === null || value === undefined || value === '') return '—';
  if (typeof value === 'boolean') return value ? 'Yes' : 'No';
  if (typeof value === 'object') return JSON.stringify(value);
  return String(value);
}
function percent(value: unknown) { return typeof value === 'number' ? `${value.toFixed(1)}%` : text(value); }

async function requestData<T>(path: string): Promise<T> {
  const response = await api.get<Envelope<T>>(path);
  return response.data.data;
}

function RecordTable({ rows, kind, empty = 'No persisted records are available in this authorized scope.' }: { rows: Row[]; kind: string; empty?: string }) {
  const fields = columns[kind] ?? Object.keys(rows[0] ?? {}).slice(0, 8).map((key) => ({ key, label: key.replaceAll('_', ' ') }));
  if (!rows.length) return <div className="live-empty">{empty}</div>;
  return <div className="live-table-scroll"><table className="live-table"><thead><tr>{fields.map((column) => <th key={column.key}>{column.label}</th>)}</tr></thead><tbody>{rows.map((row, index) => <tr key={text(row.id) === '—' ? `${kind}-${index}` : text(row.id)}>{fields.map((column) => <td key={column.key}>{text(row[column.key])}</td>)}</tr>)}</tbody></table></div>;
}

function MetricCards({ metrics }: { metrics: Array<{ label: string; value: string; helper?: string }> }) {
  return <div className="live-metric-grid">{metrics.map((metric) => <article className="live-metric" key={metric.label}><span>{metric.label}</span><strong>{metric.value}</strong><small>{metric.helper ?? 'Live database records'}</small></article>)}</div>;
}

function LivePage({ role, path, data, reload }: { role: PreviewRole; path: string; data: Bundle; reload: () => void }) {
  const [search, setSearch] = useState('');
  const [actionMessage, setActionMessage] = useState<string | null>(null);
  const summary = obj(data.reportSummary ?? data.adminSummary);
  const attendance = list(data.attendance);
  const sessions = list(data.sessions);
  const students = list(data.students);
  const predictions = list(data.predictions);
  const devices = list(data.devices);
  const title = path === '/' ? 'Overview' : path === '/predictions' ? 'AI attendance forecast' : path === '/reports' ? 'Reports & analytics' : path === '/devices' ? 'IoT device management' : path === '/students' ? 'Student records' : path === '/staff' ? 'Staff & subject assignments' : path === '/settings' ? 'Workspace settings' : 'Attendance history';

  async function exportReport(format: 'csv' | 'pdf') {
    try {
      const response = await api.get(`/reports/attendance.${format}`, { responseType: 'blob' });
      const url = URL.createObjectURL(response.data as Blob);
      const anchor = document.createElement('a');
      anchor.href = url;
      anchor.download = `smartattend-attendance.${format}`;
      anchor.click();
      URL.revokeObjectURL(url);
      setActionMessage(`${format.toUpperCase()} export downloaded from the authorized API scope.`);
    } catch (error) { setActionMessage(toApiFailure(error).message); }
  }

  return (
    <section className="live-workspace">
      <div className="live-workspace-heading"><div><p className="eyebrow">LIVE DATABASE RECORDS · {role.toUpperCase()}</p><h1>{title}</h1><p>Values below are returned by the authenticated API connected to Supabase PostgreSQL. Real-world records.</p></div><button className="button button-secondary" onClick={reload}><RefreshCw size={15} /> Refresh</button></div>
      {actionMessage && <div className="live-action-message" role="status">{actionMessage}<button onClick={() => setActionMessage(null)} aria-label="Dismiss">×</button></div>}

      {path === '/' && role === 'Admin' && <AdminOverview summary={obj(data.adminSummary)} report={obj(data.reportSummary)} low={list(data.lowAttendance)} predictions={list(data.predictions)} corrections={list(data.corrections)} onReviewed={(message) => { setActionMessage(message); reload(); }} />}
      {path === '/' && role === 'Staff' && <StaffOverview summary={summary} assignments={list(data.assignments)} sessions={sessions} />}
      {path === '/' && role === 'Student' && <StudentOverview profile={obj(data.studentMe)} attendance={attendance} predictions={predictions} notifications={list(data.notifications)} subjectSummary={obj(data.studentSummary)} />}

      {path === '/attendance' && <>
        {(role === 'Staff' || role === 'Admin') && <ClassSessionCreateForm role={role} subjects={list(data.subjects)} sections={list(data.sections)} staff={list(data.staff)} assignments={list(data.assignments)} onSaved={(message) => { setActionMessage(message); reload(); }} />}
        {(role === 'Staff' || role === 'Admin') && <AttendanceMarkForm sessions={sessions} students={students} onSaved={(message) => { setActionMessage(message); reload(); }} />}
        {role === 'Staff' && attendance.length > 0 && <CorrectionForm records={attendance} onSaved={(message) => { setActionMessage(message); reload(); }} />}
        {role === 'Admin' && <CorrectionReview rows={list(data.corrections)} onReviewed={(message) => { setActionMessage(message); reload(); }} />}
        <LiveSection title="Attendance history"><RecordTable rows={attendance} kind="attendance" /></LiveSection>
        <LiveSection title="Class sessions"><RecordTable rows={sessions} kind="sessions" /></LiveSection>
      </>}

      {path === '/predictions' && <>
        <div className="live-honesty-note"><ShieldCheck size={16} /><span>Forecasts are shown only when a versioned model has stored a prediction. Confidence is blank unless calibration is persisted by the training pipeline.</span></div>
        {role === 'Admin' && <ModelAdminPanel models={list(data.models)} onUpdated={(message) => { setActionMessage(message); reload(); }} />}
        <LiveSection title="Persisted model predictions"><RecordTable rows={predictions} kind="predictions" empty="No model predictions have been trained and saved for this authorized scope." /></LiveSection>
      </>}

      {path === '/reports' && <>
        <div className="live-export-actions"><button className="button button-secondary" onClick={() => void exportReport('csv')}><Download size={15} /> Export CSV</button><button className="button button-secondary" onClick={() => void exportReport('pdf')}><Download size={15} /> Export PDF</button></div>
        <MetricCards metrics={[{ label: 'Attendance records', value: text(summary.total_records) }, { label: 'Overall attendance', value: percent(summary.attendance_percentage) }, { label: 'Below 75% threshold', value: text(summary.low_attendance_students_below_75) }, { label: 'Persisted predictions', value: text(obj(summary.prediction_analytics).persisted_predictions) }]} />
        <LiveSection title="Department-wise attendance"><RecordTable rows={list(summary.department_breakdown)} kind="department_breakdown" /></LiveSection>
        <LiveSection title="Year-wise attendance"><RecordTable rows={list(summary.year_breakdown)} kind="year_breakdown" /></LiveSection>
        <LiveSection title="Subject analytics"><RecordTable rows={list(summary.subject_analytics)} kind="subject_analytics" /></LiveSection>
        <LiveSection title="Low-attendance students"><div className="live-filter-row"><input value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Search this report" aria-label="Filter low attendance report" /></div><RecordTable rows={list(data.lowAttendance).filter((row) => `${text(row.name)} ${text(row.roll_number)} ${text(row.department)}`.toLowerCase().includes(search.toLowerCase()))} kind="lowAttendance" /></LiveSection>
      </>}

      {path === '/devices' && <>
        <DeviceEnrollmentForm classrooms={list(data.classrooms)} onIssued={(message) => setActionMessage(message)} />
        <LiveSection title="Registered Raspberry Pi devices"><DeviceTable rows={devices} classrooms={list(data.classrooms)} onUpdated={(message) => { setActionMessage(message); reload(); }} /></LiveSection>
      </>}

      {path === '/students' && <>
        <div className="live-filter-row"><input value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Search students" aria-label="Search students" /></div>
        {role === 'Admin' && <StudentProvisionForm users={list(data.pendingUsers)} departments={list(data.departments)} sections={list(data.sections)} onSaved={(message) => { setActionMessage(message); reload(); }} />}
        <LiveSection title="Students in your authorized scope"><RecordTable rows={students.filter((row) => `${text(row.name)} ${text(row.roll_number)} ${text(row.department)}`.toLowerCase().includes(search.toLowerCase()))} kind="students" /></LiveSection>
      </>}

      {path === '/staff' && <>
        {role === 'Admin' && <><StaffProvisionForm users={list(data.pendingUsers)} departments={list(data.departments)} onSaved={(message) => { setActionMessage(message); reload(); }} /><SubjectCreateForm departments={list(data.departments)} onSaved={(message) => { setActionMessage(message); reload(); }} /><AssignmentForm staff={list(data.staff)} subjects={list(data.subjects)} sections={list(data.sections)} onSaved={(message) => { setActionMessage(message); reload(); }} /></>}
        {role === 'Admin' && <LiveSection title="Staff directory"><RecordTable rows={list(data.staff)} kind="staff" /></LiveSection>}
        <LiveSection title={role === 'Staff' ? 'Your assigned subjects' : 'Subjects in this workspace'}><RecordTable rows={list(data.assignments).length ? list(data.assignments) : list(data.subjects)} kind="assignments" /></LiveSection>
      </>}

      {path === '/settings' && <>
        <SystemStatusCard status={obj(data.systemStatus)} />
        {role === 'Admin' && <><AcademicSetupForm departments={list(data.departments)} classrooms={list(data.classrooms)} onSaved={(message) => { setActionMessage(message); reload(); }} /><LiveSection title="Pending accounts"><RecordTable rows={list(data.pendingUsers)} kind="users" empty="No pending accounts. Students and staff are provisioned from their matching profile forms." /></LiveSection></>}
      </>}
    </section>
  );
}

function LiveSection({ title, children }: { title: string; children: ReactNode }) { return <section className="live-section"><div className="live-section-heading"><h2>{title}</h2><span>API data</span></div>{children}</section>; }

function CorrectionReview({ rows, onReviewed }: { rows: Row[]; onReviewed: (message: string) => void }) {
  const [error, setError] = useState('');
  async function review(row: Row, decision: 'approve' | 'reject') {
    setError('');
    try { await api.post(`/admin/attendance-corrections/${text(row.id)}/review`, { decision, review_note: '' }); onReviewed(`Correction ${decision === 'approve' ? 'approved' : 'rejected'} and audit logged.`); }
    catch (requestError) { setError(toApiFailure(requestError).message); }
  }
  return <LiveSection title="Pending attendance correction reviews">{error && <p className="live-error-text">{error}</p>}{rows.length ? <div className="live-table-scroll"><table className="live-table"><thead><tr>{columns.corrections.map((column) => <th key={column.key}>{column.label}</th>)}<th>Review</th></tr></thead><tbody>{rows.map((row) => <tr key={text(row.id)}>{columns.corrections.map((column) => <td key={column.key}>{text(row[column.key])}</td>)}<td><button className="text-button" onClick={() => void review(row, 'approve')}>Approve</button><button className="text-button" onClick={() => void review(row, 'reject')}>Reject</button></td></tr>)}</tbody></table></div> : <div className="live-empty">No pending correction requests.</div>}</LiveSection>;
}

function ModelAdminPanel({ models, onUpdated }: { models: Row[]; onUpdated: (message: string) => void }) {
  const [busy, setBusy] = useState(false); const [error, setError] = useState('');
  const activeModel = models.find((model) => model.state === 'active');
  async function runAction(action: 'train' | 'generate' | 'activate', modelVersion?: string) {
    setBusy(true); setError('');
    try {
      if (action === 'train') {
        const response = await api.post<Envelope<Row>>('/predictions/train', {}, { timeout: 120_000 });
        const candidate = response.data.data;
        onUpdated(`Candidate ${text(candidate.model_version)} trained and saved for Admin review.`);
      } else if (action === 'generate') {
        const response = await api.post<Envelope<Row>>('/predictions/generate', {}, { timeout: 120_000 });
        const result = response.data.data;
        onUpdated(`Predictions generated from ${text(result.model_version)}: ${text(result.created)} created, ${text(result.updated)} refreshed, ${text(result.skipped_insufficient_history)} skipped for insufficient history.`);
      } else if (modelVersion) {
        await api.post(`/predictions/models/${encodeURIComponent(modelVersion)}/activate`, {});
        onUpdated(`Model ${modelVersion} activated. Previous active versions were retired.`);
      }
    } catch (requestError) { setError(toApiFailure(requestError).message); }
    finally { setBusy(false); }
  }
  return <LiveSection title="Model registry & evaluation"><div className="live-honesty-note"><ShieldCheck size={15} /><span>Training reads only persisted attendance and uses a purged chronological holdout. Candidates stay inactive until an Admin reviews metrics. Confidence is not calibrated and remains blank.</span></div><div className="live-export-actions"><button className="button button-secondary" disabled={busy} onClick={() => void runAction('train')}>Train candidate from managed records</button><button className="button button-primary" disabled={busy || !activeModel} onClick={() => void runAction('generate')}>Generate persisted predictions</button></div>{error && <p className="live-error-text">{error}</p>}{models.length ? <div className="live-table-scroll"><table className="live-table"><thead><tr><th>Version</th><th>State</th><th>Algorithm</th><th>Train windows</th><th>Validation MAE</th><th>Baseline MAE</th><th>Validation RMSE</th><th>R²</th><th>Confidence</th><th>Action</th></tr></thead><tbody>{models.map((model) => { const metrics = obj(model.evaluation_metrics); return <tr key={text(model.model_version)}><td>{text(model.model_version)}</td><td>{text(model.state)}</td><td>{text(model.algorithm)}</td><td>{text(model.training_rows)}</td><td>{text(metrics.mae_percentage_points)}</td><td>{text(metrics.persistence_baseline_mae_percentage_points)}</td><td>{text(metrics.rmse_percentage_points)}</td><td>{text(metrics.r2)}</td><td>Not calibrated</td><td>{model.state === 'candidate' ? <button className="text-button" disabled={busy} onClick={() => void runAction('activate', text(model.model_version))}>Activate</button> : '—'}</td></tr>; })}</tbody></table></div> : <div className="live-empty">No model versions are stored. Training remains unavailable until enough real, chronological attendance history exists.</div>}</LiveSection>;
}

function toLocalDateTime(value: Date) {
  const shifted = new Date(value.getTime() - value.getTimezoneOffset() * 60_000);
  return shifted.toISOString().slice(0, 16);
}

function ClassSessionCreateForm({ role, subjects, sections, staff, assignments, onSaved }: { role: PreviewRole; subjects: Row[]; sections: Row[]; staff: Row[]; assignments: Row[]; onSaved: (message: string) => void }) {
  const [assignmentId, setAssignmentId] = useState(''); const [subjectId, setSubjectId] = useState(''); const [sectionId, setSectionId] = useState(''); const [staffId, setStaffId] = useState('');
  const [startsAt, setStartsAt] = useState(() => toLocalDateTime(new Date(Date.now() + 60_000)));
  const [endsAt, setEndsAt] = useState(() => toLocalDateTime(new Date(Date.now() + 61 * 60_000)));
  const [error, setError] = useState('');
  async function submit(event: FormEvent) {
    event.preventDefault(); setError('');
    const assignment = assignments.find((row) => text(row.id) === assignmentId);
    const payload: Row = { starts_at: new Date(startsAt).toISOString(), ends_at: new Date(endsAt).toISOString(), status: 'open' };
    if (role === 'Staff' && assignment) { payload.subject_id = assignment.subject_id; payload.section_id = assignment.section_id; }
    else { payload.subject_id = subjectId; payload.section_id = sectionId; payload.staff_id = staffId; }
    try { await api.post('/attendance/sessions', payload); onSaved('Open class session created in the managed database.'); }
    catch (requestError) { setError(toApiFailure(requestError).message); }
  }
  const ready = role === 'Staff' ? assignments.length > 0 : subjects.length > 0 && sections.length > 0 && staff.length > 0;
  return <LiveSection title="Create an open class session"><form className="live-inline-form" onSubmit={(event) => void submit(event)}>
    {role === 'Staff' ? <label>Assigned subject / section<select value={assignmentId} onChange={(event) => setAssignmentId(event.target.value)} required><option value="">Choose assignment</option>{assignments.map((row) => <option key={text(row.id)} value={text(row.id)}>{text(row.subject_code)} · {text(row.subject)} · {text(row.section)}</option>)}</select></label> : <><label>Subject<select value={subjectId} onChange={(event) => setSubjectId(event.target.value)} required><option value="">Choose subject</option>{subjects.map((row) => <option key={text(row.id)} value={text(row.id)}>{text(row.code)} · {text(row.name)}</option>)}</select></label><label>Section<select value={sectionId} onChange={(event) => setSectionId(event.target.value)} required><option value="">Choose section</option>{sections.map((row) => <option key={text(row.id)} value={text(row.id)}>{text(row.code)} · Year {text(row.academic_year)}</option>)}</select></label><label>Instructor<select value={staffId} onChange={(event) => setStaffId(event.target.value)} required><option value="">Choose Staff</option>{staff.map((row) => <option key={text(row.id)} value={text(row.id)}>{text(row.name)} · {text(row.staff_number)}</option>)}</select></label></>}
    <label>Start time<input type="datetime-local" value={startsAt} onChange={(event) => setStartsAt(event.target.value)} required /></label><label>End time<input type="datetime-local" value={endsAt} onChange={(event) => setEndsAt(event.target.value)} required /></label><button className="button button-primary" disabled={!ready}>Create session</button>
  </form>{!ready && <p className="live-empty">Create a matching subject, section, Staff profile and assignment before opening a session.</p>}{error && <p className="live-error-text">{error}</p>}</LiveSection>;
}

function AdminOverview({ summary, report, low, predictions, corrections, onReviewed }: { summary: Row; report: Row; low: Row[]; predictions: Row[]; corrections: Row[]; onReviewed: (message: string) => void }) {
  return <>
    <MetricCards metrics={[{ label: 'Students', value: text(summary.students) }, { label: 'Staff', value: text(summary.staff) }, { label: 'Attendance records', value: text(summary.attendance_records) }, { label: 'Devices', value: text(summary.devices) }, { label: 'Pending corrections', value: text(summary.pending_corrections) }, { label: 'Saved predictions', value: text(summary.prediction_records) }]} />
    <LiveSection title="Department attendance"><RecordTable rows={list(report.department_breakdown)} kind="department_breakdown" /></LiveSection>
    <LiveSection title="Year-wise attendance"><RecordTable rows={list(report.year_breakdown)} kind="year_breakdown" /></LiveSection>
    <LiveSection title="Subject analytics"><RecordTable rows={list(report.subject_analytics)} kind="subject_analytics" /></LiveSection>
    <LiveSection title="Low-attendance risk (<75%)"><RecordTable rows={low} kind="lowAttendance" /></LiveSection>
    <LiveSection title="Prediction analytics"><RecordTable rows={predictions} kind="predictions" /></LiveSection>
    <CorrectionReview rows={corrections} onReviewed={onReviewed} />
  </>;
}

function StaffOverview({ summary, assignments, sessions }: { summary: Row; assignments: Row[]; sessions: Row[] }) {
  return <>
    <MetricCards metrics={[{ label: 'Attendance records', value: text(summary.total_records) }, { label: 'Assigned classes', value: String(assignments.length) }, { label: 'Sessions in scope', value: String(sessions.length) }, { label: 'Attendance percentage', value: percent(summary.attendance_percentage) }]} />
    <LiveSection title="Assigned subjects and sections"><RecordTable rows={assignments} kind="assignments" /></LiveSection>
    <LiveSection title="Recent class sessions"><RecordTable rows={sessions} kind="sessions" /></LiveSection>
  </>;
}

function StudentOverview({ profile, attendance, predictions, notifications, subjectSummary }: { profile: Row; attendance: Row[]; predictions: Row[]; notifications: Row[]; subjectSummary: Row }) {
  const present = attendance.filter((row) => row.status === 'Present' || row.status === 'Late').length;
  const overall = obj(subjectSummary.overall);
  const held = Number(overall.classes_held ?? attendance.length);
  const attended = Number(overall.classes_attended ?? present);
  const percentage = typeof overall.attendance_percentage === 'number' ? percent(overall.attendance_percentage) : attendance.length ? `${(present * 100 / attendance.length).toFixed(1)}%` : '—';
  return <>
    <div className="live-student-profile"><div><span>Student</span><strong>{text(profile.name)}</strong></div><div><span>Roll number</span><strong>{text(profile.roll_number)}</strong></div><div><span>Department / year</span><strong>{text(profile.department)} · {text(profile.academic_year)}</strong></div><div><span>Section</span><strong>{text(profile.section)}</strong></div></div>
    <MetricCards metrics={[{ label: 'Overall attendance', value: percentage }, { label: 'Sessions attended', value: `${attended} / ${held}` }, { label: 'Stored predictions', value: String(predictions.length) }, { label: 'Notifications', value: String(notifications.length) }]} />
    <LiveSection title="Subject-wise attendance"><RecordTable rows={list(subjectSummary.subjects)} kind="studentSubjectAttendance" empty="No completed class sessions are recorded for your section yet." /></LiveSection>
    <LiveSection title="Your latest attendance"><RecordTable rows={attendance.slice(0, 20)} kind="attendance" /></LiveSection>
    <LiveSection title="Your AI attendance predictions"><RecordTable rows={predictions} kind="predictions" empty="No trained-model prediction is stored for your account yet." /></LiveSection>
    <LiveSection title="Your notifications"><RecordTable rows={notifications} kind="notifications" /></LiveSection>
  </>;
}

function AttendanceMarkForm({ sessions, students, onSaved }: { sessions: Row[]; students: Row[]; onSaved: (message: string) => void }) {
  const [sessionId, setSessionId] = useState('');
  const [studentId, setStudentId] = useState('');
  const [status, setStatus] = useState('Present');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  async function submit(event: FormEvent) {
    event.preventDefault(); setBusy(true); setError('');
    try { await api.post('/attendance', { session_id: sessionId, student_id: studentId, status }); onSaved('Attendance saved to Supabase PostgreSQL database.'); }
    catch (requestError) { setError(toApiFailure(requestError).message); }
    finally { setBusy(false); }
  }
  return <LiveSection title="Mark attendance"><form className="live-inline-form" onSubmit={submit}><label>Authorized session<select value={sessionId} onChange={(event) => setSessionId(event.target.value)} required><option value="">Choose a session</option>{sessions.map((row) => <option key={text(row.id)} value={text(row.id)}>{text(row.subject)} · {text(row.section)} · {text(row.starts_at)}</option>)}</select></label><label>Student<select value={studentId} onChange={(event) => setStudentId(event.target.value)} required><option value="">Choose a student</option>{students.map((row) => <option key={text(row.id)} value={text(row.id)}>{text(row.name)} · {text(row.roll_number)}</option>)}</select></label><label>Status<select value={status} onChange={(event) => setStatus(event.target.value)}><option>Present</option><option>Absent</option><option>Late</option></select></label><button className="button button-primary" disabled={busy || !sessions.length || !students.length}>{busy ? 'Saving…' : 'Save attendance'}</button></form>{error && <p className="live-error-text">{error}</p>}</LiveSection>;
}

function CorrectionForm({ records, onSaved }: { records: Row[]; onSaved: (message: string) => void }) {
  const [recordId, setRecordId] = useState(''); const [requestedStatus, setRequestedStatus] = useState('Present'); const [reason, setReason] = useState(''); const [error, setError] = useState('');
  async function submit(event: FormEvent) { event.preventDefault(); setError(''); try { await api.post(`/attendance/${recordId}/corrections`, { requested_status: requestedStatus, reason }); onSaved('Attendance correction submitted for Admin review.'); } catch (requestError) { setError(toApiFailure(requestError).message); } }
  return <LiveSection title="Request an attendance correction"><form className="live-inline-form" onSubmit={(event) => void submit(event)}><label>Attendance record<select value={recordId} onChange={(event) => setRecordId(event.target.value)} required><option value="">Select a record</option>{records.map((row) => <option key={text(row.id)} value={text(row.id)}>{text(row.student)} · {text(row.subject)} · {text(row.date)}</option>)}</select></label><label>Requested status<select value={requestedStatus} onChange={(event) => setRequestedStatus(event.target.value)}><option>Present</option><option>Absent</option><option>Late</option></select></label><label>Reason<input value={reason} onChange={(event) => setReason(event.target.value)} minLength={8} maxLength={500} required /></label><button className="button button-secondary">Submit correction</button></form>{error && <p className="live-error-text">{error}</p>}</LiveSection>;
}

function DeviceEnrollmentForm({ classrooms, onIssued }: { classrooms: Row[]; onIssued: (message: string) => void }) {
  const [classroomId, setClassroomId] = useState(''); const [token, setToken] = useState(''); const [error, setError] = useState('');
  async function submit(event: FormEvent) { event.preventDefault(); setError(''); setToken(''); try { const response = await api.post<Envelope<{ token: string; expires_at: string }>>('/admin/device-enrollment-tokens', { classroom_id: classroomId, expires_in_minutes: 10 }); setToken(response.data.data.token); onIssued('Enrollment token was created once. Copy it now; only its hash is retained by the server.'); } catch (requestError) { setError(toApiFailure(requestError).message); } }
  return <LiveSection title="Enroll a Raspberry Pi"><form className="live-inline-form" onSubmit={(event) => void submit(event)}><label>Map to classroom<select value={classroomId} onChange={(event) => setClassroomId(event.target.value)} required><option value="">Choose classroom</option>{classrooms.map((row) => <option key={text(row.id)} value={text(row.id)}>{text(row.building)} · {text(row.room_code)}</option>)}</select></label><button className="button button-primary" disabled={!classrooms.length}>Create single-use token</button></form>{token && <div className="live-token-box"><strong>Copy now — shown once</strong><code>{token}</code><button className="button button-secondary" onClick={() => void navigator.clipboard.writeText(token)}>Copy token</button><button className="text-button" onClick={() => setToken('')}>Hide token</button></div>}{error && <p className="live-error-text">{error}</p>}</LiveSection>;
}

function DeviceTable({ rows, classrooms, onUpdated }: { rows: Row[]; classrooms: Row[]; onUpdated: (message: string) => void }) {
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const [mapping, setMapping] = useState<Record<string, string>>({});
  const [credential, setCredential] = useState('');

  async function update(device: Row, changes: Row, message: string) {
    setError(''); setBusy(true);
    try { await api.patch(`/admin/devices/${text(device.id)}`, changes); onUpdated(message); }
    catch (requestError) { setError(toApiFailure(requestError).message); }
    finally { setBusy(false); }
  }

  async function activate(device: Row) {
    setError(''); setBusy(true);
    try {
      const classroomId = mapping[text(device.id)] ?? (device.classroom_id ? String(device.classroom_id) : '');
      await api.post(`/admin/devices/${text(device.id)}/activate`, classroomId ? { classroom_id: classroomId } : {});
      onUpdated('Device activated and classroom mapping saved.');
    } catch (requestError) { setError(toApiFailure(requestError).message); }
    finally { setBusy(false); }
  }

  async function rotate(device: Row) {
    setError(''); setCredential(''); setBusy(true);
    try {
      const response = await api.post<Envelope<{ credential: string }>>(`/admin/devices/${text(device.id)}/rotate-credential`, {});
      setCredential(response.data.data.credential);
      onUpdated('Replacement credential issued once. Install it on the Raspberry Pi and store it securely.');
    } catch (requestError) { setError(toApiFailure(requestError).message); }
    finally { setBusy(false); }
  }

  return <>
    <div className="live-honesty-note"><ShieldCheck size={15} /><span>Credential rotation immediately revokes the previous credential. Copy the replacement now and install it on the device; the server never displays it again.</span></div>
    {error && <p className="live-error-text">{error}</p>}
    {rows.length ? <div className="live-table-scroll"><table className="live-table">
      <thead><tr>{columns.devices.map((column) => <th key={column.key}>{column.label}</th>)}<th>Classroom mapping</th><th>Admin controls</th></tr></thead>
      <tbody>{rows.map((row) => {
        const id = text(row.id);
        const selectedClassroom = mapping[id] ?? (row.classroom_id ? String(row.classroom_id) : '');
        return <tr key={id}>
          <td>{text(row.device_id)}</td><td>{text(row.classroom)}</td><td>{text(row.status)}</td>
          <td><span className={`live-connection ${row.connection_status === 'online' ? 'is-online' : 'is-offline'}`}>{row.connection_status === 'online' ? <Wifi size={13} /> : <WifiOff size={13} />}{text(row.connection_status)}</span></td>
          <td>{text(row.firmware_version)}</td><td>{text(row.last_heartbeat_at)}</td>
          <td><select aria-label={`Classroom for ${text(row.device_id)}`} value={selectedClassroom} onChange={(event) => setMapping((current) => ({ ...current, [id]: event.target.value }))}><option value="">No classroom</option>{classrooms.map((classroom) => <option key={text(classroom.id)} value={text(classroom.id)}>{text(classroom.building)} · {text(classroom.room_code)}</option>)}</select></td>
          <td><div className="live-device-actions">
            <button className="text-button" disabled={busy} onClick={() => void update(row, { classroom_id: selectedClassroom || null }, 'Classroom mapping updated.')}>Save mapping</button>
            {row.status !== 'active' && <button className="text-button" disabled={busy} onClick={() => void activate(row)}>{row.status === 'revoked' ? 'Reactivate' : 'Activate'}</button>}
            {row.status !== 'revoked' && <button className="text-button" disabled={busy} onClick={() => void update(row, { status: 'revoked' }, 'Device revoked; its credentials can no longer authenticate.')}>Revoke</button>}
            <button className="text-button" disabled={busy} onClick={() => void rotate(row)}>Rotate credential</button>
          </div></td>
        </tr>;
      })}</tbody>
    </table></div> : <div className="live-empty">No devices have registered in the managed database.</div>}
    {credential && <div className="live-token-box"><strong>Replacement device credential — copy now, shown once</strong><code>{credential}</code><button className="button button-secondary" onClick={() => void navigator.clipboard.writeText(credential)}>Copy credential</button><button className="text-button" onClick={() => setCredential('')}>Hide credential</button></div>}
  </>;
}

function StudentProvisionForm({ users, departments, sections, onSaved }: { users: Row[]; departments: Row[]; sections: Row[]; onSaved: (message: string) => void }) {
  const [userId, setUserId] = useState(''); const [departmentId, setDepartmentId] = useState(''); const [sectionId, setSectionId] = useState(''); const [rollNumber, setRollNumber] = useState(''); const [academicYear, setAcademicYear] = useState('1'); const [error, setError] = useState('');
  async function submit(event: FormEvent) { event.preventDefault(); setError(''); try { await api.post('/admin/students', { user_id: userId, department_id: departmentId, section_id: sectionId, roll_number: rollNumber, academic_year: Number(academicYear) }); onSaved('Student profile provisioned successfully.'); setRollNumber(''); } catch (requestError) { setError(toApiFailure(requestError).message); } }
  return <LiveSection title="Provision a student after their first sign-in"><form className="live-inline-form" onSubmit={(event) => void submit(event)}><label>Pending account<select value={userId} onChange={(event) => setUserId(event.target.value)} required><option value="">Select account</option>{users.map((row) => <option key={text(row.id)} value={text(row.id)}>{text(row.display_name)} · {text(row.email)}</option>)}</select></label><label>Department<select value={departmentId} onChange={(event) => setDepartmentId(event.target.value)} required><option value="">Select department</option>{departments.map((row) => <option key={text(row.id)} value={text(row.id)}>{text(row.name)}</option>)}</select></label><label>Class section<select value={sectionId} onChange={(event) => setSectionId(event.target.value)} required><option value="">Select section</option>{sections.filter((row) => !departmentId || row.department_id === departmentId).map((row) => <option key={text(row.id)} value={text(row.id)}>{text(row.code)} · Year {text(row.academic_year)}</option>)}</select></label><label>Roll number<input value={rollNumber} onChange={(event) => setRollNumber(event.target.value)} maxLength={48} required /></label><label>Academic year<input type="number" min={1} max={12} value={academicYear} onChange={(event) => setAcademicYear(event.target.value)} required /></label><button className="button button-primary">Create student profile</button></form>{error && <p className="live-error-text">{error}</p>}</LiveSection>;
}

function StaffProvisionForm({ users, departments, onSaved }: { users: Row[]; departments: Row[]; onSaved: (message: string) => void }) {
  const [userId, setUserId] = useState(''); const [departmentId, setDepartmentId] = useState(''); const [staffNumber, setStaffNumber] = useState(''); const [error, setError] = useState('');
  async function submit(event: FormEvent) { event.preventDefault(); setError(''); try { await api.post('/admin/staff', { user_id: userId, department_id: departmentId, staff_number: staffNumber }); onSaved('Staff profile provisioned.'); setStaffNumber(''); } catch (requestError) { setError(toApiFailure(requestError).message); } }
  return <LiveSection title="Provision a staff profile"><form className="live-inline-form" onSubmit={(event) => void submit(event)}><label>Pending account<select value={userId} onChange={(event) => setUserId(event.target.value)} required><option value="">Select account</option>{users.map((row) => <option key={text(row.id)} value={text(row.id)}>{text(row.display_name)} · {text(row.email)}</option>)}</select></label><label>Department<select value={departmentId} onChange={(event) => setDepartmentId(event.target.value)} required><option value="">Select department</option>{departments.map((row) => <option key={text(row.id)} value={text(row.id)}>{text(row.name)}</option>)}</select></label><label>Staff number<input value={staffNumber} onChange={(event) => setStaffNumber(event.target.value)} maxLength={48} required /></label><button className="button button-primary">Create staff profile</button></form>{error && <p className="live-error-text">{error}</p>}</LiveSection>;
}

function SubjectCreateForm({ departments, onSaved }: { departments: Row[]; onSaved: (message: string) => void }) {
  const [departmentId, setDepartmentId] = useState(''); const [code, setCode] = useState(''); const [name, setName] = useState(''); const [credits, setCredits] = useState('0'); const [error, setError] = useState('');
  async function submit(event: FormEvent) { event.preventDefault(); setError(''); try { await api.post('/admin/subjects', { department_id: departmentId, code, name, credits: Number(credits) }); setCode(''); setName(''); onSaved('Subject created and audit logged.'); } catch (requestError) { setError(toApiFailure(requestError).message); } }
  return <LiveSection title="Create a subject"><form className="live-inline-form" onSubmit={(event) => void submit(event)}><label>Department<select value={departmentId} onChange={(event) => setDepartmentId(event.target.value)} required><option value="">Select department</option>{departments.map((row) => <option key={text(row.id)} value={text(row.id)}>{text(row.name)}</option>)}</select></label><label>Subject code<input value={code} onChange={(event) => setCode(event.target.value)} maxLength={32} required /></label><label>Subject name<input value={name} onChange={(event) => setName(event.target.value)} maxLength={160} required /></label><label>Credits<input type="number" min={0} max={40} value={credits} onChange={(event) => setCredits(event.target.value)} required /></label><button className="button button-secondary">Add subject</button></form>{error && <p className="live-error-text">{error}</p>}</LiveSection>;
}

function AssignmentForm({ staff, subjects, sections, onSaved }: { staff: Row[]; subjects: Row[]; sections: Row[]; onSaved: (message: string) => void }) {
  const [staffId, setStaffId] = useState(''); const [subjectId, setSubjectId] = useState(''); const [sectionId, setSectionId] = useState(''); const [error, setError] = useState('');
  async function submit(event: FormEvent) { event.preventDefault(); setError(''); try { await api.post('/admin/staff-subject-assignments', { staff_id: staffId, subject_id: subjectId, section_id: sectionId }); onSaved('Staff assignment created and audit logged.'); } catch (requestError) { setError(toApiFailure(requestError).message); } }
  return <LiveSection title="Assign a subject and section"><form className="live-inline-form" onSubmit={(event) => void submit(event)}><label>Staff<select value={staffId} onChange={(event) => setStaffId(event.target.value)} required><option value="">Select staff</option>{staff.map((row) => <option key={text(row.id)} value={text(row.id)}>{text(row.name)} · {text(row.staff_number)}</option>)}</select></label><label>Subject<select value={subjectId} onChange={(event) => setSubjectId(event.target.value)} required><option value="">Select subject</option>{subjects.map((row) => <option key={text(row.id)} value={text(row.id)}>{text(row.code)} · {text(row.name)}</option>)}</select></label><label>Section<select value={sectionId} onChange={(event) => setSectionId(event.target.value)} required><option value="">Select section</option>{sections.map((row) => <option key={text(row.id)} value={text(row.id)}>{text(row.code)} · {text(row.department)}</option>)}</select></label><button className="button button-secondary">Create assignment</button></form>{error && <p className="live-error-text">{error}</p>}</LiveSection>;
}

function AcademicSetupForm({ departments, classrooms, onSaved }: { departments: Row[]; classrooms: Row[]; onSaved: (message: string) => void }) {
  const [departmentCode, setDepartmentCode] = useState(''); const [departmentName, setDepartmentName] = useState(''); const [building, setBuilding] = useState(''); const [roomCode, setRoomCode] = useState(''); const [departmentId, setDepartmentId] = useState(''); const [classroomId, setClassroomId] = useState(''); const [sectionCode, setSectionCode] = useState(''); const [year, setYear] = useState('1'); const [term, setTerm] = useState('2026-Fall'); const [error, setError] = useState('');
  async function createDepartment(event: FormEvent) { event.preventDefault(); setError(''); try { await api.post('/admin/departments', { code: departmentCode, name: departmentName }); setDepartmentCode(''); setDepartmentName(''); onSaved('Department added.'); } catch (requestError) { setError(toApiFailure(requestError).message); } }
  async function createRoom(event: FormEvent) { event.preventDefault(); setError(''); try { await api.post('/admin/classrooms', { building, room_code: roomCode }); setBuilding(''); setRoomCode(''); onSaved('Classroom added.'); } catch (requestError) { setError(toApiFailure(requestError).message); } }
  async function createSection(event: FormEvent) { event.preventDefault(); setError(''); try { await api.post('/admin/sections', { department_id: departmentId, classroom_id: classroomId || null, code: sectionCode, academic_year: Number(year), term }); setSectionCode(''); onSaved('Class section added.'); } catch (requestError) { setError(toApiFailure(requestError).message); } }
  return <LiveSection title="Academic structure"><div className="live-form-grid"><form className="live-inline-form" onSubmit={(event) => void createDepartment(event)}><strong>Department</strong><label>Code<input value={departmentCode} onChange={(event) => setDepartmentCode(event.target.value)} minLength={2} maxLength={24} required /></label><label>Name<input value={departmentName} onChange={(event) => setDepartmentName(event.target.value)} minLength={2} maxLength={120} required /></label><button className="button button-secondary">Add department</button></form><form className="live-inline-form" onSubmit={(event) => void createRoom(event)}><strong>Classroom</strong><label>Building<input value={building} onChange={(event) => setBuilding(event.target.value)} required /></label><label>Room code<input value={roomCode} onChange={(event) => setRoomCode(event.target.value)} required /></label><button className="button button-secondary">Add classroom</button></form><form className="live-inline-form" onSubmit={(event) => void createSection(event)}><strong>Class section</strong><label>Department<select value={departmentId} onChange={(event) => setDepartmentId(event.target.value)} required><option value="">Select department</option>{departments.map((row) => <option key={text(row.id)} value={text(row.id)}>{text(row.name)}</option>)}</select></label><label>Classroom<select value={classroomId} onChange={(event) => setClassroomId(event.target.value)}><option value="">No classroom assigned</option>{classrooms.map((row) => <option key={text(row.id)} value={text(row.id)}>{text(row.room_code)}</option>)}</select></label><label>Code<input value={sectionCode} onChange={(event) => setSectionCode(event.target.value)} required /></label><label>Year<input type="number" min={1} max={12} value={year} onChange={(event) => setYear(event.target.value)} /></label><label>Term<input value={term} onChange={(event) => setTerm(event.target.value)} required /></label><button className="button button-primary">Add section</button></form></div>{error && <p className="live-error-text">{error}</p>}<RecordTable rows={departments} kind="departments" /><RecordTable rows={classrooms} kind="classrooms" /></LiveSection>;
}

function SystemStatusCard({ status }: { status: Row }) {
  return <div className="live-status-card"><span className="live-status-indicator" /><div><strong>API status: {text(status.service)}</strong><span>Database provider: {text(status.database_provider)} · Connected configuration: {text(status.database_configured)} · Authentication configured: {text(status.authentication_configured)} · First-Admin bootstrap configured: {text(status.first_admin_bootstrap_configured)} · Demo data is live: {text(status.demo_data_is_live)}</span></div></div>;
}

export function LiveWorkspace() {
  const { user } = useAuth();
  const location = useLocation();
  const [data, setData] = useState<Bundle>({});
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [reloadKey, setReloadKey] = useState(0);
  const role = user?.role;
  const path = location.pathname;
  const query = new URLSearchParams(location.search).get('search') ?? '';
  const reload = useCallback(() => setReloadKey((value) => value + 1), []);

  useEffect(() => {
    if (!role) return;
    let active = true;
    setLoading(true); setError(null);
    const requests: Array<[string, Promise<unknown>]> = [];
    const add = (key: string, url: string) => requests.push([key, requestData(url)]);
    if (path === '/') {
      if (role === 'Admin') { add('adminSummary', '/admin/summary'); add('reportSummary', '/reports/summary'); add('lowAttendance', '/reports/low-attendance?threshold=75'); add('predictions', '/predictions'); add('corrections', '/admin/attendance-corrections'); }
      if (role === 'Staff') { add('reportSummary', '/reports/summary'); add('assignments', '/staff/me/assignments'); add('sessions', '/attendance/sessions'); }
      if (role === 'Student') { add('studentMe', '/students/me'); add('studentSummary', '/students/me/attendance-summary'); add('attendance', '/attendance'); add('predictions', '/predictions/me'); add('notifications', '/notifications'); }
    } else if (path === '/attendance') {
      add('attendance', '/attendance'); add('sessions', '/attendance/sessions');
      if (role !== 'Student') add('students', '/students');
      if (role === 'Admin') { add('subjects', '/subjects'); add('sections', '/admin/sections'); add('staff', '/staff'); add('corrections', '/admin/attendance-corrections'); }
      if (role === 'Staff') add('assignments', '/staff/me/assignments');
    } else if (path === '/predictions') { add('predictions', '/predictions'); if (role === 'Admin') add('models', '/predictions/models'); }
    else if (path === '/reports') { add('reportSummary', '/reports/summary'); add('lowAttendance', '/reports/low-attendance?threshold=75'); }
    else if (path === '/devices') { add('devices', '/admin/devices'); add('classrooms', '/admin/classrooms'); }
    else if (path === '/students') {
      add('students', `/students${query ? `?q=${encodeURIComponent(query)}` : ''}`);
      if (role === 'Admin') { add('pendingUsers', '/admin/users?status=pending'); add('departments', '/admin/departments'); add('sections', '/admin/sections'); }
    } else if (path === '/staff') {
      add('staff', '/staff');
      if (role === 'Staff') add('assignments', '/staff/me/assignments');
      if (role === 'Admin') { add('pendingUsers', '/admin/users?status=pending'); add('departments', '/admin/departments'); add('sections', '/admin/sections'); add('subjects', '/subjects'); }
    } else if (path === '/settings') {
      add('systemStatus', '/system/status');
      if (role === 'Admin') { add('pendingUsers', '/admin/users?status=pending'); add('departments', '/admin/departments'); add('classrooms', '/admin/classrooms'); add('sections', '/admin/sections'); }
    }
    Promise.all(requests.map(async ([key, promise]) => [key, await promise] as const))
      .then((entries) => { if (active) setData(Object.fromEntries(entries)); })
      .catch((requestError) => { if (active) setError(toApiFailure(requestError).message); })
      .finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, [role, path, query, reloadKey]);

  const title = useMemo(() => path === '/' ? 'Overview' : path, [path]);
  if (loading) return <section className="live-workspace"><div className="live-loading"><span className="loading-indicator" /><strong>Loading {title} from the authenticated API…</strong><span>No demo records are used as a fallback.</span></div></section>;
  if (error) return <section className="live-workspace"><div className="live-error-panel"><p className="eyebrow">LIVE API REQUEST FAILED</p><h2>Live records could not be loaded</h2><p>{error}</p><p>Sample data is intentionally hidden for signed-in accounts.</p><button className="button button-primary" onClick={reload}><RefreshCw size={15} /> Retry API request</button></div></section>;
  if (!role) return null;
  const permittedPaths: Record<PreviewRole, string[]> = { Admin: ['/', '/attendance', '/predictions', '/reports', '/devices', '/students', '/staff', '/settings'], Staff: ['/', '/attendance', '/predictions', '/reports', '/students', '/staff'], Student: ['/', '/attendance', '/predictions'] };
  if (!permittedPaths[role].includes(path)) return <section className="live-workspace"><div className="live-error-panel"><p className="eyebrow">ROLE-RESTRICTED ROUTE</p><h2>This page is not available for your role</h2><p>The Flask API and navigation enforce the authenticated role.</p></div></section>;
  return <LivePage role={role} path={path} data={data} reload={reload} />;
}
