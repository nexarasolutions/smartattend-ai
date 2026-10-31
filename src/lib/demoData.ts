import type { AttendanceRow, DeviceRow } from '../types';

export const demoStudents = [
  { name: 'Aarav Mehta', rollNo: 'STU-24-018', department: 'Computer Science', year: 'Year 2', section: 'CS-B', attendance: 88, classes: '37 / 42', trend: '+4.2%' },
  { name: 'Diya Nair', rollNo: 'STU-24-026', department: 'Computer Science', year: 'Year 2', section: 'CS-B', attendance: 72, classes: '30 / 42', trend: '−3.1%' },
  { name: 'Kabir Shah', rollNo: 'STU-23-041', department: 'Information Systems', year: 'Year 3', section: 'IS-A', attendance: 94, classes: '45 / 48', trend: '+2.5%' },
  { name: 'Meera Iyer', rollNo: 'STU-24-052', department: 'Computer Science', year: 'Year 2', section: 'CS-A', attendance: 81, classes: '34 / 42', trend: '+1.8%' },
  { name: 'Rohan Das', rollNo: 'STU-25-011', department: 'Data Science', year: 'Year 1', section: 'DS-A', attendance: 67, classes: '28 / 42', trend: '−5.4%' },
  { name: 'Sara Thomas', rollNo: 'STU-23-064', department: 'Information Systems', year: 'Year 3', section: 'IS-A', attendance: 91, classes: '44 / 48', trend: '+3.2%' },
  { name: 'Ishaan Rao', rollNo: 'STU-24-073', department: 'Computer Science', year: 'Year 2', section: 'CS-B', attendance: 79, classes: '33 / 42', trend: '−0.8%' },
  { name: 'Anaya Kapoor', rollNo: 'STU-25-029', department: 'Data Science', year: 'Year 1', section: 'DS-A', attendance: 86, classes: '36 / 42', trend: '+2.1%' },
];

export const demoAttendance: AttendanceRow[] = [
  { id: 'ATT-1042', student: 'Aarav Mehta', rollNo: 'STU-24-018', subject: 'Data Structures', section: 'CS-B', date: '30 Oct 2026', status: 'Present' },
  { id: 'ATT-1041', student: 'Diya Nair', rollNo: 'STU-24-026', subject: 'Data Structures', section: 'CS-B', date: '30 Oct 2026', status: 'Absent' },
  { id: 'ATT-1040', student: 'Kabir Shah', rollNo: 'STU-23-041', subject: 'Database Systems', section: 'IS-A', date: '30 Oct 2026', status: 'Present' },
  { id: 'ATT-1039', student: 'Meera Iyer', rollNo: 'STU-24-052', subject: 'Data Structures', section: 'CS-A', date: '30 Oct 2026', status: 'Late' },
  { id: 'ATT-1038', student: 'Rohan Das', rollNo: 'STU-25-011', subject: 'Applied Statistics', section: 'DS-A', date: '29 Oct 2026', status: 'Absent' },
  { id: 'ATT-1037', student: 'Sara Thomas', rollNo: 'STU-23-064', subject: 'Database Systems', section: 'IS-A', date: '29 Oct 2026', status: 'Present' },
  { id: 'ATT-1036', student: 'Ishaan Rao', rollNo: 'STU-24-073', subject: 'Data Structures', section: 'CS-B', date: '29 Oct 2026', status: 'Present' },
  { id: 'ATT-1035', student: 'Anaya Kapoor', rollNo: 'STU-25-029', subject: 'Applied Statistics', section: 'DS-A', date: '29 Oct 2026', status: 'Present' },
];

export const demoDevices: DeviceRow[] = [
  { id: 'PI-ATT-021', room: 'A-204 · North Wing', model: 'Raspberry Pi 4B', sampleState: 'online', lastSeen: '2 min ago', firmware: 'v0.8.4' },
  { id: 'PI-ATT-018', room: 'B-112 · Science Block', model: 'Raspberry Pi 4B', sampleState: 'online', lastSeen: '5 min ago', firmware: 'v0.8.4' },
  { id: 'PI-ATT-014', room: 'C-306 · Library Annex', model: 'Raspberry Pi 3B+', sampleState: 'attention', lastSeen: '18 min ago', firmware: 'v0.8.1' },
  { id: 'PI-ATT-009', room: 'A-101 · North Wing', model: 'Raspberry Pi 4B', sampleState: 'offline', lastSeen: '46 min ago', firmware: 'v0.8.2' },
];

export const attendanceTrend = [
  { day: 'Mon', current: 88, previous: 84 },
  { day: 'Tue', current: 91, previous: 86 },
  { day: 'Wed', current: 86, previous: 88 },
  { day: 'Thu', current: 93, previous: 87 },
  { day: 'Fri', current: 90, previous: 85 },
  { day: 'Sat', current: 82, previous: 80 },
];

export const subjectAttendance = [
  { subject: 'Data Structures', rate: 91, color: '#3156c8' },
  { subject: 'Database Systems', rate: 86, color: '#53a98a' },
  { subject: 'Applied Statistics', rate: 79, color: '#d6a14d' },
  { subject: 'Computer Networks', rate: 94, color: '#7586a7' },
];

export const demoNotifications = [
  { title: 'Attendance review needed', detail: 'CS-B · 2 records awaiting staff confirmation', time: 'Today, 10:42 AM', kind: 'amber' },
  { title: 'Weekly report ready', detail: 'Department summary · Week 43', time: 'Today, 9:15 AM', kind: 'blue' },
  { title: 'Device requires attention', detail: 'Sample status · Library Annex · PI-ATT-014', time: 'Yesterday, 4:30 PM', kind: 'rose' },
];
