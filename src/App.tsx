import { useState, type FormEvent, type ReactNode } from 'react';
import { BrowserRouter, Link, Navigate, Outlet, Route, Routes } from 'react-router-dom';
import { ArrowLeft, LockKeyhole, RefreshCw, ShieldCheck, Mail, KeyRound } from 'lucide-react';
import { AppShell } from './components/Layout';
import { BrandMark } from './components/BrandMark';
import { AuthProvider, useAuth } from './lib/auth';
import { api, toApiFailure } from './lib/api';
import { LiveWorkspace } from './pages/LiveWorkspace';
import { DashboardPage } from './pages/Dashboard';
import { AttendancePage } from './pages/Attendance';
import { PredictionPage } from './pages/Predictions';
import { ReportsPage } from './pages/Reports';
import { DevicesPage } from './pages/Devices';
import { PeoplePage } from './pages/People';
import { SettingsPage } from './pages/Settings';

function LoginPage() {
  const { status, user, error, signIn, refresh, signOut } = useAuth();
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [bootstrapToken, setBootstrapToken] = useState('');

  async function handleSignIn(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!email.trim() || !password) return;
    setBusy(true);
    setMessage(null);
    const problem = await signIn(email.trim(), password);
    if (problem) setMessage(problem);
    setBusy(false);
  }

  async function provisionFirstAdmin(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!bootstrapToken.trim()) return;
    setBusy(true);
    setMessage(null);
    try {
      await api.post('/admin/bootstrap', {}, { headers: { 'X-Admin-Bootstrap-Token': bootstrapToken.trim() } });
      setBootstrapToken('');
      await refresh();
    } catch (requestError) {
      setMessage(toApiFailure(requestError).message);
    } finally {
      setBusy(false);
    }
  }

  if (status === 'authenticated' && user?.account_state === 'active' && user.role) return <Navigate to="/" replace />;
  const signedIn = status === 'authenticated';
  const eligibleForBootstrap = signedIn && user?.account_state === 'pending' && !user.role;

  return (
    <div className="login-page">
      <div className="login-top"><BrandMark /><Link to="/" className="back-link"><ArrowLeft size={16} /> Back to UI preview</Link></div>
      <div className="login-card">
        <div className="login-icon"><LockKeyhole size={20} /></div>
        <p className="eyebrow">COLLEGE ATTENDANCE WORKSPACE</p>
        <h1>{eligibleForBootstrap ? <>Provision the<br /><em>first administrator.</em></> : <>Sign in to your<br /><em>academic workspace.</em></>}</h1>
        <p className="login-copy">Secure role-based access for students, staff and administrators.</p>

        {eligibleForBootstrap ? (
          <>
            <div className="login-notice"><strong>Signed in as {user?.email}</strong><span>Your account is pending. The first administrator can be provisioned once using the protected bootstrap token configured for this application.</span></div>
            <form className="bootstrap-form" onSubmit={provisionFirstAdmin}>
              <label htmlFor="bootstrap-token">First-admin bootstrap token</label>
              <input id="bootstrap-token" type="password" value={bootstrapToken} onChange={(event) => setBootstrapToken(event.target.value)} autoComplete="off" required />
              <button className="button button-primary button-wide" disabled={busy}>{busy ? 'Provisioning…' : 'Create the first Admin'} <ShieldCheck size={15} /></button>
            </form>
            {message && <div className="form-error" role="alert">{message}</div>}
            <button type="button" className="demo-link" onClick={() => void signOut()}>Sign out of this account</button>
          </>
        ) : signedIn && user?.account_state === 'disabled' ? (
          <>
            <div className="login-notice"><strong>This account is disabled.</strong><span>Contact a SmartAttend administrator.</span></div>
            <button type="button" className="demo-link" onClick={() => void signOut()}>Sign out</button>
          </>
        ) : (
          <>
            {status === 'error' && <div className="login-notice"><strong>Session check unavailable.</strong><span>{error ?? 'The API did not verify the current session.'} Retry before accessing live records.</span><button type="button" className="text-button" onClick={() => void refresh()}><RefreshCw size={13} /> Retry</button></div>}
            {message && <div className="form-error" role="alert">{message}</div>}
            <form className="login-form" onSubmit={handleSignIn}>
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
                  autoComplete="current-password"
                  placeholder="••••••••"
                  required
                />
              </div>
              <button className="button button-primary button-wide" disabled={busy || status === 'loading'}>
                {busy ? 'Signing in…' : 'Sign in'} <LockKeyhole size={15} />
              </button>
            </form>
            <div className="login-security-note"><ShieldCheck size={15} /><span>Supabase Auth · signed session · role checked by the API</span></div>
            <Link to="/" className="demo-link">Continue to clearly labeled UI preview <ArrowLeft size={14} /></Link>
          </>
        )}
      </div>
      <p className="login-footer">SmartAttend AI · Supabase + Render + Vercel</p>
    </div>
  );
}

