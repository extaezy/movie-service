import React from 'react';
import { BrowserRouter, Routes, Route, Navigate, useLocation } from 'react-router-dom';
import { AuthProvider, useAuth } from './context/AuthContext.tsx';
import { ToastProvider } from './context/ToastContext';
import { Header } from './components/Header/Header';
import { Spinner } from './components/Spinner/Spinner';

import { Catalog } from './pages/Catalog/Catalog';
import { MoviePage } from './pages/Movie/Movie';
import { Login } from './pages/Login/Login';
import { Register } from './pages/Register/Register';
import { Profile } from './pages/Profile/Profile';
import { EditProfile } from './pages/EditProfile/EditProfile';
import { Lists } from './pages/Lists/Lists';
import { SavedMovieList } from './pages/Lists/SavedMovieList';
import { Friends } from './pages/Friends/Friends';

// Защищённый маршрут
const ProtectedRoute: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const { user, loading } = useAuth();
  if (loading) return <Spinner />;
  if (!user) return <Navigate to="/login" replace />;
  return <>{children}</>;
};

const AppLayout: React.FC = () => {
  const location = useLocation();
  const hideHeader = location.pathname === '/login' || location.pathname === '/register';

  return (
    <>
      {!hideHeader && <Header />}
      <main>
        <Routes>
          <Route path="/" element={<Catalog />} />
          <Route path="/movies/:id" element={<MoviePage />} />
          <Route path="/movies/tmdb/:id" element={<MoviePage source="tmdb" />} />
          <Route path="/demo/movies/:id" element={<MoviePage source="demo" />} />
          <Route path="/login" element={<Login />} />
          <Route path="/register" element={<Register />} />
          <Route path="/profile/:username" element={<Profile />} />
          <Route
            path="/profile/me/edit"
            element={
              <ProtectedRoute>
                <EditProfile />
              </ProtectedRoute>
            }
          />
          {(['watchlist', 'watched', 'favorite'] as const).map((listType) => (
            <Route
              key={listType}
              path={`/lists/${listType}`}
              element={
                <ProtectedRoute>
                  <SavedMovieList key={listType} listType={listType} />
                </ProtectedRoute>
              }
            />
          ))}
          <Route
            path="/lists/:type"
            element={
              <ProtectedRoute>
                <Lists />
              </ProtectedRoute>
            }
          />
          <Route
            path="/friends"
            element={
              <ProtectedRoute>
                <Friends />
              </ProtectedRoute>
            }
          />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </main>
    </>
  );
};

export const App: React.FC = () => {
  return (
    <BrowserRouter>
      <AuthProvider>
        <ToastProvider>
          <AppLayout />
        </ToastProvider>
      </AuthProvider>
    </BrowserRouter>
  );
};

export default App;
