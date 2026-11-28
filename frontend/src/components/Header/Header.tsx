import React, { useState } from 'react';
import { Link, NavLink } from 'react-router-dom';
import { useAuth } from '../../context/AuthContext.tsx';
import styles from './Header.module.css';
import { getApiErrorMessage } from '../../api/errors';

export const Header: React.FC = () => {
  const { user, logout } = useAuth();
  const [loggingOut, setLoggingOut] = useState(false);
  const [logoutError, setLogoutError] = useState('');

  const handleLogout = async () => {
    setLoggingOut(true);
    setLogoutError('');
    try {
      await logout();
    } catch (error) {
      setLogoutError(getApiErrorMessage(error, 'Не удалось выйти. Повторите попытку.'));
    } finally {
      setLoggingOut(false);
    }
  };

  return (
    <header className={styles.header}>
      <div className={styles.container}>
        <Link to="/" className={styles.logo}>
          Movie Service
        </Link>
        <nav className={styles.nav}>
          <NavLink to="/" className={({ isActive }) => `${styles.navLink} ${isActive ? styles.active : ''}`} end>
            Каталог
          </NavLink>
          <NavLink to="/lists/watchlist" className={({ isActive }) => `${styles.navLink} ${isActive ? styles.active : ''}`}>
            Мои списки
          </NavLink>
          <NavLink to="/friends" className={({ isActive }) => `${styles.navLink} ${isActive ? styles.active : ''}`}>
            Друзья
          </NavLink>
        </nav>
        <div className={styles.userSection}>
          {user ? (
            <>
              <Link to={`/profile/${user.username}`} className={styles.profileLink}>
                <img
                  src={user.avatar_url || 'https://via.placeholder.com/36'}
                  alt={user.username}
                  className={styles.avatar}
                />
                <span className={styles.username}>{user.display_name || user.username}</span>
              </Link>
              <button onClick={handleLogout} disabled={loggingOut} className={styles.logoutBtn} title="Выйти">
                {loggingOut ? 'Выходим…' : 'Выйти'}
              </button>
              {logoutError && <span role="alert">{logoutError}</span>}
            </>
          ) : (
            <Link to="/login" className={styles.loginBtn}>
              Войти
            </Link>
          )}
        </div>
      </div>
    </header>
  );
};
