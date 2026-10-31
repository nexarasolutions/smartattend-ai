import { Cell, Pie, PieChart, ResponsiveContainer } from 'recharts';
import type { AttendanceStatus } from '../types';

export function StatusPill({ status, sample = true }: { status: AttendanceStatus | 'online' | 'offline' | 'attention'; sample?: boolean }) {
  const label = sample ? `Sample · ${status}` : status;
  return <span className={`status-pill status-${status.toLowerCase()}`}><i />{label}</span>;
}

export function DemoDonut({ present = 89.6 }: { present?: number }) {
  const data = [{ name: 'Present', value: present }, { name: 'Remaining', value: 100 - present }];
  return <div className="donut-wrap"><div className="donut-chart"><ResponsiveContainer width="100%" height="100%"><PieChart><Pie data={data} dataKey="value" innerRadius="74%" outerRadius="96%" startAngle={90} endAngle={-270} paddingAngle={1} stroke="none">{data.map((entry, index) => <Cell key={entry.name} fill={index === 0 ? '#3156c8' : '#e9edf5'} />)}</Pie></PieChart></ResponsiveContainer></div><div className="donut-center"><strong>{present}%</strong><span>sample</span></div></div>;
}
