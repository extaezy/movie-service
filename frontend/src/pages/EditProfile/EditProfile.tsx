import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../../context/AuthContext.tsx';
import { useToast } from '../../context/ToastContext';
import { updateProfileApi } from '../../api/profile';
import styles from './EditProfile.module.css';

export const EditProfile: React.FC = () => {
  const { user, refreshUser } = useAuth();
  const { showToast } = useToast();
  const navigate = useNavigate();

  const [displayName, setDisplayName] = useState(user?.display_name || '');
  const [bio, setBio] = useState(user?.bio || '');
  const [avatarUrl, setAvatarUrl] = useState(user?.avatar_url || '');
  const [isPrivate, setIsPrivate] = useState(user?.is_private || false);
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    try {
      await updateProfileApi({
        display_name: displayName,
        bio,
        avatar_url: avatarUrl,
        is_private: isPrivate,
      });
      await refreshUser();
      showToast('Профиль обновлен');
      navigate(`/profile/${user?.username}`);
    } catch {
      showToast('Не удалось обновить профиль');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className={styles.container}>
      <div className={styles.card}>
        <h1 className={styles.title}>Редактирование профиля</h1>
        <form onSubmit={handleSubmit} className={styles.form}>
          <div className={styles.field}>
            <label className={styles.label}>Отображаемое имя</label>
            <input
              type="text"
              className={styles.input}
              value={displayName}
              onChange={(e) => setDisplayName(e.target.value)}
              placeholder="Ваше имя"
            />
          </div>
          <div className={styles.field}>
            <label className={styles.label}>Описание (Bio)</label>
            <textarea
              className={styles.textarea}
              value={bio}
              onChange={(e) => setBio(e.target.value)}
              placeholder="Пара слов о себе..."
              rows={3}
            />
          </div>
          <div className={styles.field}>
            <label className={styles.label}>URL аватара</label>
            <input
              type="url"
              className={styles.input}
              value={avatarUrl}
              onChange={(e) => setAvatarUrl(e.target.value)}
              placeholder="https://example.com/avatar.jpg"
            />
          </div>
          <div className={styles.checkboxField}>
            <label className={styles.checkboxLabel}>
              <input
                type="checkbox"
                checked={isPrivate}
                onChange={(e) => setIsPrivate(e.target.checked)}
              />
              Закрытый профиль
            </label>
          </div>
          <div className={styles.buttonsRow}>
            <button type="submit" className={styles.saveBtn} disabled={loading}>
              {loading ? 'Сохранение...' : 'Сохранить'}
            </button>
            <button
              type="button"
              className={styles.cancelBtn}
              onClick={() => navigate(`/profile/${user?.username}`)}
            >
              Отмена
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};