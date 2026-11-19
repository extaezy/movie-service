import React, { useCallback, useState, useEffect, useRef } from 'react';
import { isAxiosError } from 'axios';
import { Link, useNavigate, useParams } from 'react-router-dom';
import { Spinner } from '../../components/Spinner/Spinner';
import { ErrorState } from '../../components/ErrorState/ErrorState';
import { useAuth } from '../../context/AuthContext';
import { useToast } from '../../context/ToastContext';
import { getApiErrorMessage } from '../../api/errors';
import { addMovieListEntryApi } from '../../api/lists';
import type { ListType } from '../../api/lists';
import {
  createMovieReviewApi,
  getDemoMovieDetailApi,
  getMovieDetailApi,
  openTmdbMovieApi,
  removeMovieReviewApi,
  rateMovieApi,
  setMovieStatusApi,
  saveReviewApi,
  deleteReviewApi,
  updateMovieReviewApi,
} from '../../api/movieDetail';
import type { MovieDetail, Review } from '../../api/movieDetail';
import { UserReviewList } from './UserReviewList';
import styles from './Movie.module.css';

interface MoviePageProps {
  source?: 'catalog' | 'tmdb' | 'demo';
}

type SavedReview = NonNullable<MovieDetail['user_review']>;
type ReviewAction = 'save' | 'delete';
type ListSaveStatus = 'idle' | 'saving' | 'saved';

