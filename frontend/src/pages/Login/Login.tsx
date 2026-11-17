import React, { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useAuth } from '../../context/AuthContext.tsx';
import { useToast } from '../../context/ToastContext';
import { getApiErrorMessage } from '../../api/errors';
import styles from './Login.module.css';

export const Login: React.FC = () => {
  const [identifier, setIdentifier] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  const { login } = useAuth();
  const { showToast } = useToast();
  const navigate = useNavigate();

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');

    if (!identifier || !password) {
      setError('Заполните все обязательные поля');
      return;
    }

    setLoading(true);
    try {
      await login({ identifier, password });
      showToast('Успешный вход!');
      navigate('/');
    } catch (err: unknown) {
      setError(getApiErrorMessage(err, 'Ошибка входа. Проверьте данные.'));
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className={styles.container}>
      <div className={styles.card}>
        <h1 className={styles.title}>Вход в Movie Service</h1>
        {error && <div className={styles.commonError}>{error}</div>}
        <form onSubmit={handleSubmit} className={styles.form}>
          <div className={styles.field}>
            <label className={styles.label}>Имя пользователя или email</label>
            <input
              type="text"
              className={styles.input}
              value={identifier}
              onChange={(e) => setIdentifier(e.target.value)}
              placeholder="Введите username или email"
            />
          </div>
          <div className={styles.field}>
            <label className={styles.label}>Пароль</label>
            <input
              type="password"
              className={styles.input}
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="Введите пароль"
            />
          </div>
          <button type="submit" className={styles.submitBtn} disabled={loading}>
            {loading ? 'Вход...' : 'Войти'}
          </button>
        </form>
        <p className={styles.footerText}>
          Нет аккаунта? <Link to="/register" className={styles.link}>Зарегистрироваться</Link>
        </p>
      </div>
    </div>
  );
};
