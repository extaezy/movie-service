import React, { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useToast } from '../../context/ToastContext';
import { registerApi } from '../../api/auth';
import { getApiErrorMessage } from '../../api/errors';
import styles from './Register.module.css';

export const Register: React.FC = () => {
  const [username, setUsername] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [passwordConfirm, setPasswordConfirm] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  const { showToast } = useToast();
  const navigate = useNavigate();

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');

    if (!username || !email || !password || !passwordConfirm) {
      setError('Заполните все обязательные поля');
      return;
    }

    if (password.length < 8) {
      setError('Пароль должен содержать не менее 8 символов');
      return;
    }

    if (password !== passwordConfirm) {
      setError('Пароли не совпадают');
      return;
    }

    setLoading(true);
    try {
      await registerApi({
        username,
        email,
        password,
        password_confirm: passwordConfirm,
      });
      showToast('Регистрация успешна');
      navigate('/login');
    } catch (err: unknown) {
      setError(getApiErrorMessage(err, 'Ошибка регистрации. Попробуйте снова.'));
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className={styles.container}>
      <div className={styles.card}>
        <h1 className={styles.title}>Регистрация</h1>
        {error && <div className={styles.commonError}>{error}</div>}
        <form onSubmit={handleSubmit} className={styles.form}>
          <div className={styles.field}>
            <label className={styles.label}>Имя пользователя</label>
            <input
              type="text"
              className={styles.input}
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              placeholder="username"
            />
          </div>
          <div className={styles.field}>
            <label className={styles.label}>Email</label>
            <input
              type="email"
              className={styles.input}
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="example@domain.com"
            />
          </div>
          <div className={styles.field}>
            <label className={styles.label}>Пароль</label>
            <input
              type="password"
              className={styles.input}
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="Не менее 8 символов"
            />
          </div>
          <div className={styles.field}>
            <label className={styles.label}>Подтверждение пароля</label>
            <input
              type="password"
              className={styles.input}
              value={passwordConfirm}
              onChange={(e) => setPasswordConfirm(e.target.value)}
              placeholder="Повторите пароль"
            />
          </div>
          <button type="submit" className={styles.submitBtn} disabled={loading}>
            {loading ? 'Регистрация...' : 'Зарегистрироваться'}
          </button>
        </form>
        <p className={styles.footerText}>
          Уже есть аккаунт? <Link to="/login" className={styles.link}>Войти</Link>
        </p>
      </div>
    </div>
  );
};
