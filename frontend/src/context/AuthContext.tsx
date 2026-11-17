import React, { createContext, useContext, useState, useEffect } from 'react';
import { isAxiosError } from 'axios';
import type { User } from '../types';
import { getCurrentUserApi, loginApi } from '../api/auth';
import type { LoginCredentials } from '../api/auth';
import { getApiErrorMessage } from '../api/errors';
import { ErrorState } from '../components/ErrorState/ErrorState';
import { Spinner } from '../components/Spinner/Spinner';

const ACCESS_TOKEN_KEY = 'movie_service_access_token';

interface AuthContextType {
  user: User | null;
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

  const fetchUser = async () => {
    setLoading(true);
    setError('');

    try {
      const token = sessionStorage.getItem(ACCESS_TOKEN_KEY);
      if (!token) {
        setUser(null);
        return;
      }

      setUser(await getCurrentUserApi(token));
    } catch (err: unknown) {
      if (isAxiosError(err) && err.response?.status === 401) {
        sessionStorage.removeItem(ACCESS_TOKEN_KEY);
        setUser(null);
      } else {
        setError(getApiErrorMessage(err, 'Не удалось загрузить текущего пользователя.'));
      }
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchUser();
  }, []);

  const login = async (credentials: LoginCredentials) => {
    const { access_token } = await loginApi(credentials);
    const currentUser = await getCurrentUserApi(access_token);
    sessionStorage.setItem(ACCESS_TOKEN_KEY, access_token);
    setUser(currentUser);
  };

  const logout = async () => {};

  return (
    <AuthContext.Provider value={{ user, loading, login, logout, refreshUser: fetchUser }}>
      {loading ? <Spinner /> : error ? <ErrorState message={error} onRetry={fetchUser} /> : children}
    </AuthContext.Provider>
  );
};

export const useAuth = () => {
  const context = useContext(AuthContext);
  if (!context) throw new Error('useAuth must be used within an AuthProvider');
  return context;
};
