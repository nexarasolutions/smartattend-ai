import { useMemo, useState } from 'react';
import { Download, GraduationCap, Search, UsersRound } from 'lucide-react';
import { useSearchParams } from 'react-router-dom';
import { demoStudents, subjectAttendance } from '../lib/demoData';

const demoStaff = [
  { name: 'Dr. Ananya Sharma', id: 'STF-018', department: 'Computer Science', assignment: 'Data Structures · CS-B', students: 36, email: 'ananya.sharma@example.edu' },
  { name: 'Prof. Vikram Sen', id: 'STF-024', department: 'Information Systems', assignment: 'Database Systems · IS-A', students: 28, email: 'vikram.sen@example.edu' },
  { name: 'Dr. Leena Menon', id: 'STF-031', department: 'Data Science', assignment: 'Applied Statistics · DS-A', students: 31, email: 'leena.menon@example.edu' },
  { name: 'Prof. Arjun Bose', id: 'STF-012', department: 'Computer Science', assignment: 'Computer Networks · CS-A', students: 34, email: 'arjun.bose@example.edu' },
];
const pageSize = 5;

function csvCell(value: string) { return `"${value.replaceAll('"', '""')}"`; }

export function PeoplePage({ kind }: { kind: 'students' | 'staff' }) {
  const [searchParams] = useSearchParams();
  const [query, setQuery] = useState(() => searchParams.get('search') ?? '');
  const [department, setDepartment] = useState('All departments');
  const [page, setPage] = useState(1);
  const students = kind === 'students';
  const source = students ? demoStudents : demoStaff;
  const filteredPeople = useMemo(() => source.filter((person) => {
    const identifier = 'rollNo' in person ? person.rollNo : person.id;
    const matchesQuery = `${person.name} ${identifier} ${person.department}`.toLowerCase().includes(query.toLowerCase());
    return matchesQuery && (department === 'All departments' || person.department === department);
  }), [source, query, department]);
  const pageCount = Math.max(1, Math.ceil(filteredPeople.length / pageSize));
  const pagePeople = filteredPeople.slice((page - 1) * pageSize, page * pageSize);

  function exportList() {
    const rows = students ? [['Name', 'Roll number', 'Department', 'Year', 'Section', 'Sample attendance'], ...demoStudents.map((student) => [student.name, student.rollNo, student.department, student.year, student.section, `${student.attendance}%`])] : [['Name', 'Staff ID', 'Department', 'Assignment', 'Sample students'], ...demoStaff.map((staff) => [staff.name, staff.id, staff.department, staff.assignment, `${staff.students}`])];
    const csv = rows.map((row) => row.map(csvCell).join(',')).join('\n');
    const anchor = document.createElement('a');
    anchor.href = URL.createObjectURL(new Blob([csv], { type: 'text/csv;charset=utf-8' }));
    anchor.download = `smartattend-demo-${kind}.csv`;
    anchor.click();
    URL.revokeObjectURL(anchor.href);
  }

  return <>
    <div className="page-heading"><div><p className="eyebrow">{students ? 'STUDENT ROSTER' : 'STAFF & SUBJECT ASSIGNMENTS'} · DEMONSTRATION</p><h1>{students ? 'Student records' : 'Staff and subjects'}</h1><p className="page-subtitle">{students ? 'Fictional sample student profiles for the dashboard prototype.' : 'Fictional staff and class assignments for the dashboard prototype.'}</p></div><button className="button button-secondary" onClick={exportList}><Download size={14} /> Export sample CSV</button></div>
    <div className="report-card-grid"><div className="report-card"><span>{students ? 'Sample student profiles' : 'Sample staff profiles'}</span><strong>{filteredPeople.length}</strong><small>Fictional list rows</small></div><div className="report-card"><span>Database connection</span><strong style={{ fontSize: 16 }}>Not connected</strong><small>No live directory source</small></div><div className="report-card"><span>{students ? 'Attendance linkage' : 'Assignment scope'}</span><strong style={{ fontSize: 16 }}>{students ? 'Demo only' : 'UI example'}</strong><small>Authorization not active</small></div></div>
    {!students && <section className="panel" style={{ marginBottom: 13 }}><div className="panel-heading" style={{ padding: 17 }}><div><h2>Subject assignment preview</h2><p>Assignment scoping must be enforced by the Flask API in Phase 2.</p></div><UsersRound size={16} color="#8a95a7" /></div><div className="role-card-list">{subjectAttendance.slice(0, 3).map((subject, index) => <article className="role-card" key={subject.subject}><span><GraduationCap size={17} /></span><h3>{subject.subject}</h3><p>{['CS-B · Year 2 · Example assignment', 'IS-A · Year 3 · Example assignment', 'DS-A · Year 1 · Example assignment'][index]}</p></article>)}</div></section>}
    <div className="page-toolbar"><div className="toolbar-left"><label className="search-box attendance-search"><Search size={15} /><input value={query} onChange={(event) => { setQuery(event.target.value); setPage(1); }} placeholder={students ? 'Search name, roll number or department…' : 'Search staff, ID or department…'} aria-label="Search directory" /></label><select className="filter-control" value={department} onChange={(event) => { setDepartment(event.target.value); setPage(1); }} aria-label="Filter department"><option>All departments</option><option>Computer Science</option><option>Information Systems</option><option>Data Science</option></select></div></div>
    <section className="panel wide-panel"><div className="panel-heading"><div><h2>{students ? 'Student directory' : 'Staff directory'}</h2><p>Fictional examples only · {filteredPeople.length} rows match</p></div></div><div className="table-scroll"><table className="data-table"><thead>{students ? <tr><th>STUDENT</th><th>DEPARTMENT / YEAR</th><th>SECTION</th><th>ATTENDANCE · SAMPLE</th><th>TREND · SAMPLE</th></tr> : <tr><th>STAFF MEMBER</th><th>DEPARTMENT</th><th>ASSIGNMENT</th><th>STUDENTS · SAMPLE</th><th>CONTACT · EXAMPLE</th></tr>}</thead><tbody>
      {students ? pagePeople.map((person) => { if (!('rollNo' in person)) return null; return <tr key={person.rollNo}><td><div className="person-cell"><span className="avatar avatar-sm">{person.name.split(' ').map((part) => part[0]).join('')}</span><span><strong>{person.name}</strong><small>{person.rollNo}</small></span></div></td><td>{person.department}<small className="table-subline">{person.year}</small></td><td>{person.section}</td><td><div className="progress-inline"><div className="progress-track"><i style={{ width: `${person.attendance}%`, backgroundColor: person.attendance < 75 ? '#c45e65' : '#3156c8' }} /></div><strong>{person.attendance}%</strong></div></td><td><span className={`trend-label ${person.trend.startsWith('−') ? 'trend-negative' : ''}`}>{person.trend} <small>sample</small></span></td></tr>; }) : pagePeople.map((person) => { if (!('id' in person)) return null; return <tr key={person.id}><td><div className="person-cell"><span className="avatar avatar-sm avatar-indigo">{person.name.split(' ').map((part) => part[0]).join('')}</span><span><strong>{person.name}</strong><small>{person.id}</small></span></div></td><td>{person.department}</td><td>{person.assignment}</td><td>{person.students}</td><td className="muted-cell">{person.email}</td></tr>; })}
      {pagePeople.length === 0 && <tr><td className="empty-table-cell" colSpan={5}>No sample directory rows match these filters.</td></tr>}
    </tbody></table></div><div className="pagination"><span>Showing {filteredPeople.length ? (page - 1) * pageSize + 1 : 0}–{Math.min(page * pageSize, filteredPeople.length)} of {filteredPeople.length} fictional rows</span><div className="pagination-actions"><button aria-label="Previous page" disabled={page <= 1} onClick={() => setPage((current) => current - 1)}>‹</button>{Array.from({ length: pageCount }, (_, index) => index + 1).map((pageNumber) => <button key={pageNumber} className={pageNumber === page ? 'active' : ''} onClick={() => setPage(pageNumber)}>{pageNumber}</button>)}<button aria-label="Next page" disabled={page >= pageCount} onClick={() => setPage((current) => current + 1)}>›</button></div></div><div className="panel-bottom-note"><span>Directory and assignment data are not synced to a database.</span><span>Access controls are not active in the UI phase.</span></div></section>
  </>;
}
