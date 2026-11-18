import React, { useState, useEffect } from 'react';
import { isAxiosError } from 'axios';
import { useNavigate, useParams } from 'react-router-dom';
import { Spinner } from '../../components/Spinner/Spinner';
import { ErrorState } from '../../components/ErrorState/ErrorState';
import { useToast } from '../../context/ToastContext';
import { getApiErrorMessage } from '../../api/errors';
import {
  getDemoMovieDetailApi,
  getMovieDetailApi,
  openTmdbMovieApi,
  rateMovieApi,
  setMovieStatusApi,
  saveReviewApi,
  deleteReviewApi,
} from '../../api/movieDetail';
import type { MovieDetail } from '../../api/movieDetail';
import styles from './Movie.module.css';

interface MoviePageProps {
  source?: 'catalog' | 'tmdb' | 'demo';
}

const releaseDateFormat = new Intl.DateTimeFormat('ru-RU', { dateStyle: 'long', timeZone: 'UTC' });
const ratingFormat = new Intl.NumberFormat('ru-RU', { maximumFractionDigits: 2 });

export const MoviePage: React.FC<MoviePageProps> = ({ source = 'catalog' }) => {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const isDemo = source === 'demo';
  const [movie, setMovie] = useState<MovieDetail | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [notFound, setNotFound] = useState(false);
  const [error, setError] = useState('');
  const [attempt, setAttempt] = useState(0);

  // Рецензия локальное состояние формы
  const [reviewText, setReviewText] = useState<string>('');
  const [isSpoiler, setIsSpoiler] = useState<boolean>(false);
  const [isEditingReview, setIsEditingReview] = useState<boolean>(false);

  const { showToast } = useToast();

  const fetchMovie = () => setAttempt((previous) => previous + 1);

  useEffect(() => {
    setLoading(true);
    setNotFound(false);
    setError('');
    setMovie(null);

    if (!id || (!isDemo && (!/^\d+$/.test(id) || Number(id) < 1 || Number(id) > 2147483647))) {
      setNotFound(true);
      setLoading(false);
      return;
    }

    const controller = new AbortController();
    const { signal } = controller;
    const handleError = (requestError: unknown) => {
      if (signal.aborted) return;
      if (isAxiosError(requestError) && requestError.response?.status === 404) {
        setNotFound(true);
      } else {
        setError(getApiErrorMessage(requestError, 'Не удалось загрузить фильм.'));
      }
      setLoading(false);
    };

    if (source === 'tmdb') {
      openTmdbMovieApi(id, signal)
        .then((movieId) => {
          if (!signal.aborted) navigate(`/movies/${movieId}`, { replace: true });
        })
        .catch(handleError);
    } else {
      const request = isDemo ? getDemoMovieDetailApi(id, signal) : getMovieDetailApi(id, signal);
      request.then((data) => {
        if (signal.aborted) return;
        setMovie(data);
        setReviewText(data.user_review?.text ?? '');
        setIsSpoiler(data.user_review?.is_spoiler ?? false);
        setLoading(false);
      }).catch(handleError);
    }
    return () => controller.abort();
  }, [id, source, isDemo, navigate, attempt]);

  // Обработка рейтинга
  const handleRate = async (rating: number | null) => {
    if (!id || !isDemo) return;
    try {
      await rateMovieApi(id, rating);
      setMovie((prev) => (prev ? { ...prev, user_rating: rating } : null));
      showToast(rating ? `Оценка ${rating} сохранена` : 'Оценка удалена');
    } catch {
      showToast('Не удалось сохранить оценку');
    }
  };

  // Обработка статуса (watchlist, watched, favorite)
  const handleStatusChange = async (status: 'watchlist' | 'watched' | 'favorite') => {
    if (!id || !movie || !isDemo) return;
    const newStatus = movie.user_status === status ? null : status;
    try {
      await setMovieStatusApi(id, newStatus);
      setMovie((prev) => (prev ? { ...prev, user_status: newStatus } : null));
      showToast('Статус обновлен');
    } catch {
      showToast('Не удалось обновить статус');
    }
  };

  // Сохранение рецензии
  const handleSaveReview = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!id || !isDemo || !reviewText.trim()) return;
    try {
      await saveReviewApi(id, reviewText, isSpoiler);
      setMovie((prev) =>
        prev
          ? {
              ...prev,
              user_review: { id: 'temp', text: reviewText, is_spoiler: isSpoiler },
            }
          : null
      );
      setIsEditingReview(false);
      showToast('Рецензия сохранена');
      fetchMovie();
    } catch {
      showToast('Не удалось сохранить рецензию');
    }
  };

  // Удаление рецензии
  const handleDeleteReview = async () => {
    if (!id || !isDemo) return;
    try {
      await deleteReviewApi(id);
      setMovie((prev) => (prev ? { ...prev, user_review: null } : null));
      setReviewText('');
      setIsSpoiler(false);
      setIsEditingReview(false);
      showToast('Рецензия удалена');
    } catch {
      showToast('Не удалось удалить рецензию');
    }
  };

  if (loading) return <Spinner />;
  if (notFound) return <ErrorState message="Фильм не найден" />;
  if (!movie) return <ErrorState message={error} onRetry={fetchMovie} />;

  const releaseDate = movie.release_date ? releaseDateFormat.format(new Date(movie.release_date)) : movie.year;

  return (
    <div className={styles.container}>
      {/* Основная информация */}
      <div className={styles.heroSection}>
        <div className={styles.posterWrapper}>
          {movie.poster_url && (
            <img
              key={movie.poster_url}
              src={movie.poster_url}
              alt={movie.title}
              className={styles.poster}
              onError={(event) => { event.currentTarget.hidden = true; }}
            />
          )}
        </div>
        <div className={styles.meta}>
          <h1 className={styles.title}>{movie.title}</h1>
          <div className={styles.detailsRow}>
            {releaseDate && <span className={styles.year}>{releaseDate}</span>}
            {movie.duration && <span className={styles.duration}>{movie.duration} мин.</span>}
          </div>
          <div className={styles.genres}>
            {movie.genres?.map((genre) => (
              <span key={genre} className={styles.genreTag}>
                {genre}
              </span>
            ))}
          </div>
          <p className={styles.description}>{movie.description || 'Описание отсутствует.'}</p>
          {!isDemo && (
            <div className={styles.detailsRow}>
              <span>
                Рейтинг TMDB {movie.tmdb_vote_average == null
                  ? '— нет оценок'
                  : `${ratingFormat.format(movie.tmdb_vote_average)}/10 (голосов: ${movie.tmdb_vote_count})`}
              </span>
              <span>
                Рейтинг Movie Service {movie.average_rating == null
                  ? '— нет оценок'
                  : `${ratingFormat.format(movie.average_rating)}/10 (голосов: ${movie.ratings_count})`}
              </span>
            </div>
          )}

          {/* Блок добавления в список */}
          <div className={styles.statusTabs}>
            <button
              className={`${styles.statusBtn} ${movie.user_status === 'watchlist' ? styles.activeStatus : ''}`}
              disabled={!isDemo}
              onClick={() => handleStatusChange('watchlist')}
            >
              Планирую посмотреть
            </button>
            <button
              className={`${styles.statusBtn} ${movie.user_status === 'watched' ? styles.activeStatus : ''}`}
              disabled={!isDemo}
              onClick={() => handleStatusChange('watched')}
            >
              Просмотрено
            </button>
            <button
              className={`${styles.statusBtn} ${movie.user_status === 'favorite' ? styles.activeStatus : ''}`}
              disabled={!isDemo}
              onClick={() => handleStatusChange('favorite')}
            >
              Любимое
            </button>
          </div>
        </div>
      </div>

      <div className={styles.contentGrid}>
        {/* Левая колонка: Оценка и Своя рецензия */}
        <div className={styles.leftColumn}>
          {/* Блок "Моя оценка" */}
          <div className={styles.card}>
            <h3 className={styles.cardTitle}>Моя оценка</h3>
            <div className={styles.ratingSelector}>
              {Array.from({ length: 10 }, (_, i) => i + 1).map((num) => (
                <button
                  key={num}
                  className={`${styles.rateBtn} ${movie.user_rating === num ? styles.activeRate : ''}`}
                  disabled={!isDemo}
                  onClick={() => handleRate(num)}
                >
                  {num}
                </button>
              ))}
            </div>
            {movie.user_rating && (
              <button className={styles.deleteRateBtn} onClick={() => handleRate(null)}>
                Удалить оценку
              </button>
            )}
          </div>

          {/* Блок "Моя рецензия" */}
          <div className={styles.card}>
            <h3 className={styles.cardTitle}>Моя рецензия</h3>
            {movie.user_review && !isEditingReview ? (
              <div className={styles.myReviewView}>
                <p className={styles.reviewText}>{movie.user_review.text}</p>
                {movie.user_review.is_spoiler && <span className={styles.spoilerTag}>Содержит спойлеры</span>}
                <div className={styles.reviewActions}>
                  <button className={styles.actionBtn} onClick={() => setIsEditingReview(true)}>
                    Редактировать
                  </button>
                  <button className={`${styles.actionBtn} ${styles.danger}`} onClick={handleDeleteReview}>
                    Удалить
                  </button>
                </div>
              </div>
            ) : (
              <form onSubmit={handleSaveReview} className={styles.reviewForm}>
                <textarea
                  className={styles.textarea}
                  placeholder="Напишите вашу рецензию..."
                  value={reviewText}
                  onChange={(e) => setReviewText(e.target.value)}
                  rows={4}
                  disabled={!isDemo}
                />
                <label className={styles.checkboxLabel}>
                  <input
                    type="checkbox"
                    checked={isSpoiler}
                    disabled={!isDemo}
                    onChange={(e) => setIsSpoiler(e.target.checked)}
                  />
                  Содержит спойлеры
                </label>
                <div className={styles.formButtons}>
                  <button type="submit" className={styles.saveBtn} disabled={!isDemo}>
                    Сохранить
                  </button>
                  {movie.user_review && (
                    <button
                      type="button"
                      className={styles.cancelBtn}
                      onClick={() => setIsEditingReview(false)}
                    >
                      Отмена
                    </button>
                  )}
                </div>
              </form>
            )}
          </div>
        </div>

        {/* Правая колонка: Рецензии других и Рецензии критиков */}
        <div className={styles.rightColumn}>
          {/* Рецензии других пользователей */}
          <div className={styles.card}>
            <h3 className={styles.cardTitle}>Рецензии пользователей</h3>
            {movie.reviews && movie.reviews.length > 0 ? (
              <div className={styles.reviewsList}>
                {movie.reviews.map((rev) => (
                  <div key={rev.id} className={styles.reviewCard}>
                    <div className={styles.reviewHeader}>
                      <span className={styles.authorName}>{rev.author.display_name || rev.author.username}</span>
                      <span className={styles.reviewDate}>{new Date(rev.created_at).toLocaleDateString()}</span>
                    </div>
                    {rev.is_spoiler && <span className={styles.spoilerTag}>Спойлер</span>}
                    <p className={styles.reviewBody}>{rev.text}</p>
                  </div>
                ))}
              </div>
            ) : (
              <p className={styles.emptyText}>{isDemo ? 'Пока нет рецензий от пользователей' : 'Рецензии пользователей пока не подключены'}</p>
            )}
          </div>

          {/* Рецензии критиков */}
          <div className={styles.card}>
            <h3 className={styles.cardTitle}>Рецензии критиков</h3>
            {movie.critic_reviews && movie.critic_reviews.length > 0 ? (
              <div className={styles.reviewsList}>
                {movie.critic_reviews.map((crit) => (
                  <div key={crit.id} className={styles.criticCard}>
                    <div className={styles.criticHeader}>
                      <span className={styles.sourceName}>{crit.source}</span>
                      <span className={styles.criticName}>{crit.critic}</span>
                      {crit.rating && <span className={styles.criticRating}>{crit.rating}</span>}
                    </div>
                    <p className={styles.reviewBody}>"{crit.excerpt}"</p>
                    <a href={crit.url} target="_blank" rel="noopener noreferrer" className={styles.readMoreLink}>
                      Читать полностью →
                    </a>
                  </div>
                ))}
              </div>
            ) : (
              <p className={styles.emptyText}>{isDemo ? 'Пока нет рецензий критиков' : 'Рецензии критиков пока не подключены'}</p>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};
