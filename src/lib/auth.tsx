import { createContext, useCallback, useContext, useEffect, useMemo, useState, type PropsWithChildren } from 'react';
import { createClient } from '@supabase/supabase-js';
import { api, toApiFailure } from './api';
import type { PreviewRole } from '../types';

const SUPABASE_URL = import.meta.env.VITE_SUPABASE_URL as string;
const SUPABASE_ANON_KEY = import.meta.env.VITE_SUPABASE_ANON_KEY as string;

export const supabase = createClient(SUPABASE_URL, SUPABASE_ANON_KEY);

export type AuthStatus = 'loading' | 'anonymous' | 'authenticated' | 'error';

export interface AuthUser {
  authenticated: true;
  account_state: 'active' | 'pending' | 'disabled' | 'unprovisioned';
  role: PreviewRole | null;
  open_id?: string;
  email?: string;
  display_name?: string;
}

interface AuthContextValue {
  status: AuthStatus;
  user: AuthUser | null;
  error: string | null;
  refresh: () => Promise<void>;
  signIn: (email: string, password: string) => Promise<string | null>;
  signOut: () => Promise<void>;
}

interface ApiEnvelope<T> { data: T }
const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: PropsWithChildren) {
  const [status, setStatus] = useState<AuthStatus>('loading');
  const [user, setUser] = useState<AuthUser | null>(null);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    setStatus('loading');
    setError(null);
    try {
      // Get current Supabase session
      const { data: { session } } = await supabase.auth.getSession();
      if (!session) {
        setUser(null);
        setStatus('anonymous');
        return;
      }
      // Call backend /auth/me with Bearer token
      const response = await api.get<ApiEnvelope<AuthUser>>('/auth/me', {
        headers: { Authorization: `Bearer ${session.access_token}` },
      });
      const next = response.data.data;
      if (next?.authenticated) {
        setUser(next);
        setStatus('authenticated');
      } else {
        setUser(null);
        setStatus('anonymous');
      }
    } catch (requestError) {
      const failure = toApiFailure(requestError);
      if (failure.status === 401) {
        setUser(null);
        setStatus('anonymous');
      } else {
        setUser(null);
        setError(failure.message);
        setStatus('error');
      }
    }
  }, []);

  useEffect(() => {
    void refresh();
    // Listen for Supabase auth state changes (sign in / sign out)
    const { data: { subscription } } = supabase.auth.onAuthStateChange((_event, _session) => {
      void refresh();
    });
    return () => subscription.unsubscribe();
  }, [refresh]);

  const signIn = useCallback(async (email: string, password: string): Promise<string | null> => {
    const { error: authError } = await supabase.auth.signInWithPassword({ email, password });
    if (authError) return authError.message;
    await refresh();
    return null;
  }, [refresh]);

  const signOut = useCallback(async () => {
    await supabase.auth.signOut();
    try { await api.post('/auth/logout', {}); } catch { /* ignore */ }
    setUser(null);
    setError(null);
    setStatus('anonymous');
  }, []);

  const value = useMemo(() => ({ status, user, error, refresh, signIn, signOut }), [status, user, error, refresh, signIn, signOut]);
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) throw new Error('useAuth must be used inside AuthProvider.');
  return context;
}
