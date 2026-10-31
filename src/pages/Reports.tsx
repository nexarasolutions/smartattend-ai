import { useState } from 'react';
import { Download, FileDown, FileText, Printer } from 'lucide-react';
import { DemoDonut } from '../components/Visuals';
import { subjectAttendance } from '../lib/demoData';

function exportSummaryCsv() {
  const data = [['Subject', 'Illustrative attendance rate'], ...subjectAttendance.map((item) => [item.subject, `${item.rate}%`])];
  const csv = data.map((row) => row.map((cell) => `"${cell.replaceAll('"', '""')}"`).join(',')).join('\n');
  const anchor = document.createElement('a');
  anchor.href = URL.createObjectURL(new Blob([csv], { type: 'text/csv;charset=utf-8' }));
  anchor.download = 'smartattend-demo-report.csv';
  anchor.click();
  URL.revokeObjectURL(anchor.href);
}

export function ReportsPage() {
  const [message, setMessage] = useState('');
  const doPdf = () => { setMessage('Print dialog opened. Use “Save as PDF” for a preview-only report.'); window.print(); window.setTimeout(() => setMessage(''), 3000); };
  return <>
    <div className="page-heading"><div><p className="eyebrow">REPORTS & ANALYTICS · SAMPLE AGGREGATES</p><h1>Reports that clarify patterns</h1><p className="page-subtitle">Department and subject layouts previewed with fictional summary figures.</p></div><div className="toolbar-right"><button className="button button-secondary" onClick={exportSummaryCsv}><Download size={14} /> Export sample CSV</button><button className="button button-primary" onClick={doPdf}><Printer size={14} /> Print / save PDF</button></div></div>
    <div className="report-card-grid"><div className="report-card"><span>College-wide attendance · sample</span><strong>89.6%</strong><small>Illustrative aggregate · no data source</small></div><div className="report-card"><span>Departments in example</span><strong>3</strong><small>Computer Science · IS · Data Science</small></div><div className="report-card"><span>Records below example threshold</span><strong>38</strong><small>Not a live risk report</small></div></div>
    <div className="dashboard-grid dashboard-grid-main"><section className="panel donut-panel"><DemoDonut /><div><div className="panel-heading"><div><h2>Attendance distribution</h2><p>Illustrative status mix</p></div></div><div className="report-legend"><span className="report-legend-item"><i />Present <strong>89.6%</strong></span><span className="report-legend-item"><i />Absent <strong>7.2%</strong></span><span className="report-legend-item"><i />Late / review <strong>3.2%</strong></span></div></div></section><section className="panel subject-panel"><div className="panel-heading"><div><h2>Department snapshot</h2><p>Fictional summary rates</p></div><FileBar /></div>{[{name:'Computer Science', rate:91, students:486},{name:'Information Systems', rate:88, students:402},{name:'Data Science', rate:84, students:271}].map((item) => <div className="subject-row" key={item.name}><div className="subject-row-heading"><span>{item.name}</span><strong>{item.rate}%</strong></div><div className="progress-track"><i style={{ width: `${item.rate}%`, backgroundColor: item.rate > 89 ? '#3156c8' : '#53a98a' }} /></div><span className="report-small-note">{item.students} sample student profiles</span></div>)}</section></div>
    <section className="panel wide-panel"><div className="panel-heading"><div><h2>Subject performance</h2><p>Sample data · report export does not create an official record</p></div><button className="button button-secondary" onClick={exportSummaryCsv}><FileDown size={14} /> CSV</button></div><div className="table-scroll"><table className="data-table"><thead><tr><th>SUBJECT</th><th>CLASSES · SAMPLE</th><th>ATTENDANCE RATE</th><th>ILLUSTRATIVE TREND</th></tr></thead><tbody>{subjectAttendance.map((subject, index) => <tr key={subject.subject}><td><strong className="table-strong">{subject.subject}</strong></td><td>{[42, 38, 40, 35][index]} sample sessions</td><td><div className="progress-inline"><div className="progress-track"><i style={{ width: `${subject.rate}%`, backgroundColor: subject.color }} /></div><strong>{subject.rate}%</strong></div></td><td><span className={`trend-label ${index === 2 ? 'trend-negative' : ''}`}>{index === 2 ? '−1.6%' : `+${(2.1 + index * 0.6).toFixed(1)}%`} <small>example</small></span></td></tr>)}</tbody></table></div><div className="panel-bottom-note"><span>Student names and attendance percentages shown on this prototype are fictional.</span><a href="/students">View sample student rows <FileText size={13} /></a></div></section>
    <section className="report-insight" style={{ marginTop: 13 }}><span><FileBar /></span><div><strong>How to read this preview</strong><p>These charts demonstrate the planned reporting interface only. Once connected, reports will use authorized PostgreSQL-backed records and carry a generation date, filters and export metadata.</p></div></section>
    {message && <div className="toast-message" role="status"><strong>Preview export</strong>{message}</div>}
  </>;
}

function FileBar() { return <FileText size={16} color="#8290a7" />; }
