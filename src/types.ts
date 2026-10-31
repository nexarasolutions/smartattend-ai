export type PreviewRole = 'Admin' | 'Staff' | 'Student';
export type AttendanceStatus = 'Present' | 'Absent' | 'Late';

export interface AttendanceRow {
  id: string;
  student: string;
  rollNo: string;
  subject: string;
  section: string;
  date: string;
  status: AttendanceStatus;
}

export interface DeviceRow {
  id: string;
  room: string;
  model: string;
  sampleState: 'online' | 'offline' | 'attention';
  lastSeen: string;
  firmware: string;
}

export interface OutletContextValue {
  role: PreviewRole;
  setRole: (role: PreviewRole) => void;
}