function AuthCheckError() {
  const { error, refresh } = useAuth();
  return <div className="empty-page"><div className="empty-icon"><ShieldCheck size={22} /></div><p className="eyebrow">IDENTITY CHECK UNAVAILABLE</p><h2>Live records are temporarily hidden</h2><p>{error ?? 'The application could not verify the current session.'} No sample data is shown while an existing session cannot be confirmed.</p><div className="empty-actions"><button className="button button-primary" onClick={() => void refresh()}><RefreshCw size={15} /> Retry</button><Link to="/login" className="button button-secondary">Sign in</Link></div></div>;
}

function LoadingScreen() {
  return (
    <div className="empty-page loading-screen" role="status" aria-live="polite">
      <img className="splash-lockup" src="/smartattend-lockup.png" alt="SmartAttend AI — AI Powered Attendance System. Developed by Simbu AI/ML from ESEC." />
      <div className="loading-indicator" aria-hidden="true" />
      <h2>Checking your workspace session</h2>
      <p>Live records remain hidden until your role is confirmed.</p>
    </div>
  );
}

function PendingAccess() {
  const { signOut, user } = useAuth();
  return <div className="empty-page"><div className="empty-icon"><LockKeyhole size={22} /></div><p className="eyebrow">ACCOUNT PROVISIONING</p><h2>Your workspace role is pending</h2><p>{user?.email ?? 'This account'} has not been assigned a Student, Staff or Admin role. An administrator must provision the profile before live records are available.</p><div className="empty-actions"><Link className="button button-primary" to="/login">Open account setup</Link><button className="button button-secondary" onClick={() => void signOut()}>Sign out</button></div></div>;
}

function DisabledAccess() {
  const { signOut } = useAuth();
  return <div className="empty-page"><div className="empty-icon"><LockKeyhole size={22} /></div><p className="eyebrow">ACCESS DISABLED</p><h2>This account cannot open live records</h2><p>Contact an administrator if you believe this access state is incorrect.</p><button className="button button-primary" onClick={() => void signOut()}>Sign out</button></div>;
}

function NotFound() {
  return <div className="empty-page"><div className="empty-icon"><span className="not-found-mark">404</span></div><h2>That page isn't in this workspace</h2><p>Try the workspace navigation or return to the overview.</p><Link to="/" className="button button-primary">Back to overview</Link></div>;
}

function WorkspaceRoute() {
  const { status } = useAuth();
  if (status === 'loading') return <LoadingScreen />;
  if (status === 'error') return <AuthCheckError />;
  return <Outlet />;
}

function RoleAwarePage({ demo }: { demo: ReactNode }) {
  const { status, user } = useAuth();
  if (status === 'authenticated') {
    if (user?.account_state === 'disabled') return <DisabledAccess />;
    if (user?.account_state !== 'active' || !user.role) return <PendingAccess />;
    return <LiveWorkspace />;
  }
  return <>{demo}</>;
}

export function App() {
  return (
    <AuthProvider>
      <BrowserRouter>
        <Routes>
          <Route path="/login" element={<LoginPage />} />
          <Route element={<WorkspaceRoute />}>
            <Route element={<AppShell />}>
              <Route index element={<RoleAwarePage demo={<DashboardPage />} />} />
              <Route path="attendance" element={<RoleAwarePage demo={<AttendancePage />} />} />
              <Route path="predictions" element={<RoleAwarePage demo={<PredictionPage />} />} />
              <Route path="reports" element={<RoleAwarePage demo={<ReportsPage />} />} />
              <Route path="devices" element={<RoleAwarePage demo={<DevicesPage />} />} />
              <Route path="students" element={<RoleAwarePage demo={<PeoplePage kind="students" />} />} />
              <Route path="staff" element={<RoleAwarePage demo={<PeoplePage kind="staff" />} />} />
              <Route path="settings" element={<RoleAwarePage demo={<SettingsPage />} />} />
              <Route path="*" element={<NotFound />} />
            </Route>
          </Route>
        </Routes>
      </BrowserRouter>
    </AuthProvider>
  );
}
