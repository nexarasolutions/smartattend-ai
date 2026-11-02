import { useState, type FormEvent, type ReactNode } from 'react';
import { BrowserRouter, Link, Navigate, Outlet, Route, Routes } from 'react-router-dom';
import { LockKeyhole, RefreshCw, ShieldCheck, Mail, KeyRound, User as UserIcon, UserPlus, LogIn } from 'lucide-react';
import { AppShell } from './components/Layout';
import { BrandMark } from './components/BrandMark';
import { AuthProvider, useAuth } from './lib/auth';
import { LiveWorkspace } from './pages/LiveWorkspace';
import { PredictionPage } from './pages/Predictions';
import { ReportsPage } from './pages/Reports';
import { DevicesPage } from './pages/Devices';
import { PeoplePage } from './pages/People';
import { SettingsPage } from './pages/Settings';

function LoginPage() {
  const { status, user, signIn, signUp } = useAuth();
  const [mode, setMode] = useState<'signin' | 'signup'>('signin');
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [successMsg, setSuccessMsg] = useState<string | null>(null);

  // Form fields
  const [name, setName] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [role, setRole] = useState<'Student' | 'Staff' | 'Admin'>('Admin');

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!email.trim() || !password) return;
    setBusy(true);
    setMessage(null);
    setSuccessMsg(null);

    if (mode === 'signin') {
      const problem = await signIn(email.trim(), password);
      if (problem) {
        setMessage(problem);
      }
    } else {
      if (!name.trim()) {
        setMessage('Please enter your full name.');
        setBusy(false);
        return;
      }
      const problem = await signUp(email.trim(), password, name.trim(), role);
      if (problem) {
        setMessage(problem);
      } else {
        setSuccessMsg('Account created successfully! Signing you in…');
        await signIn(email.trim(), password);
      }
    }
    setBusy(false);
  }

  if (status === 'authenticated' && user?.account_state === 'active') {
    return <Navigate to="/" replace />;
  }

  return (
    <div className="login-page">
      <div className="login-top">
        <BrandMark />
      </div>
      <div className="login-card">
        <div className="login-icon">
          {mode === 'signin' ? <LockKeyhole size={20} /> : <UserPlus size={20} />}
        </div>
        <p className="eyebrow">COLLEGE ATTENDANCE WORKSPACE</p>
        <h1>
          {mode === 'signin' ? (
            <>Sign in to your<br /><em>academic workspace.</em></>
          ) : (
            <>Create your<br /><em>SmartAttend account.</em></>
          )}
        </h1>
        <p className="login-copy">Real-world AI attendance tracking and management connected to live database.</p>

        {/* Tab Switcher */}
        <div style={{ display: 'flex', gap: '8px', marginBottom: '16px', borderBottom: '1px solid #e2e8f0', paddingBottom: '8px' }}>
          <button
            type="button"
            onClick={() => { setMode('signin'); setMessage(null); setSuccessMsg(null); }}
            style={{
              flex: 1,
              padding: '8px',
              borderRadius: '6px',
              border: 'none',
              background: mode === 'signin' ? '#3156c8' : '#f1f5f9',
              color: mode === 'signin' ? '#fff' : '#64748b',
              fontWeight: 600,
              fontSize: '12px',
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              gap: '6px',
            }}
          >
            <LogIn size={14} /> Sign In
          </button>
          <button
            type="button"
            onClick={() => { setMode('signup'); setMessage(null); setSuccessMsg(null); }}
            style={{
              flex: 1,
              padding: '8px',
              borderRadius: '6px',
              border: 'none',
              background: mode === 'signup' ? '#3156c8' : '#f1f5f9',
              color: mode === 'signup' ? '#fff' : '#64748b',
              fontWeight: 600,
              fontSize: '12px',
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              gap: '6px',
            }}
          >
            <UserPlus size={14} /> Create Account
          </button>
        </div>

        {status === 'error' && (
          <div className="login-notice">
            <strong>Session check unavailable.</strong>
            <span>{error ?? 'Could not verify session.'}</span>
            <button type="button" className="text-button" onClick={() => void refresh()}>
              <RefreshCw size={13} /> Retry
            </button>
          </div>
        )}

        {message && <div className="form-error" role="alert">{message}</div>}
        {successMsg && (
          <div style={{ margin: '10px 0', padding: '10px', background: '#f0fdf4', border: '1px solid #bbf7d0', borderRadius: '6px', color: '#166534', fontSize: '12px' }}>
            {successMsg}
          </div>
        )}

        <form className="login-form" onSubmit={handleSubmit}>
          {mode === 'signup' && (
            <>
              <div className="form-field">
                <label htmlFor="login-name"><UserIcon size={14} /> Full Name</label>
                <input
                  id="login-name"
                  type="text"
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  placeholder="Prof. John Doe / Student Name"
                  required
                />
              </div>
              <div className="form-field">
                <label htmlFor="login-role"><ShieldCheck size={14} /> Account Role</label>
                <select
                  id="login-role"
                  value={role}
                  onChange={(e) => setRole(e.target.value as 'Student' | 'Staff' | 'Admin')}
                  style={{ width: '100%', height: '38px', padding: '0 10px', border: '1px solid #e3e8f0', borderRadius: '7px', background: '#fff' }}
                >
                  <option value="Admin">Administrator (Full Access)</option>
                  <option value="Staff">Faculty / Staff</option>
                  <option value="Student">Student</option>
                </select>
              </div>
            </>
          )}

          <div className="form-field">
            <label htmlFor="login-email"><Mail size={14} /> Email address</label>
            <input
              id="login-email"
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              autoComplete="email"
              placeholder="you@college.edu"
              required
            />
          </div>

          <div className="form-field">
            <label htmlFor="login-password"><KeyRound size={14} /> Password</label>
            <input
              id="login-password"
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              autoComplete={mode === 'signin' ? 'current-password' : 'new-password'}
              placeholder="••••••••"
              required
            />
          </div>

          <button className="button button-primary button-wide" disabled={busy || status === 'loading'}>
            {busy ? (mode === 'signin' ? 'Signing in…' : 'Creating account…') : (mode === 'signin' ? 'Sign in' : 'Register & Launch Workspace')}{' '}
            <LockKeyhole size={15} />
          </button>
        </form>

        <div className="login-security-note">
          <ShieldCheck size={15} />
          <span>Real-World Supabase Auth · PostgreSQL DB · Render Flask API</span>
        </div>
      </div>
      <p className="login-footer">SmartAttend AI · Real-World College Attendance Management</p>
    </div>
  );
}

