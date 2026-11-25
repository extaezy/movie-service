import React, { useCallback, useState, useEffect, useRef } from 'react';
import { isAxiosError } from 'axios';
import { Link, useNavigate, useParams } from 'react-router-dom';
import { Spinner } from '../../components/Spinner/Spinner';
import { ErrorState } from '../../components/ErrorState/ErrorState';
import { MovieCard } from '../../components/MovieCard/MovieCard';
import { useAuth } from '../../context/AuthContext';
import { useToast } from '../../context/ToastContext';
import { getApiErrorMessage } from '../../api/errors';
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
  updateMovieRatingApi,
  updateMovieReviewApi,
} from '../../api/movieDetail';
import {
  getDiscoverMoviesApi,
  getLocalMoviesApi,
  getTmdbPosterUrl,
} from '../../api/movies';
import type { MovieDetail, Review } from '../../api/movieDetail';
import { MovieListButtons } from './MovieListButtons';
import { UserReviewList } from './UserReviewList';
import styles from './Movie.module.css';

interface MoviePageProps {
  source?: 'catalog' | 'tmdb' | 'demo';
}

interface RecommendedCardItem {
  id: string;
  title: string;
  poster_url: string;
  year?: number;
  to: string;
}

type SavedReview = NonNullable<MovieDetail['user_review']>;
type ReviewAction = 'save' | 'delete';
type MoviePageTab = 'overview' | 'recommended';

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
  const [savedRating, setSavedRating] = useState<number | null>(null);
  const [ratingPending, setRatingPending] = useState(false);
  const [ratingError, setRatingError] = useState('');
  const ratingSubmission = useRef<AbortController | null>(null);

  const [activeTab, setActiveTab] = useState<MoviePageTab>('overview');
  const [recommended, setRecommended] = useState<RecommendedCardItem[]>([]);
  const [recommendedLoading, setRecommendedLoading] = useState(false);

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
    setReviewError('');
    setIsEditingReview(false);
    setPendingReviewAction(null);
    setActiveTab('overview');

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
      reviewSubmission.current?.abort();
      reviewSubmission.current = null;
    };
  }, [id, source, isDemo, navigate, attempt]);

  useEffect(() => {
    if (!movie || isDemo) {
      setRecommended([]);
      return;
    }

    const controller = new AbortController();
    const { signal } = controller;
    setRecommendedLoading(true);

const loadRecommendations = async () => {
      try {
        const currentId = String(movie.id);
        const currentGenreNames = new Set(
          (movie.catalog_genres ?? []).map((g) => g.name.toLowerCase()),
        );

        const items: RecommendedCardItem[] = [];
        const usedIds = new Set<string>([currentId]);

        const localPage = await getLocalMoviesApi({ page: 1, sort: 'release_date_desc' }, signal);
        const sortedLocal = [...localPage.results].sort((a, b) => {
          const aMatch = a.genres.some((g) => currentGenreNames.has(g.name.toLowerCase())) ? 1 : 0;
          const bMatch = b.genres.some((g) => currentGenreNames.has(g.name.toLowerCase())) ? 1 : 0;
          return bMatch - aMatch;
        });

        let matchedTmdbGenreId: number | undefined;
        for (const item of localPage.results) {
          const foundGenre = item.genres.find((g) => currentGenreNames.has(g.name.toLowerCase()));
          if (foundGenre?.tmdb_id) {
            matchedTmdbGenreId = foundGenre.tmdb_id;
            break;
          }
        }

        for (const item of sortedLocal) {
          const itemId = String(item.id);
          if (usedIds.has(itemId)) continue;
          usedIds.add(itemId);
          items.push({
            id: itemId,
            title: item.title,
            poster_url: getTmdbPosterUrl(item.poster_path),
            year: item.release_date ? Number(item.release_date.slice(0, 4)) : undefined,
            to: `/movies/${itemId}`,
          });
          if (items.length >= 10) break;
        }

        if (items.length < 10) {
          const discoverPage = await getDiscoverMoviesApi(
            {
              page: 1,
              tmdb_genre_id: matchedTmdbGenreId,
              sort: 'popularity_desc',
            },
            signal,
          );

          for (const tmdbItem of discoverPage.results) {
            const tmdbId = String(tmdbItem.tmdb_id);
            if (usedIds.has(`tmdb-${tmdbId}`)) continue;
            usedIds.add(`tmdb-${tmdbId}`);
            items.push({
              id: `tmdb-${tmdbId}`,
              title: tmdbItem.title,
              poster_url: getTmdbPosterUrl(tmdbItem.poster_path),
              year: tmdbItem.release_date ? Number(tmdbItem.release_date.slice(0, 4)) : undefined,
              to: `/tmdb/${tmdbId}`,
            });
            if (items.length >= 10) break;
          }
        }

        if (!signal.aborted) {
          setRecommended(items);
        }
      } catch {
        if (!signal.aborted) {
          setRecommended([]);
        }
      } finally {
        if (!signal.aborted) {
          setRecommendedLoading(false);
        }
      }
    };

    loadRecommendations();
    return () => controller.abort();
  }, [movie, isDemo]);

  useEffect(() => {
    setSavedRating(null);
    setRatingPending(false);
    setRatingError('');
    return () => {
      ratingSubmission.current?.abort();
      ratingSubmission.current = null;
    };
  }, [id, source, accessToken, attempt]);

  const handleRate = async (rating: number | null) => {
    if (!movie || (!isDemo && !accessToken) || ratingSubmission.current) return;
    const movieId = movie.id;
    const submission = new AbortController();
    const { signal } = submission;
    ratingSubmission.current = submission;
    setRatingPending(true);
    setRatingError('');

    try {
      let score = rating;
      if (isDemo) {
        await rateMovieApi(movieId, rating);
      } else if (accessToken) {
        score = await updateMovieRatingApi(movieId, rating, accessToken, signal);
      }
      if (signal.aborted) return;

      if (isDemo) {
        setMovie((previous) => previous?.id === movieId ? { ...previous, user_rating: score } : previous);
      } else {
        setSavedRating(score);
      }
      showToast(score === null ? 'Оценка удалена' : `Оценка ${score} сохранена`);

      if (!isDemo) {
        try {
          const { average_rating, ratings_count } = await getMovieDetailApi(movieId, signal);
          if (!signal.aborted) {
            setMovie((previous) => previous?.id === movieId
              ? { ...previous, average_rating, ratings_count }
              : previous);
          }
        } catch {
          if (!signal.aborted) {
            setRatingError('Не удалось обновить общий рейтинг. Обновите страницу, чтобы увидеть актуальные данные.');
          }
        }
      }
    } catch (requestError) {
      if (!signal.aborted) {
        const fallback = rating === null ? 'Не удалось удалить оценку.' : 'Не удалось сохранить оценку.';
        setRatingError(getApiErrorMessage(requestError, fallback));
      }
    } finally {
      if (ratingSubmission.current === submission) {
        ratingSubmission.current = null;
        setRatingPending(false);
      }
    }
  };

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
  const selectedRating = isDemo ? movie.user_rating : savedRating;
  const ratingDisabled = ratingPending || (!isDemo && !accessToken);

  return (
    <div className={styles.container}>
      {/* Hero-блок с замыленным постером на фоне */}
      <div className={styles.heroSection}>
        {movie.poster_url && (
          <div
            className={styles.heroBackdrop}
            style={{ backgroundImage: `url(${movie.poster_url})` }}
            aria-hidden="true"
          />
        )}
        <div className={styles.heroOverlay} aria-hidden="true" />

        <div className={styles.heroContent}>
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
              <div className={styles.ratingsRow}>
                <div className={styles.ratingBadge}>
                  <span className={styles.ratingBadgeValue}>
                    {movie.tmdb_vote_average == null
                      ? '—'
                      : ratingFormat.format(movie.tmdb_vote_average)}
                  </span>
                  <span className={styles.ratingBadgeLabel}>
                    TMDB {movie.tmdb_vote_count ? `(${movie.tmdb_vote_count})` : ''}
                  </span>
                </div>
                <div className={styles.ratingBadge}>
                  <span className={`${styles.ratingBadgeValue} ${styles.localRatingValue}`}>
                    {movie.average_rating == null
                      ? '—'
                      : ratingFormat.format(movie.average_rating)}
                  </span>
                  <span className={styles.ratingBadgeLabel}>
                    MOVIE SERVICE {movie.ratings_count ? `(${movie.ratings_count})` : ''}
                  </span>
                </div>
              </div>
            )}

            {/* Блок добавления в список */}
            {isDemo ? (
              <div className={styles.statusTabs}>
                <button
                  type="button"
                  className={`${styles.statusBtn} ${movie.user_status === 'watchlist' ? styles.activeStatus : ''}`}
                  onClick={() => handleStatusChange('watchlist')}
                >
                  Планирую посмотреть
                </button>
                <button
                  type="button"
                  className={`${styles.statusBtn} ${movie.user_status === 'watched' ? styles.activeStatus : ''}`}
                  onClick={() => handleStatusChange('watched')}
                >
                  Просмотрено
                </button>
                <button
                  type="button"
                  className={`${styles.statusBtn} ${movie.user_status === 'favorite' ? styles.activeStatus : ''}`}
                  onClick={() => handleStatusChange('favorite')}
                >
                  Любимое
                </button>
              </div>
            ) : (
              <MovieListButtons
                key={`${movie.id}:${user?.username ?? ''}:${accessToken ?? ''}`}
                movieId={movie.id}
                username={user?.username}
                accessToken={accessToken}
              />
            )}
          </div>
        </div>
      </div>

      {/* Вкладки под шапкой фильма */}
      <div className={styles.pageTabs} role="tablist" aria-label="Разделы страницы фильма">
        <button
          type="button"
          role="tab"
          aria-selected={activeTab === 'overview'}
          className={`${styles.pageTabBtn} ${activeTab === 'overview' ? styles.pageTabActive : ''}`}
          onClick={() => setActiveTab('overview')}
        >
          ОЦЕНКИ И РЕЦЕНЗИИ
        </button>
        <button
          type="button"
          role="tab"
          aria-selected={activeTab === 'recommended'}
          className={`${styles.pageTabBtn} ${activeTab === 'recommended' ? styles.pageTabActive : ''}`}
          onClick={() => setActiveTab('recommended')}
        >
          РЕКОМЕНДОВАННЫЕ ФИЛЬМЫ
          {recommended.length > 0 && (
            <span className={styles.tabCountBadge}>{recommended.length}</span>
          )}
        </button>
      </div>

      {activeTab === 'recommended' ? (
        <section className={styles.recommendedSection}>
          {recommendedLoading ? (
            <Spinner />
          ) : recommended.length > 0 ? (
            <div className={styles.recommendedGrid}>
              {recommended.map((item) => (
                <MovieCard
                  key={item.id}
                  movie={{
                    id: item.id,
                    title: item.title,
                    poster_url: item.poster_url,
                    year: item.year,
                    is_favorite: false,
                  }}
                  to={item.to}
                />
              ))}
            </div>
          ) : (
            <div className={styles.card}>
              <p className={styles.emptyText}>Рекомендованные фильмы пока не найдены.</p>
            </div>
          )}
        </section>
      ) : (
        <div className={styles.contentGrid}>
          {/* Левая колонка: Оценка и Своя рецензия */}
          <div className={styles.leftColumn}>
            {/* Блок "Моя оценка" */}
            <div className={styles.card} aria-busy={ratingPending}>
              <h3 className={styles.cardTitle}>Моя оценка</h3>
              <div className={styles.ratingSelector}>
                {Array.from({ length: 10 }, (_, i) => i + 1).map((num) => (
                  <button
                    key={num}
                    type="button"
                    className={`${styles.rateBtn} ${selectedRating === num ? styles.activeRate : ''}`}
                    aria-pressed={selectedRating === num}
                    disabled={ratingDisabled}
                    onClick={() => handleRate(num)}
                  >
                    {num}
                  </button>
                ))}
              </div>
              {(isDemo ? Boolean(selectedRating) : Boolean(accessToken)) && (
                <button
                  type="button"
                  className={styles.deleteRateBtn}
                  disabled={ratingDisabled}
                  onClick={() => handleRate(null)}
                >
                  Удалить оценку
                </button>
              )}
              {!isDemo && !accessToken && (
                <Link to="/login" className={styles.actionBtn}>Войти, чтобы поставить оценку</Link>
              )}
              {ratingPending && <p role="status">Обновляем оценку…</p>}
              {ratingError && <p className={styles.reviewError} role="alert">{ratingError}</p>}
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
      )}
    </div>
  );
};