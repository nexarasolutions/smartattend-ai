import { createContext, useCallback, useContext, useEffect, useMemo, useState, type PropsWithChildren } from 'react';
import { createClient, type SupabaseClient } from '@supabase/supabase-js';
import { api, toApiFailure } from './api';
import type { PreviewRole } from '../types';

const FALLBACK_SUPABASE_URL = 'https://pfjaffhkdvrfcelgslap.supabase.co';
const FALLBACK_SUPABASE_KEY =
  'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InBmamFmZmhrZHZyZmNlbGdzbGFwIiwicm9sZSI6ImFub24iLCJpYXQiOjE3OTM0NTUyNTksImV4cCI6MjEwOTAzMTI1OX0.DqSWjpYxGilc68-Bz5YOgfPhf3l0FWnL6AuZi1aIT90';

const SUPABASE_URL = (import.meta.env.VITE_SUPABASE_URL as string) || FALLBACK_SUPABASE_URL;
const SUPABASE_ANON_KEY = (import.meta.env.VITE_SUPABASE_ANON_KEY as string) || FALLBACK_SUPABASE_KEY;

export const supabase: SupabaseClient = createClient(SUPABASE_URL, SUPABASE_ANON_KEY);

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
  signUp: (email: string, password: string, name: string, role: string) => Promise<string | null>;
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
    try {
      const { data: { subscription } } = supabase.auth.onAuthStateChange((_event, _session) => {
        void refresh();
      });
      return () => subscription.unsubscribe();
    } catch {
      // ignore
    }
  }, [refresh]);

  const signIn = useCallback(async (email: string, password: string): Promise<string | null> => {
    try {
      const { error: authError } = await supabase.auth.signInWithPassword({ email, password });
      if (authError) return authError.message;
      await refresh();
      return null;
    } catch (err) {
      return err instanceof Error ? err.message : 'Sign in failed';
    }
  }, [refresh]);

  const signUp = useCallback(async (email: string, password: string, name: string, role: string): Promise<string | null> => {
    try {
      const { data, error: authError } = await supabase.auth.signUp({
        email,
        password,
        options: {
          data: {
            name,
            full_name: name,
            role,
          },
        },
      });
      if (authError) return authError.message;
      if (data.session) {
        await refresh();
      }
      return null;
    } catch (err) {
      return err instanceof Error ? err.message : 'Sign up failed';
    }
  }, [refresh]);

  const signOut = useCallback(async () => {
    try {
      await supabase.auth.signOut();
      await api.post('/auth/logout', {});
    } catch {
      /* ignore */
    }
    setUser(null);
    setError(null);
    setStatus('anonymous');
  }, []);

  const value = useMemo(() => ({ status, user, error, refresh, signIn, signUp, signOut }), [status, user, error, refresh, signIn, signUp, signOut]);
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) throw new Error('useAuth must be used inside AuthProvider.');
  return context;
}
