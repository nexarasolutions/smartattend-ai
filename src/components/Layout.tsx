import { useEffect, useState, type KeyboardEvent } from 'react';
import { Link, NavLink, Outlet, useLocation, useNavigate } from 'react-router-dom';
import {
  Activity, Bell, BookOpen, CalendarCheck2, ChartNoAxesCombined,
  Cpu, FileBarChart2, GraduationCap, LayoutDashboard, LogIn, LogOut, Menu, Search, Settings,
  ShieldCheck,
} from 'lucide-react';
import { BrandMark } from './BrandMark';
import { api, toApiFailure } from '../lib/api';
import { useAuth } from '../lib/auth';
import type { OutletContextValue, PreviewRole } from '../types';

const pageTitles: Record<string, string> = {
  '/': 'Overview', '/attendance': 'Attendance', '/predictions': 'AI attendance forecast',
  '/reports': 'Reports & analytics', '/devices': 'IoT device management',
  '/students': 'Students', '/staff': 'Staff & subjects', '/settings': 'Workspace settings',
};
const navItems = [
  { path: '/', label: 'Overview', icon: LayoutDashboard, group: 'WORKSPACE', roles: ['Admin', 'Staff', 'Student'] },
  { path: '/students', label: 'Students', icon: GraduationCap, group: 'ACADEMICS', roles: ['Admin', 'Staff'] },
  { path: '/staff', label: 'Staff & subjects', icon: BookOpen, group: 'ACADEMICS', roles: ['Admin', 'Staff'] },
  { path: '/attendance', label: 'Attendance', icon: CalendarCheck2, group: 'ACADEMICS', roles: ['Admin', 'Staff', 'Student'] },
  { path: '/predictions', label: 'AI forecast', icon: ChartNoAxesCombined, group: 'INSIGHTS', roles: ['Admin', 'Staff', 'Student'] },
  { path: '/reports', label: 'Reports', icon: FileBarChart2, group: 'INSIGHTS', roles: ['Admin', 'Staff'] },
  { path: '/devices', label: 'IoT devices', icon: Cpu, group: 'OPERATIONS', roles: ['Admin'] },
];
interface ApiEnvelope<T> { data: T }
interface LiveNotification { id: string; title: string; body: string; created_at: string; read_at: string | null }

