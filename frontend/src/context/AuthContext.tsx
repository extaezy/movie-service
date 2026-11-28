import React, { createContext, useContext, useState, useEffect } from 'react';
import { isAxiosError } from 'axios';
import type { User } from '../types';
import { getCurrentUserApi, loginApi, logoutApi } from '../api/auth';
import { getAccessToken, refreshAccessToken, subscribeAccessToken } from '../api/httpClient';
import type { LoginCredentials } from '../api/auth';
import { getApiErrorMessage } from '../api/errors';
import { ErrorState } from '../components/ErrorState/ErrorState';
import { Spinner } from '../components/Spinner/Spinner';

interface AuthContextType {
  user: User | null;
  accessToken: string | null;
  loading: boolean;
  login: (credentials: LoginCredentials) => Promise<void>;
  logout: () => Promise<void>;
  refreshUser: () => Promise<void>;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export const AuthProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState('');
  const [accessToken, setAccessToken] = useState<string | null>(getAccessToken);

  const fetchUser = async () => {
    setLoading(true);
    setError('');

    try {
      const token = getAccessToken() ?? await refreshAccessToken();
      setUser(await getCurrentUserApi(token));
    } catch (err: unknown) {
      if (isAxiosError(err) && err.response?.status === 401) {
        setUser(null);
      } else {
        setError(getApiErrorMessage(err, 'Не удалось загрузить текущего пользователя.'));
      }
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    sessionStorage.removeItem('movie_service_access_token');
    const unsubscribe = subscribeAccessToken(token => {
      setAccessToken(token);
      if (!token) setUser(null);
    });
    window.addEventListener('movie-service-session-changed', fetchUser);
    fetchUser();
    return () => {
      unsubscribe();
      window.removeEventListener('movie-service-session-changed', fetchUser);
    };
  }, []);

  const login = async (credentials: LoginCredentials) => {
    const { access_token } = await loginApi(credentials);
    const currentUser = await getCurrentUserApi(access_token);
    setUser(currentUser);
  };

  const logout = async () => {
    await logoutApi();
    setUser(null);
  };

  return (
    <AuthContext.Provider value={{ user, accessToken, loading, login, logout, refreshUser: fetchUser }}>
      {loading ? <Spinner /> : error ? <ErrorState message={error} onRetry={fetchUser} /> : children}
    </AuthContext.Provider>
  );
};

export const useAuth = () => {
  const context = useContext(AuthContext);
  if (!context) throw new Error('useAuth must be used within an AuthProvider');
  return context;
};
