import React from 'react';
import { Link, NavLink } from 'react-router-dom';
import { useAuth } from '../../context/AuthContext.tsx';
import styles from './Header.module.css';

export const Header: React.FC = () => {
  const { user, logout } = useAuth();

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
              <button onClick={logout} className={styles.logoutBtn} title="Выйти">
                Выйти
              </button>
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