export function AppShell() {
  const auth = useAuth();
  const location = useLocation();
  const navigate = useNavigate();
  const [menuOpen, setMenuOpen] = useState(false);
  const [search, setSearch] = useState('');
  const [notificationsOpen, setNotificationsOpen] = useState(false);
  const [liveNotifications, setLiveNotifications] = useState<LiveNotification[]>([]);
  const [notificationError, setNotificationError] = useState<string | null>(null);

  const role: PreviewRole = auth.user?.role || 'Admin';
  const title = pageTitles[location.pathname] ?? 'SmartAttend';
  const visibleNavItems = navItems.filter((item) => item.roles.includes(role));
  const grouped = [...new Set(visibleNavItems.map((item) => item.group))];
  const userLabel = auth.user?.display_name || auth.user?.email || 'Signed in user';
  const unread = liveNotifications.filter((notification) => !notification.read_at).length;

  useEffect(() => {
    let active = true;
    api.get<ApiEnvelope<LiveNotification[]>>('/notifications')
      .then((response) => { if (active) { setLiveNotifications(response.data.data); setNotificationError(null); } })
      .catch((error) => { if (active) setNotificationError(toApiFailure(error).message); });
    return () => { active = false; };
  }, [location.pathname]);

  function submitSearch(event: KeyboardEvent<HTMLInputElement>) {
    if (event.key === 'Enter' && search.trim() && role !== 'Student') navigate(`/students?search=${encodeURIComponent(search.trim())}`);
  }

  async function markRead(notification: LiveNotification) {
    if (notification.read_at) return;
    try {
      await api.patch(`/notifications/${notification.id}/read`, {});
      setLiveNotifications((items) => items.map((item) => item.id === notification.id ? { ...item, read_at: new Date().toISOString() } : item));
    } catch (error) { setNotificationError(toApiFailure(error).message); }
  }

  return (
    <div className="app-layout">
      {menuOpen && <button className="sidebar-scrim" aria-label="Close navigation" onClick={() => setMenuOpen(false)} />}
      <aside className={`sidebar ${menuOpen ? 'sidebar-open' : ''}`}>
        <div className="sidebar-brand"><BrandMark /></div>
        <div className="workspace-switcher">
          <div className="workspace-avatar">{(userLabel.slice(0, 1).toUpperCase() || 'S')}</div>
          <div className="workspace-copy">
            <strong>SmartAttend College</strong>
            <span>Live PostgreSQL Database</span>
          </div>
        </div>
        <nav className="primary-nav" aria-label="Main navigation">
          {grouped.map((group) => (
            <div className="nav-group" key={group}>
              <span className="nav-group-label">{group}</span>
              {visibleNavItems.filter((item) => item.group === group).map(({ path, label, icon: Icon }) => (
                <NavLink key={path} to={path} end={path === '/'} onClick={() => setMenuOpen(false)} className={({ isActive }) => `nav-link ${isActive ? 'nav-link-active' : ''}`}>
                  <Icon size={17} strokeWidth={1.8} /><span>{label}</span>
                </NavLink>
              ))}
            </div>
          ))}
        </nav>
        <div className="sidebar-footer">
          <div className="security-note"><ShieldCheck size={15} /><span>Real-world authenticated session · Role: {role}</span></div>
          {role === 'Admin' && <NavLink to="/settings" className={({ isActive }) => `nav-link settings-link ${isActive ? 'nav-link-active' : ''}`} onClick={() => setMenuOpen(false)}><Settings size={17} /><span>Settings</span></NavLink>}
          <div className="sidebar-profile">
            <div className="avatar avatar-indigo">{(userLabel.split(/\s+/).slice(0, 2).map((part) => part[0]).join('').toUpperCase() || 'U')}</div>
            <div><strong>{userLabel}</strong><span>{role} · Active session</span></div>
            <Activity size={15} />
          </div>
        </div>
      </aside>

      <div className="main-column">
        <header className="topbar">
          <button className="icon-button mobile-menu" onClick={() => setMenuOpen(true)} aria-label="Open navigation"><Menu size={20} /></button>
          <Link to="/" className="topbar-brand" aria-label="SmartAttend AI home"><BrandMark compact /></Link>
          <div className="breadcrumb"><span>Workspace</span><span className="breadcrumb-slash">/</span><strong>{title}</strong></div>
          <div className="topbar-actions">
            {role !== 'Student' && <label className="search-box"><Search size={16} /><input value={search} onChange={(event) => setSearch(event.target.value)} onKeyDown={submitSearch} placeholder="Search records…" aria-label="Search records (press Enter)" /><kbd>Enter</kbd></label>}
            <div className="notification-wrap">
              <button className="icon-button notification-button" aria-label={`Notifications${unread ? `, ${unread} unread` : ''}`} aria-expanded={notificationsOpen} onClick={() => setNotificationsOpen((open) => !open)}>
                <Bell size={18} />
                {unread > 0 && <i />}
              </button>
              {notificationsOpen && (
                <div className="notification-popover">
                  <div className="notification-popover-heading">
                    <div><strong>Notifications</strong><span>Live system alerts</span></div>
                    <button onClick={() => setNotificationsOpen(false)} aria-label="Close notifications">×</button>
                  </div>
                  {notificationError ? (
                    <div className="notification-empty">{notificationError}</div>
                  ) : liveNotifications.length ? (
                    liveNotifications.map((notification) => (
                      <button type="button" className={`notification-item notification-live ${notification.read_at ? '' : 'notification-unread'}`} key={notification.id} onClick={() => void markRead(notification)}>
                        <i className="notification-tone notification-blue" />
                        <span><strong>{notification.title}</strong><span>{notification.body}</span><small>{notification.created_at}{notification.read_at ? ' · read' : ' · click to mark read'}</small></span>
                      </button>
                    ))
                  ) : (
                    <div className="notification-empty">No notifications in database.</div>
                  )}
                </div>
              )}
            </div>
            <div className="topbar-divider" />
            {auth.status === 'authenticated' ? (
              <button className="topbar-auth" onClick={() => void auth.signOut()}><LogOut size={14} /><span>Sign out</span></button>
            ) : (
              <Link to="/login" className="topbar-auth"><LogIn size={14} /><span>Sign in</span></Link>
            )}
          </div>
        </header>
        <main className="page-content">
          <div className="live-top-banner">
            <span className="live-top-dot" />
            <strong>LIVE ATTENDANCE WORKSPACE</strong>
            <span>Connected to Supabase PostgreSQL Database & Render Python API</span>
          </div>
          <Outlet context={{ role, setRole: () => {} } satisfies OutletContextValue} />
          <footer className="app-footer">
            <span>SmartAttend AI · Real-World College Attendance Management</span>
            <span>Live Data · Enforced by Flask REST API & Supabase</span>
          </footer>
        </main>
      </div>
    </div>
  );
}