function AuthCheckError() {
  const { error, refresh } = useAuth();
  return (
    <div className="empty-page">
      <div className="empty-icon"><ShieldCheck size={22} /></div>
      <p className="eyebrow">IDENTITY CHECK UNAVAILABLE</p>
      <h2>Connection Error</h2>
      <p>{error ?? 'The application could not verify the session.'}</p>
      <div className="empty-actions">
        <button className="button button-primary" onClick={() => void refresh()}><RefreshCw size={15} /> Retry</button>
        <Link to="/login" className="button button-secondary">Sign in</Link>
      </div>
    </div>
  );
}

function LoadingScreen() {
  return (
    <div className="empty-page loading-screen" role="status" aria-live="polite">
      <img className="splash-lockup" src="/smartattend-lockup.png" alt="SmartAttend AI" />
      <div className="loading-indicator" aria-hidden="true" />
      <h2>Connecting to SmartAttend Workspace</h2>
      <p>Loading real-time records from live database…</p>
    </div>
  );
}

function DisabledAccess() {
  const { signOut } = useAuth();
  return (
    <div className="empty-page">
      <div className="empty-icon"><LockKeyhole size={22} /></div>
      <p className="eyebrow">ACCESS DISABLED</p>
      <h2>Account disabled</h2>
      <button className="button button-primary" onClick={() => void signOut()}>Sign out</button>
    </div>
  );
}

function NotFound() {
  return (
    <div className="empty-page">
      <div className="empty-icon"><span className="not-found-mark">404</span></div>
      <h2>Page not found</h2>
      <Link to="/" className="button button-primary">Back to workspace</Link>
    </div>
  );
}

function WorkspaceRoute() {
  const { status } = useAuth();
  if (status === 'loading') return <LoadingScreen />;
  if (status === 'error') return <AuthCheckError />;
  return <Outlet />;
}

function ProtectedRoute({ children }: { children?: ReactNode }) {
  const { status, user } = useAuth();
  if (status === 'loading') return <LoadingScreen />;
  if (status !== 'authenticated') {
    return <Navigate to="/login" replace />;
  }
  if (user?.account_state === 'disabled') {
    return <DisabledAccess />;
  }
  return <>{children ?? <LiveWorkspace />}</>;
}

export function App() {
  return (
    <AuthProvider>
      <BrowserRouter>
        <Routes>
          <Route path="/login" element={<LoginPage />} />
          <Route element={<WorkspaceRoute />}>
            <Route element={<AppShell />}>
              <Route index element={<ProtectedRoute><LiveWorkspace /></ProtectedRoute>} />
              <Route path="attendance" element={<ProtectedRoute><LiveWorkspace /></ProtectedRoute>} />
              <Route path="predictions" element={<ProtectedRoute><PredictionPage /></ProtectedRoute>} />
              <Route path="reports" element={<ProtectedRoute><ReportsPage /></ProtectedRoute>} />
              <Route path="devices" element={<ProtectedRoute><DevicesPage /></ProtectedRoute>} />
              <Route path="students" element={<ProtectedRoute><PeoplePage kind="students" /></ProtectedRoute>} />
              <Route path="staff" element={<ProtectedRoute><PeoplePage kind="staff" /></ProtectedRoute>} />
              <Route path="settings" element={<ProtectedRoute><SettingsPage /></ProtectedRoute>} />
              <Route path="*" element={<NotFound />} />
            </Route>
          </Route>
        </Routes>
      </BrowserRouter>
    </AuthProvider>
  );
}
