import React, { useState, useEffect, useCallback } from 'react';
import { useParams, Link } from 'react-router-dom';
import { Spinner } from '../../components/Spinner/Spinner';
import { ErrorState } from '../../components/ErrorState/ErrorState';
import { useToast } from '../../context/ToastContext';
import {
  getMovieDetailApi,
  rateMovieApi,
  setMovieStatusApi,
  saveReviewApi,
  deleteReviewApi,
} from '../../api/movieDetail';
import type { MovieDetail } from '../../api/movieDetail';
import styles from './Movie.module.css';

export const MoviePage: React.FC = () => {
  const { id } = useParams<{ id: string }>();
  const { showToast } = useToast();

  const [movie, setMovie] = useState<MovieDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);

  const [reviewText, setReviewText] = useState('');
  const [isSpoiler, setIsSpoiler] = useState(false);
  const [submittingReview, setSubmittingReview] = useState(false);
  const [revealedSpoilers, setRevealedSpoilers] = useState<Record<string, boolean>>({});

  const fetchDetail = useCallback(async () => {
    if (!id) return;
    setLoading(true);
    setError(false);
    try {
      const data = await getMovieDetailApi(id);
      setMovie(data);
      if (data.user_review) {
        setReviewText(data.user_review.text);
        setIsSpoiler(data.user_review.is_spoiler);
      }
    } catch {
      setError(true);
    } finally {
      setLoading(false);
    }
  }, [id]);

  useEffect(() => {
    fetchDetail();
  }, [fetchDetail]);

  const handleRate = async (rating: number | null) => {
    if (!movie) return;
    try {
      await rateMovieApi(movie.id, rating);
      setMovie({ ...movie, user_rating: rating });
      showToast(rating ? `Ваша оценка: ${rating}/10` : 'Оценка удалена');
    } catch {
      showToast('Не удалось сохранить оценку');
    }
  };

  const handleStatusChange = async (
    status: 'watchlist' | 'watched' | 'favorite' | null
  ) => {
    if (!movie) return;
    const nextStatus = movie.user_status === status ? null : status;
    try {
      await setMovieStatusApi(movie.id, nextStatus);
      setMovie({ ...movie, user_status: nextStatus });
      showToast(nextStatus ? 'Статус обновлён' : 'Удалено из списков');
    } catch {
      showToast('Не удалось обновить статус');
    }
  };

  const handleReviewSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!movie || !reviewText.trim()) return;
    setSubmittingReview(true);
    try {
      await saveReviewApi(movie.id, reviewText.trim(), isSpoiler);
      showToast('Рецензия сохранена');
      fetchDetail();
    } catch {
      showToast('Ошибка при сохранении рецензии');
    } finally {
      setSubmittingReview(false);
    }
  };

  const handleReviewDelete = async () => {
    if (!movie) return;
    try {
      await deleteReviewApi(movie.id);
      setReviewText('');
      setIsSpoiler(false);
      showToast('Рецензия удалена');
      fetchDetail();
    } catch {
      showToast('Не удалось удалить рецензию');
    }
  };

  if (loading) return <Spinner />;
  if (error || !movie) return <ErrorState onRetry={fetchDetail} />;

  const kpScore = (movie.kp_rating || 8.6).toFixed(1);
  const imdbScore = (movie.imdb_rating || 8.4).toFixed(1);
  const myScore = movie.user_rating ? movie.user_rating.toFixed(1) : '—';

  return (
    <div className={styles.page}>
      {/* Полноширинный Hero-баннер */}
      <section className={styles.hero}>
        <div
          className={styles.heroBackdrop}
          style={{
            backgroundImage: `url(${movie.backdrop_url || movie.poster_url})`,
          }}
        />
        <div className={styles.heroGradient} />

        <div className={styles.heroInner}>
          <Link to="/" className={styles.backLink}>
            ‹ Каталог
          </Link>

          <div className={styles.heroMain}>
            <div className={styles.posterCard}>
              <img
                src={movie.poster_url}
                alt={movie.title}
                className={styles.poster}
              />
            </div>

            <div className={styles.heroInfo}>
              <span className={styles.categoryTag}>ФИЛЬМ</span>
              <h1 className={styles.title}>{movie.title}</h1>

              <div className={styles.metaLine}>
                <span>{movie.year}</span>
                <span>{movie.genres.join(', ')}</span>
                {movie.duration && <span>{movie.duration} мин</span>}
              </div>

              {/* Блок рейтингов как на референсе */}
              <div className={styles.ratingsGrid}>
                <div className={styles.ratingBlock}>
                  <span className={`${styles.ratingValue} ${styles.kpColor}`}>
                    {kpScore}
                  </span>
                  <span className={styles.ratingLabel}>КИНОПОИСК</span>
                </div>

                <div className={styles.ratingBlock}>
                  <span className={styles.ratingValue}>{imdbScore}</span>
                  <span className={styles.ratingLabel}>IMDB</span>
                </div>

                <div className={styles.ratingBlock}>
                  <span className={styles.ratingValue}>{myScore}</span>
                  <span className={styles.ratingLabel}>МОЯ ОЦЕНКА</span>
                </div>
              </div>

              {movie.description && (
                <p className={styles.description}>{movie.description}</p>
              )}

              {/* Pill-кнопки действий */}
              <div className={styles.heroButtons}>
                <button
                  type="button"
                  className={styles.whitePillBtn}
                  onClick={() => handleStatusChange('watched')}
                >
                  <span>▶</span>
                  {movie.user_status === 'watched' ? 'Просмотрено' : 'Смотреть'}
                </button>

                <button
                  type="button"
                  className={`${styles.glassPillBtn} ${
                    movie.user_status === 'favorite' ? styles.glassPillActive : ''
                  }`}
                  onClick={() => handleStatusChange('favorite')}
                >
                  <span className={styles.heartIcon}>♥</span>
                  {movie.user_status === 'favorite' ? 'В избранном' : 'В избранное'}
                </button>

                <button
                  type="button"
                  className={`${styles.glassPillBtn} ${
                    movie.user_status === 'watchlist' ? styles.glassPillActive : ''
                  }`}
                  onClick={() => handleStatusChange('watchlist')}
                >
                  {movie.user_status === 'watchlist' ? '✓ Буду смотреть' : '+ Буду смотреть'}
                </button>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* Нижняя рабочая зона: оценка 1-10 и рецензии */}
      <div className={styles.contentContainer}>
        <div className={styles.rateStrip}>
          <span className={styles.rateStripTitle}>Поставить свою оценку:</span>
          <div className={styles.scoreButtons}>
            {[1, 2, 3, 4, 5, 6, 7, 8, 9, 10].map((num) => (
              <button
                key={num}
                type="button"
                className={`${styles.scoreBtn} ${
                  movie.user_rating === num ? styles.scoreBtnActive : ''
                }`}
                onClick={() => handleRate(num)}
              >
                {num}
              </button>
            ))}
            {movie.user_rating && (
              <button
                type="button"
                className={styles.clearScoreBtn}
                onClick={() => handleRate(null)}
              >
                Сбросить
              </button>
            )}
          </div>
        </div>

        {/* Секция рецензий */}
        <section className={styles.reviewsSection}>
          <h2 className={styles.sectionHeading}>Рецензии зрителей</h2>

          <form onSubmit={handleReviewSubmit} className={styles.reviewForm}>
            <textarea
              className={styles.textarea}
              placeholder="Поделитесь впечатлениями о фильме..."
              value={reviewText}
              onChange={(e) => setReviewText(e.target.value)}
              rows={3}
            />
            <div className={styles.formFooter}>
              <label className={styles.spoilerLabel}>
                <input
                  type="checkbox"
                  checked={isSpoiler}
                  onChange={(e) => setIsSpoiler(e.target.checked)}
                />
                Содержит спойлеры
              </label>

              <div className={styles.formBtns}>
                {movie.user_review && (
                  <button
                    type="button"
                    className={styles.deleteBtn}
                    onClick={handleReviewDelete}
                  >
                    Удалить
                  </button>
                )}
                <button
                  type="submit"
                  className={styles.submitBtn}
                  disabled={submittingReview || !reviewText.trim()}
                >
                  {movie.user_review ? 'Обновить рецензию' : 'Опубликовать'}
                </button>
              </div>
            </div>
          </form>

          <div className={styles.reviewsList}>
            {movie.reviews.length === 0 ? (
              <p className={styles.noReviews}>Пока нет рецензий. Станьте первым!</p>
            ) : (
              movie.reviews.map((rev) => {
                const isHidden = rev.is_spoiler && !revealedSpoilers[rev.id];
                return (
                  <div key={rev.id} className={styles.reviewCard}>
                    <div className={styles.reviewHeader}>
                      <Link
                        to={`/profile/${rev.author.username}`}
                        className={styles.authorName}
                      >
                        {rev.author.display_name || rev.author.username}
                      </Link>
                      <span className={styles.reviewDate}>
                        {new Date(rev.created_at).toLocaleDateString()}
                      </span>
                    </div>

                    {isHidden ? (
                      <button
                        type="button"
                        className={styles.revealSpoilerBtn}
                        onClick={() =>
                          setRevealedSpoilers({ ...revealedSpoilers, [rev.id]: true })
                        }
                      >
                        ⚠ Рецензия содержит спойлер. Нажмите, чтобы показать
                      </button>
                    ) : (
                      <p className={styles.reviewText}>{rev.text}</p>
                    )}
                  </div>
                );
              })
            )}
          </div>
        </section>
      </div>
    </div>
  );
};