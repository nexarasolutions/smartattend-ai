import axios from 'axios';
import { supabase } from './auth';

const API_BASE = (import.meta.env.VITE_API_BASE_URL as string | undefined) || '/api';

/** All browser API requests use the configured base URL; Vite proxies /api to Flask during development. */
export const api = axios.create({
  baseURL: API_BASE,
  timeout: 15_000,
  withCredentials: true,
  headers: { Accept: 'application/json', 'Content-Type': 'application/json' },
});

function readCookie(name: string): string | null {
  if (typeof document === 'undefined') return null;
  const prefix = `${name}=`;
  const entry = document.cookie.split('; ').find((item) => item.startsWith(prefix));
  return entry ? decodeURIComponent(entry.slice(prefix.length)) : null;
}

api.interceptors.request.use(async (config) => {
  // Attach Supabase Bearer token to every request
  const { data: { session } } = await supabase.auth.getSession();
  if (session?.access_token) {
    config.headers.set('Authorization', `Bearer ${session.access_token}`);
  }
  const method = (config.method ?? 'get').toUpperCase();
  if (['POST', 'PUT', 'PATCH', 'DELETE'].includes(method)) {
    const csrf = readCookie('smartattend_csrf');
    if (csrf) config.headers.set('X-CSRF-Token', csrf);
  }
  return config;
});

export interface ApiFailure {
  message: string;
  status?: number;
  requestId?: string;
}

export function toApiFailure(error: unknown): ApiFailure {
  if (axios.isAxiosError(error)) {
    const body = error.response?.data;
    return {
      message: body?.error?.message ?? body?.message ?? error.message ?? 'The request could not be completed.',
      status: error.response?.status,
      requestId: body?.request_id ?? error.response?.headers['x-request-id'],
    };
  }
  return { message: error instanceof Error ? error.message : 'An unexpected error occurred.' };
}
