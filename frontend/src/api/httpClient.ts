import axios, { CanceledError } from 'axios';
import type { InternalAxiosRequestConfig } from 'axios';

interface AuthRequestConfig extends InternalAxiosRequestConfig {
  authRetried?: boolean;
  authEpoch?: number;
}

let accessToken: string | null = null;
let authEpoch = 0;
let refreshPromise: Promise<string> | null = null;
const listeners = new Set<(token: string | null) => void>();
const authChannel = typeof BroadcastChannel === 'undefined'
  ? null : new BroadcastChannel('movie-service-auth');

export const getAccessToken = () => accessToken;

const updateAccessToken = (token: string | null) => {
  accessToken = token;
  listeners.forEach(listener => listener(token));
};

export const subscribeAccessToken = (listener: (token: string | null) => void) => {
  listeners.add(listener);
  return () => { listeners.delete(listener); };
};

export const changeAuthSession = (token: string | null) => {
  authEpoch += 1;
  updateAccessToken(token);
  authChannel?.postMessage(token ? 'login' : 'logout');
};

authChannel?.addEventListener('message', event => {
  if (event.data !== 'login' && event.data !== 'logout') return;
  authEpoch += 1;
  updateAccessToken(null);
  if (event.data === 'login') window.dispatchEvent(new Event('movie-service-session-changed'));
});

export const withAuthLock = <T,>(operation: () => Promise<T>): Promise<T> => {
  if (navigator.locks) return navigator.locks.request('movie-service-auth', operation);
  return operation();
};

export const authHttpClient = axios.create({
  baseURL: '/api',
  timeout: 10000,
  withCredentials: true,
  headers: { 'Content-Type': 'application/json', 'X-Auth-Request': '1' },
});

export const refreshAccessToken = (): Promise<string> => {
  if (!refreshPromise) {
    const epoch = authEpoch;
    refreshPromise = withAuthLock(async () => {
      if (epoch !== authEpoch) throw new CanceledError('Сессия изменилась');
      try {
        const { data } = await authHttpClient.post<{ access_token: string }>('/auth/refresh');
        if (epoch !== authEpoch) throw new CanceledError('Сессия изменилась');
        updateAccessToken(data.access_token);
        return data.access_token;
      } catch (error) {
        if (axios.isAxiosError(error) && error.response?.status === 401 && epoch === authEpoch) {
          updateAccessToken(null);
        }
        throw error;
      }
    }).finally(() => { refreshPromise = null; });
  }
  return refreshPromise;
};

export const httpClient = axios.create({
  baseURL: '/api',
  timeout: 10000,
  withCredentials: true,
  headers: { 'Content-Type': 'application/json' },
});

httpClient.interceptors.request.use((config: AuthRequestConfig) => {
  config.authEpoch ??= authEpoch;
  if (accessToken) config.headers.set('Authorization', `Bearer ${accessToken}`);
  return config;
});

httpClient.interceptors.response.use(response => response, async (error: unknown) => {
  if (!axios.isAxiosError(error) || error.response?.status !== 401 || !error.config) {
    return Promise.reject(error);
  }
  const config = error.config as AuthRequestConfig;
  if (config.authRetried || config.authEpoch !== authEpoch) return Promise.reject(error);
  config.authRetried = true;
  const previous = config.headers.get('Authorization');
  const token = accessToken && previous !== `Bearer ${accessToken}`
    ? accessToken : await refreshAccessToken();
  if (config.authEpoch !== authEpoch) throw new CanceledError('Сессия изменилась');
  config.headers.set('Authorization', `Bearer ${token}`);
  return httpClient.request(config);
});
