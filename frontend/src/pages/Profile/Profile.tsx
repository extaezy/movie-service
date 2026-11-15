import React, { useState, useEffect, useCallback } from 'react';
import { useParams, Link } from 'react-router-dom';
import { useAuth } from '../../context/AuthContext.tsx';
import { useToast } from '../../context/ToastContext';
import { Spinner } from '../../components/Spinner/Spinner';
import { ErrorState } from '../../components/ErrorState/ErrorState';
import { MovieCard } from '../../components/MovieCard/MovieCard';
import { getUserProfileApi, sendFriendRequestApi } from '../../api/profile';
import type { UserProfile } from '../../api/profile';
import styles from './Profile.module.css';

export const Profile: React.FC = () => {
  const { username } = useParams<{ username: string }>();
  const { user: currentUser } = useAuth();
  const { showToast } = useToast();

  const [profile, setProfile] = useState<UserProfile | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<boolean>(false);

  // Активная вкладка: 'lists' | 'ratings' | 'reviews'
  const [activeTab, setActiveTab] = useState<'lists' | 'ratings' | 'reviews'>('lists');
  // Подвкладка для списков: 'watchlist' | 'watched' | 'favorite'
  const [activeListSubTab, setActiveListSubTab] = useState<'watchlist' | 'watched' | 'favorite'>('watchlist');

  const isOwnProfile = currentUser?.username === username;

  const fetchProfile = useCallback(async () => {
    if (!username) return;
    setLoading(true);
    setError(false);
    try {
      const data = await getUserProfileApi(username);
      setProfile(data);
    } catch {
      setError(true);
    } finally {
      setLoading(false);
    }
  }, [username]);

  useEffect(() => {
    fetchProfile();
  }, [fetchProfile]);

  const handleSendFriendRequest = async () => {
    if (!profile) return;
    try {
      await sendFriendRequestApi(profile.username);
      setProfile((prev) => (prev ? { ...prev, pending_request: true } : null));
      showToast('Заявка в друзья отправлена');
    } catch {
      showToast('Не удалось отправить заявку');
    }
  };

  if (loading) return <Spinner />;
  if (error || !profile) return <ErrorState onRetry={fetchProfile} message="Профиль не найден или ошибка загрузки" />;

  const showFullContent = isOwnProfile || profile.is_friend || !profile.is_private;

  return (
    <div className={styles.container}>
      {/* Шапка профиля */}
      <div className={styles.profileHeader}>
        <img
          src={profile.avatar_url || 'https://via.placeholder.com/96'}
          alt={profile.username}
          className={styles.avatar}
        />
        <div className={styles.profileInfo}>
          <h1 className={styles.displayName}>{profile.display_name || profile.username}</h1>
          <span className={styles.username}>@{profile.username}</span>
          {profile.bio && <p className={styles.bio}>{profile.bio}</p>}
        </div>
        <div className={styles.profileActions}>
          {isOwnProfile ? (
            <Link to="/profile/me/edit" className={styles.editBtn}>
              Редактировать профиль
            </Link>
          ) : (
            !profile.is_friend && (
              <button
                className={styles.friendBtn}
                onClick={handleSendFriendRequest}
                disabled={profile.pending_request}
              >
                {profile.pending_request ? 'Заявка отправлена' : 'Добавить в друзья'}
              </button>
            )
          )}
        </div>
      </div>

      {/* Если закрытый профиль и не друг */}
      {!showFullContent ? (
        <div className={styles.privateNotice}>
          <p>Этот профиль закрыт. Добавьте пользователя в друзья, чтобы просматривать его списки, оценки и рецензии.</p>
        </div>
      ) : (
        <>
          {/* Табы профиля */}
          <div className={styles.tabsBar}>
            <button
              className={`${styles.tabBtn} ${activeTab === 'lists' ? styles.activeTab : ''}`}
              onClick={() => setActiveTab('lists')}
            >
              Списки
            </button>
            <button
              className={`${styles.tabBtn} ${activeTab === 'ratings' ? styles.activeTab : ''}`}
              onClick={() => setActiveTab('ratings')}
            >
              Оценки
            </button>
            <button
              className={`${styles.tabBtn} ${activeTab === 'reviews' ? styles.activeTab : ''}`}
              onClick={() => setActiveTab('reviews')}
            >
              Рецензии
            </button>
          </div>

          {/* Содержимое вкладок */}
          {activeTab === 'lists' && (
            <div className={styles.tabContent}>
              <div className={styles.subTabsBar}>
                <button
                  className={`${styles.subTabBtn} ${activeListSubTab === 'watchlist' ? styles.activeSubTab : ''}`}
                  onClick={() => setActiveListSubTab('watchlist')}
                >
                  Планирую посмотреть
                </button>
                <button
                  className={`${styles.subTabBtn} ${activeListSubTab === 'watched' ? styles.activeSubTab : ''}`}
                  onClick={() => setActiveListSubTab('watched')}
                >
                  Просмотрено
                </button>
                <button
                  className={`${styles.subTabBtn} ${activeListSubTab === 'favorite' ? styles.activeSubTab : ''}`}
                  onClick={() => setActiveListSubTab('favorite')}
                >
                  Любимое
                </button>
              </div>

              <div className={styles.moviesGrid}>
                {profile.lists?.[activeListSubTab]?.length ? (
                  profile.lists[activeListSubTab].map((movie) => (
                    <MovieCard key={movie.id} movie={movie} />
                  ))
                ) : (
                  <p className={styles.emptyText}>Список пуст</p>
                )}
              </div>
            </div>
          )}

          {activeTab === 'ratings' && (
            <div className={styles.tabContent}>
              <div className={styles.moviesGrid}>
                {profile.ratings?.length ? (
                  profile.ratings.map((item) => (
                    <div key={item.movie.id} className={styles.ratedCardWrapper}>
                      <MovieCard movie={item.movie} />
                      <div className={styles.ratingBadge}>★ {item.rating}</div>
                    </div>
                  ))
                ) : (
                  <p className={styles.emptyText}>Нет оценок</p>
                )}
              </div>
            </div>
          )}

          {activeTab === 'reviews' && (
            <div className={styles.reviewsList}>
              {profile.reviews?.length ? (
                profile.reviews.map((rev) => (
                  <div key={rev.id} className={styles.reviewCard}>
                    <div className={styles.reviewHeader}>
                      <Link to={`/movies/${rev.movie.id}`} className={styles.movieLink}>
                        {rev.movie.title}
                      </Link>
                      <span className={styles.reviewDate}>{new Date(rev.created_at).toLocaleDateString()}</span>
                    </div>
                    {rev.is_spoiler && <span className={styles.spoilerTag}>Спойлер</span>}
                    <p className={styles.reviewBody}>{rev.text}</p>
                  </div>
                ))
              ) : (
                <p className={styles.emptyText}>Нет рецензий</p>
              )}
            </div>
          )}
        </>
      )}
    </div>
  );
};