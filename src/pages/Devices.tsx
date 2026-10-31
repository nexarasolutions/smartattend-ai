import { useMemo, useState } from 'react';
import { Activity, Cpu, MapPin, Plus, RefreshCcw, Search, Signal, X } from 'lucide-react';
import { demoDevices } from '../lib/demoData';
import { StatusPill } from '../components/Visuals';
import type { DeviceRow } from '../types';

export function DevicesPage() {
  const [devices, setDevices] = useState<DeviceRow[]>(demoDevices);
  const [query, setQuery] = useState('');
  const [modalOpen, setModalOpen] = useState(false);
  const [toast, setToast] = useState('');
  const [newId, setNewId] = useState('');
  const [newRoom, setNewRoom] = useState('');
  const shownDevices = useMemo(() => devices.filter((device) => `${device.id} ${device.room} ${device.model}`.toLowerCase().includes(query.toLowerCase())), [devices, query]);
  function registerSample() {
    if (!newId.trim() || !newRoom.trim()) return;
    setDevices((current) => [{ id: newId.trim().toUpperCase(), room: newRoom.trim(), model: 'Raspberry Pi · sample', sampleState: 'offline', lastSeen: 'Not connected', firmware: 'Not reported' }, ...current]);
    setModalOpen(false);
    setNewId(''); setNewRoom('');
    setToast('Sample row added to this browser only. No device was registered or contacted.');
    window.setTimeout(() => setToast(''), 3500);
  }
  const online = devices.filter((device) => device.sampleState === 'online').length;
  const offline = devices.filter((device) => device.sampleState === 'offline').length;
  const attention = devices.filter((device) => device.sampleState === 'attention').length;
  return <>
    <div className="page-heading"><div><p className="eyebrow">IOT DEVICE MANAGEMENT · UI PREVIEW</p><h1>Device fleet</h1><p className="page-subtitle">A hardware-neutral control surface for future Raspberry Pi integrations.</p></div><button className="button button-primary" onClick={() => setModalOpen(true)}><Plus size={15} /> Add sample device</button></div>
    <div className="device-summary"><div className="device-stat"><span>Devices in sample view</span><strong>{devices.length}</strong><small>Not a registered fleet</small></div><div className="device-stat"><span>Sample “online” state</span><strong>{online}</strong><small>Fictional UI fixture only</small></div><div className="device-stat"><span>Sample “offline” state</span><strong>{offline}</strong><small>No live heartbeat source</small></div><div className="device-stat"><span>Sample attention state</span><strong>{attention}</strong><small>Not a real health alert</small></div></div>
    <div className="page-toolbar"><div className="toolbar-left"><label className="search-box attendance-search"><Search size={15} /><input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Search device or room…" aria-label="Search device list" /></label><button className="button button-secondary" onClick={() => { setToast('Heartbeat check is not connected in this UI preview.'); window.setTimeout(() => setToast(''), 3000); }}><RefreshCcw size={14} /> Check heartbeat</button></div><div className="toolbar-right"><span className="status-pill status-attention"><i />No live device connection</span></div></div>
    <section className="panel wide-panel"><div className="panel-heading"><div><h2>Raspberry Pi devices</h2><p>Sample device inventory · states below are not live telemetry</p></div><span className="status-pill"><i />Sensor type: not assumed</span></div><div className="table-scroll"><table className="data-table"><thead><tr><th>DEVICE</th><th>ROOM MAPPING</th><th>STATUS</th><th>LAST HEARTBEAT</th><th>FIRMWARE</th><th>DETAILS</th></tr></thead><tbody>{shownDevices.map((device) => <tr key={device.id}><td><div className="device-cell"><span className="device-icon"><Cpu size={15} /></span><span><strong>{device.id}</strong><small>{device.model}</small></span></div></td><td><span className="room-cell"><MapPin size={12} />{device.room}</span></td><td><StatusPill status={device.sampleState} /></td><td><span className="device-last-seen"><Signal size={12} />{device.lastSeen}</span></td><td>{device.firmware}</td><td><button className="table-action" onClick={() => { setToast('Device details are sample-only until the Flask device API is connected.'); window.setTimeout(() => setToast(''), 3000); }}>View</button></td></tr>)}</tbody></table></div><div className="device-table-note"><Activity size={14} /><span>Registration, activation, device credentials, classroom mapping, secure heartbeats, event idempotency, failure queue and health monitoring are not connected yet. Sensor integration remains pluggable; no RFID/QR/fingerprint/camera hardware is assumed.</span></div><div className="pagination"><span>{shownDevices.length} sample device rows · no hardware connection</span><div className="pagination-actions"><button disabled>‹</button><button className="active">1</button><button disabled>›</button></div></div></section>
    {modalOpen && <div className="modal-backdrop" role="presentation" onClick={(event) => { if (event.target === event.currentTarget) setModalOpen(false); }}><section className="modal-card" role="dialog" aria-modal="true" aria-labelledby="device-dialog-title"><div className="modal-header"><div><h2 id="device-dialog-title">Add a sample device row</h2><p>This form will not contact or register hardware.</p></div><button className="icon-button" aria-label="Close dialog" onClick={() => setModalOpen(false)}><X size={17} /></button></div><label className="form-field">Device ID<input value={newId} onChange={(event) => setNewId(event.target.value)} placeholder="e.g. PI-ATT-025" /></label><label className="form-field">Room mapping<input value={newRoom} onChange={(event) => setNewRoom(event.target.value)} placeholder="e.g. A-205 · North Wing" /></label><div className="modal-note">This adds a fictional inventory row to the current browser view only. Registration and credential activation will be implemented in the IoT integration phase.</div><div className="modal-actions"><button className="button button-secondary" onClick={() => setModalOpen(false)}>Cancel</button><button className="button button-primary" disabled={!newId.trim() || !newRoom.trim()} onClick={registerSample}>Add demo row</button></div></section></div>}
    {toast && <div className="toast-message" role="status"><strong>Device preview</strong>{toast}</div>}
  </>;
}
