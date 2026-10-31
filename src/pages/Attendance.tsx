import { useMemo, useState } from 'react';
import { CalendarDays, Download, Filter, Search } from 'lucide-react';
import { useOutletContext } from 'react-router-dom';
import { StatusPill } from '../components/Visuals';
import { demoAttendance } from '../lib/demoData';
import type { AttendanceRow, AttendanceStatus, OutletContextValue } from '../types';

const pageSize = 5;

function downloadCsv(filename: string, rows: string[][]) {
  const csv = rows.map((row) => row.map((cell) => `"${cell.replaceAll('"', '""')}"`).join(',')).join('\n');
  const link = document.createElement('a');
  link.href = URL.createObjectURL(new Blob([csv], { type: 'text/csv;charset=utf-8' }));
  link.download = filename;
  link.click();
  URL.revokeObjectURL(link.href);
}

export function AttendancePage() {
  const { role } = useOutletContext<OutletContextValue>();
  const [rows, setRows] = useState<AttendanceRow[]>(demoAttendance);
  const [query, setQuery] = useState('');
  const [status, setStatus] = useState('All statuses');
  const [subject, setSubject] = useState('All subjects');
  const [page, setPage] = useState(1);
  const [toast, setToast] = useState('');
  const studentOnly = role === 'Student';
  const visibleRows = useMemo(() => rows.filter((row) => {
    const matchQuery = `${row.student} ${row.rollNo} ${row.subject}`.toLowerCase().includes(query.toLowerCase());
    return matchQuery && (status === 'All statuses' || row.status === status) && (subject === 'All subjects' || row.subject === subject) && (!studentOnly || row.rollNo === 'STU-24-018');
  }), [rows, query, status, subject, studentOnly]);
  const pageCount = Math.max(1, Math.ceil(visibleRows.length / pageSize));
  const pageRows = visibleRows.slice((page - 1) * pageSize, page * pageSize);

  function showToast(message: string) {
    setToast(message);
    window.setTimeout(() => setToast(''), 3200);
  }

  function updateStatus(id: string, value: AttendanceStatus) {
    setRows((current) => current.map((row) => row.id === id ? { ...row, status: value } : row));
    showToast('Demo change applied in this browser only. No attendance record was saved.');
  }

  function exportRows() {
    downloadCsv('smartattend-demo-attendance.csv', [['Record ID', 'Student', 'Roll number', 'Subject', 'Section', 'Date', 'Status'], ...visibleRows.map((row) => [row.id, row.student, row.rollNo, row.subject, row.section, row.date, row.status])]);
    showToast('A demo CSV was downloaded. These sample rows are not college records.');
  }

  return <>
    <div className="page-heading">
      <div><p className="eyebrow">ACADEMIC RECORDS · SAMPLE DATA</p><h1>{studentOnly ? 'My attendance history' : 'Attendance workspace'}</h1><p className="page-subtitle">{studentOnly ? 'A fictional student history for layout demonstration.' : 'Review, filter and update attendance in this local-only UI demonstration.'}</p></div>
      {!studentOnly && <button className="button button-primary" onClick={() => showToast('Demo marking flow: choose a sample record to change its local status.')}><CalendarDays size={15} /> Mark attendance</button>}
    </div>
    <div className="report-card-grid">
      <div className="report-card"><span>Records in preview</span><strong>{studentOnly ? visibleRows.length : '42'}</strong><small>Fictional data only</small></div>
      <div className="report-card"><span>Present · sample</span><strong>{visibleRows.filter((row) => row.status === 'Present').length}</strong><small>Filtered rows in this view</small></div>
      <div className="report-card"><span>Data connection</span><strong style={{ fontSize: 16 }}>Not connected</strong><small>No attendance API or database is active</small></div>
    </div>
    <div className="page-toolbar">
      <div className="toolbar-left">
        <label className="search-box attendance-search"><Search size={15} /><input value={query} onChange={(event) => { setQuery(event.target.value); setPage(1); }} placeholder={studentOnly ? 'Search my history…' : 'Search name, roll no. or subject…'} aria-label="Search attendance" /></label>
        <select className="filter-control" value={subject} onChange={(event) => { setSubject(event.target.value); setPage(1); }} aria-label="Filter by subject"><option>All subjects</option><option>Data Structures</option><option>Database Systems</option><option>Applied Statistics</option></select>
        <select className="filter-control" value={status} onChange={(event) => { setStatus(event.target.value); setPage(1); }} aria-label="Filter by status"><option>All statuses</option><option>Present</option><option>Absent</option><option>Late</option></select>
      </div>
      <div className="toolbar-right"><button className="button button-secondary" onClick={exportRows}><Download size={14} /> Export sample CSV</button></div>
    </div>
    <section className="panel wide-panel">
      <div className="panel-heading"><div><h2>Attendance records</h2><p>All records below are fictional UI fixtures · <span className="table-count">{visibleRows.length} rows match</span></p></div><button className="icon-menu" aria-label="Filter options"><Filter size={15} /></button></div>
      <div className="table-scroll"><table className="data-table"><thead><tr><th>STUDENT</th><th>SUBJECT / SECTION</th><th>DATE</th><th>STATUS</th>{!studentOnly && <th>LOCAL DEMO ACTION</th>}</tr></thead><tbody>
        {pageRows.map((row) => <tr key={row.id}><td><div className="person-cell"><span className="avatar avatar-sm">{row.student.split(' ').map((part) => part[0]).join('')}</span><span><strong>{row.student}</strong><small>{row.rollNo}</small></span></div></td><td>{row.subject}<small className="table-subline">{row.section}</small></td><td>{row.date}</td><td><StatusPill status={row.status} /></td>{!studentOnly && <td><select className="table-select-control" aria-label={`Change sample attendance status for ${row.student}`} value={row.status} onChange={(event) => updateStatus(row.id, event.target.value as AttendanceStatus)}><option>Present</option><option>Absent</option><option>Late</option></select></td>}</tr>)}
        {pageRows.length === 0 && <tr><td colSpan={studentOnly ? 4 : 5} className="empty-table-cell">No sample records match these filters.</td></tr>}
      </tbody></table></div>
      <div className="pagination"><span>Showing {visibleRows.length ? (page - 1) * pageSize + 1 : 0}–{Math.min(page * pageSize, visibleRows.length)} of {visibleRows.length} fictional rows</span><div className="pagination-actions"><button aria-label="Previous page" disabled={page <= 1} onClick={() => setPage((current) => current - 1)}>‹</button>{Array.from({ length: pageCount }, (_, index) => index + 1).map((pageNumber) => <button key={pageNumber} className={pageNumber === page ? 'active' : ''} onClick={() => setPage(pageNumber)}>{pageNumber}</button>)}<button aria-label="Next page" disabled={page >= pageCount} onClick={() => setPage((current) => current + 1)}>›</button></div></div>
    </section>
    {toast && <div className="toast-message" role="status"><strong>Demo-only interaction</strong>{toast}</div>}
  </>;
}
