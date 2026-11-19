import { useEffect, useState } from 'react';
import { getApiErrorMessage } from '../../api/errors';
import { getMovieReviewsApi } from '../../api/movieDetail';
import type { Review } from '../../api/movieDetail';
import { ErrorState } from '../../components/ErrorState/ErrorState';
import { Spinner } from '../../components/Spinner/Spinner';
import styles from './Movie.module.css';

interface UserReviewListProps {
  movieId: string;
  demoReviews?: Review[];
  currentUsername?: string;
  onOwnReview: (movieId: string, review: Review) => void;
}

interface LoadedReviews {
  page: number;
  totalPages: number;
  reviews: Review[];
}

export const UserReviewList = ({ movieId, demoReviews, currentUsername, onOwnReview }: UserReviewListProps) => {
  const isDemo = demoReviews !== undefined;
  const [loaded, setLoaded] = useState<LoadedReviews>({ page: 0, totalPages: 0, reviews: [] });
  const [request, setRequest] = useState({ page: 1 });
  const [loading, setLoading] = useState(!isDemo);
  const [error, setError] = useState('');

  useEffect(() => {
    if (isDemo) return;
    const controller = new AbortController();
    const { signal } = controller;

    getMovieReviewsApi(movieId, request.page, signal)
      .then((data) => {
        if (signal.aborted) return;
        const ownReview = data.reviews.find((review) => review.author.username === currentUsername);
        if (ownReview) onOwnReview(movieId, ownReview);

        setLoaded((previous) => {
          const previousIds = new Set(previous.reviews.map((review) => review.id));
          const newReviews = data.reviews.filter((review) => !previousIds.has(review.id));
          return { ...data, reviews: [...previous.reviews, ...newReviews] };
        });
      })
      .catch((requestError) => {
        if (!signal.aborted) {
          setError(getApiErrorMessage(requestError, 'Не удалось загрузить рецензии.'));
        }
      })
      .finally(() => {
        if (!signal.aborted) setLoading(false);
      });

    return () => controller.abort();
  }, [currentUsername, isDemo, movieId, onOwnReview, request]);

  const loadPage = (page: number) => {
    setLoading(true);
    setError('');
    setRequest({ page });
  };
  const reviews = demoReviews ?? loaded.reviews;

  return (
    <div className={styles.card} aria-busy={loading}>
      <h3 className={styles.cardTitle}>Рецензии пользователей</h3>
      {reviews.length > 0 && (
        <div className={styles.reviewsList}>
          {reviews.map((review) => (
            <div key={review.id} className={styles.reviewCard}>
              <div className={styles.reviewHeader}>
                <span className={styles.authorName}>{review.author.display_name || review.author.username}</span>
                <time className={styles.reviewDate} dateTime={review.created_at}>
                  {new Date(review.created_at).toLocaleDateString()}
                </time>
              </div>
              {review.is_spoiler && <span className={styles.spoilerTag}>Спойлер</span>}
              <p className={styles.reviewBody}>{review.text}</p>
            </div>
          ))}
        </div>
      )}
      {reviews.length === 0 && !loading && !error && (
        <p className={styles.emptyText}>Пока нет рецензий от пользователей</p>
      )}
      {loading && (
        <div role="status" aria-label="Загрузка рецензий">
          <Spinner />
        </div>
      )}
      {error && <ErrorState message={error} onRetry={() => loadPage(request.page)} />}
      {loaded.page < loaded.totalPages && !error && (
        <button
          type="button"
          className={styles.actionBtn}
          disabled={loading}
          onClick={() => loadPage(loaded.page + 1)}
        >
          Показать ещё
        </button>
      )}
    </div>
  );
};