const listMessages = {
  watchlist: {
    added: 'Фильм добавлен в список',
    exists: 'Фильм уже в списке',
    error: 'Не удалось добавить фильм в список.',
  },
  watched: {
    added: 'Фильм отмечен как просмотренный',
    exists: 'Фильм уже в «Просмотрено»',
    error: 'Не удалось отметить фильм как просмотренный.',
  },
  favorite: {
    added: 'Фильм добавлен в «Любимое»',
    exists: 'Фильм уже в «Любимом»',
    error: 'Не удалось добавить фильм в «Любимое».',
  },
};

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
  const [listStatuses, setListStatuses] = useState<Partial<Record<ListType, ListSaveStatus>>>({});
  const listSubmissions = useRef<Partial<Record<ListType, AbortController>>>({});

  // Рецензия локальное состояние формы
  const [reviewText, setReviewText] = useState<string>('');
  const [isSpoiler, setIsSpoiler] = useState<boolean>(false);
  const [isEditingReview, setIsEditingReview] = useState<boolean>(false);
  const [pendingReviewAction, setPendingReviewAction] = useState<ReviewAction | null>(null);
  const [reviewError, setReviewError] = useState('');
  const [reviewRevision, setReviewRevision] = useState(0);
  const reviewSubmission = useRef<AbortController | null>(null);

  const { user, accessToken } = useAuth();
  const { showToast } = useToast();

  const editingReview = isEditingReview ? movie?.user_review : null;
  const unchangedReview = editingReview?.text === reviewText && editingReview?.is_spoiler === isSpoiler;

  const fetchMovie = () => setAttempt((previous) => previous + 1);

  useEffect(() => {
    setLoading(true);
    setNotFound(false);
    setError('');
    setMovie(null);
    setListStatuses({});
    setReviewError('');
    setIsEditingReview(false);
    setPendingReviewAction(null);

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
    return () => {
      controller.abort();
      Object.values(listSubmissions.current).forEach((submission) => submission.abort());
      listSubmissions.current = {};
      reviewSubmission.current?.abort();
      reviewSubmission.current = null;
    };
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

  const handleAddToList = async (listType: ListType) => {
    if (!movie || !accessToken || listSubmissions.current[listType]) return;
    const submission = new AbortController();
    const messages = listMessages[listType];
    listSubmissions.current[listType] = submission;
    setListStatuses((previous) => ({ ...previous, [listType]: 'saving' }));

    try {
      const created = await addMovieListEntryApi(movie.id, listType, accessToken, submission.signal);
      if (submission.signal.aborted) return;
      setListStatuses((previous) => ({ ...previous, [listType]: 'saved' }));
      showToast(created ? messages.added : messages.exists);
    } catch (requestError) {
      if (!submission.signal.aborted) {
        setListStatuses((previous) => ({ ...previous, [listType]: 'idle' }));
        showToast(getApiErrorMessage(requestError, messages.error));
      }
    } finally {
      if (listSubmissions.current[listType] === submission) delete listSubmissions.current[listType];
    }
  };

  const restoreOwnReview = useCallback((movieId: string, review: Review) => {
    setMovie((previous) => {
      if (previous?.id !== movieId || previous.user_review) return previous;
      return {
        ...previous,
        user_review: { id: review.id, text: review.text, is_spoiler: review.is_spoiler },
      };
    });
  }, []);

  const handleEditReview = () => {
    const review = movie?.user_review;
    if (!review) return;
    setReviewText(review.text);
    setIsSpoiler(review.is_spoiler);
    setReviewError('');
    setIsEditingReview(true);
  };

  const mutateReview = async (
    movieId: string,
    action: ReviewAction,
    mutate: (token: string, signal: AbortSignal) => Promise<SavedReview | null>,
  ) => {
    if (!accessToken || reviewSubmission.current) return;
    const submission = new AbortController();
    reviewSubmission.current = submission;
    setPendingReviewAction(action);
    setReviewError('');

    try {
      const saved = await mutate(accessToken, submission.signal);
      if (submission.signal.aborted) return;

      setMovie((previous) => previous?.id === movieId ? { ...previous, user_review: saved } : previous);
      setReviewText(saved?.text ?? '');
      setIsSpoiler(saved?.is_spoiler ?? false);
      setIsEditingReview(false);
      setReviewRevision((revision) => revision + 1);
      showToast(action === 'save' ? 'Рецензия сохранена' : 'Рецензия удалена');
    } catch (requestError) {
      if (!submission.signal.aborted) {
        const fallback = action === 'save' ? 'Не удалось сохранить рецензию.' : 'Не удалось удалить рецензию.';
        setReviewError(getApiErrorMessage(requestError, fallback));
      }
    } finally {
      if (reviewSubmission.current === submission) {
        reviewSubmission.current = null;
        setPendingReviewAction(null);
      }
    }
  };

  // Сохранение рецензии
  const handleSaveReview = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!id || !movie || !reviewText.trim()) return;

    if (!isDemo) {
      if (unchangedReview) return;
      const draft = { text: reviewText, contains_spoilers: isSpoiler };
      const changes: Partial<typeof draft> = {};
      if (editingReview?.text !== draft.text) changes.text = draft.text;
      if (editingReview?.is_spoiler !== draft.contains_spoilers) changes.contains_spoilers = draft.contains_spoilers;

      await mutateReview(movie.id, 'save', async (token, signal) => {
        const saved = editingReview
          ? await updateMovieReviewApi(editingReview.id, changes, token, signal)
          : await createMovieReviewApi(movie.id, draft, token, signal);
        return { id: String(saved.id), text: saved.text, is_spoiler: saved.contains_spoilers };
      });
      return;
    }

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
    const review = movie?.user_review;
    if (!id || !movie || !review) return;

    if (!isDemo) {
      await mutateReview(movie.id, 'delete', async (token, signal) => {
        await removeMovieReviewApi(review.id, token, signal);
        return null;
      });
      return;
    }

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
  const genres = movie.catalog_genres ?? (movie.genres ?? []).map((name) => ({ id: undefined, name }));
  const reviewFieldsDisabled = !isDemo && (!accessToken || pendingReviewAction !== null);
  const {
    watchlist: watchlistStatus = 'idle',
    watched: watchedStatus = 'idle',
    favorite: favoriteStatus = 'idle',
  } = listStatuses;
  const watchlistActive = isDemo ? movie.user_status === 'watchlist' : watchlistStatus === 'saved';
  const watchedActive = isDemo ? movie.user_status === 'watched' : watchedStatus === 'saved';
  const favoriteActive = isDemo ? movie.user_status === 'favorite' : favoriteStatus === 'saved';

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
            {genres.map(({ id: genreId, name }) => (
              user && genreId !== undefined ? (
                <Link
                  key={genreId}
                  className={styles.genreTag}
                  to={`/lists/watched?${new URLSearchParams({ genre_id: String(genreId), genre_name: name })}`}
                  title={`Просмотренные фильмы жанра «${name}»`}
                >
                  {name}
                </Link>
              ) : (
                <span key={genreId ?? name} className={styles.genreTag}>{name}</span>
              )
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
              type="button"
              className={`${styles.statusBtn} ${watchlistActive ? styles.activeStatus : ''}`}
              disabled={!isDemo && (!accessToken || watchlistStatus !== 'idle')}
              onClick={isDemo ? () => handleStatusChange('watchlist') : () => handleAddToList('watchlist')}
            >
              {watchlistStatus === 'saving' ? 'Добавляем…' : 'Планирую посмотреть'}
            </button>
            <button
              type="button"
              className={`${styles.statusBtn} ${watchedActive ? styles.activeStatus : ''}`}
              disabled={!isDemo && (!accessToken || watchedStatus !== 'idle')}
              onClick={isDemo ? () => handleStatusChange('watched') : () => handleAddToList('watched')}
            >
              {watchedStatus === 'saving' ? 'Отмечаем…' : 'Просмотрено'}
            </button>
            <button
              type="button"
              className={`${styles.statusBtn} ${favoriteActive ? styles.activeStatus : ''}`}
              disabled={!isDemo && (!accessToken || favoriteStatus !== 'idle')}
              onClick={isDemo ? () => handleStatusChange('favorite') : () => handleAddToList('favorite')}
            >
              {favoriteStatus === 'saving' ? 'Сохраняем…' : 'Любимое'}
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
              <div className={styles.myReviewView} aria-busy={pendingReviewAction === 'delete'}>
                <p className={styles.reviewText}>{movie.user_review.text}</p>
                {movie.user_review.is_spoiler && <span className={styles.spoilerTag}>Содержит спойлеры</span>}
                <div className={styles.reviewActions}>
                  <button
                    type="button"
                    className={styles.actionBtn}
                    disabled={reviewFieldsDisabled}
                    onClick={handleEditReview}
                  >
                    Редактировать
                  </button>
                  <button
                    type="button"
                    className={`${styles.actionBtn} ${styles.danger}`}
                    disabled={reviewFieldsDisabled}
                    onClick={handleDeleteReview}
                  >
                    {pendingReviewAction === 'delete' ? 'Удаляем…' : 'Удалить'}
                  </button>
                </div>
              </div>
            ) : (
              <form onSubmit={handleSaveReview} className={styles.reviewForm} aria-busy={pendingReviewAction === 'save'}>
                <textarea
                  className={styles.textarea}
                  placeholder="Напишите вашу рецензию..."
                  value={reviewText}
                  onChange={(e) => setReviewText(e.target.value)}
                  rows={4}
                  disabled={reviewFieldsDisabled}
                />
                <label className={styles.checkboxLabel}>
                  <input
                    type="checkbox"
                    checked={isSpoiler}
                    disabled={reviewFieldsDisabled}
                    onChange={(e) => setIsSpoiler(e.target.checked)}
                  />
                  Содержит спойлеры
                </label>
                <div className={styles.formButtons}>
                  <button
                    type="submit"
                    className={styles.saveBtn}
                    disabled={reviewFieldsDisabled || (!isDemo && (!reviewText.trim() || unchangedReview))}
                  >
                    {pendingReviewAction === 'save' ? 'Сохраняем…' : 'Сохранить'}
                  </button>
                  {movie.user_review && (
                    <button
                      type="button"
                      className={styles.cancelBtn}
                      disabled={reviewFieldsDisabled}
                      onClick={() => {
                        setIsEditingReview(false);
                        setReviewError('');
                      }}
                    >
                      Отмена
                    </button>
                  )}
                </div>
                {!isDemo && !accessToken && (
                  <Link to="/login" className={styles.actionBtn}>Войти, чтобы написать рецензию</Link>
                )}
              </form>
            )}
            {reviewError && <p className={styles.reviewError} role="alert">{reviewError}</p>}
          </div>
        </div>

        {/* Правая колонка: Рецензии других и Рецензии критиков */}
        <div className={styles.rightColumn}>
          {/* Рецензии других пользователей */}
          <UserReviewList
            key={`${source}:${movie.id}:${reviewRevision}`}
            movieId={movie.id}
            demoReviews={isDemo ? movie.reviews ?? [] : undefined}
            currentUsername={isDemo ? undefined : user?.username}
            onOwnReview={restoreOwnReview}
          />

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
