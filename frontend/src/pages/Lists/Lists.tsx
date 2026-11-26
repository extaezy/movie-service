import React, { useState, useEffect, useCallback } from 'react';
import { useParams, useNavigate, Navigate } from 'react-router-dom';
import { MovieCard } from '../../components/MovieCard/MovieCard';
import { Spinner } from '../../components/Spinner/Spinner';
import { EmptyState } from '../../components/EmptyState/EmptyState';
import { ErrorState } from '../../components/ErrorState/ErrorState';
import { useToast } from '../../context/ToastContext';
import { getUserListApi } from '../../api/lists';
import type { ListType } from '../../api/lists';
import { toggleFavoriteApi } from '../../api/movies';
import { setMovieStatusApi, rateMovieApi } from '../../api/movieDetail';
import type { Movie } from '../../types';
import styles from './Lists.module.css';

const VALID_TYPES: ListType[] = ['watchlist', 'watched', 'favorite'];

const TAB_LABELS: Record<ListType, string> = {
  watchlist: 'Планирую посмотреть',
  watched: 'Просмотрено',
  favorite: 'Любимое',
};

export const ListTabs = ({ currentType }: { currentType: ListType }) => {
  const navigate = useNavigate();
  return (
    <div className={styles.tabsBar}>
      {VALID_TYPES.map((tabType) => (
        <button
          type="button"
          key={tabType}
          className={`${styles.tabBtn} ${currentType === tabType ? styles.activeTab : ''}`}
          onClick={() => navigate(`/lists/${tabType}`)}
        >
          {TAB_LABELS[tabType]}
        </button>
      ))}
    </div>
  );
};

export const Lists: React.FC = () => {
  const { type } = useParams<{ type: string }>();
  const { showToast } = useToast();

  const [movies, setMovies] = useState<Movie[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<boolean>(false);
  const [page, setPage] = useState<number>(1);
  const [totalPages, setTotalPages] = useState<number>(1);
  const [ratingMovieId, setRatingMovieId] = useState<string | null>(null);

  const currentType = type as ListType;

  const fetchList = useCallback(async () => {
    if (!VALID_TYPES.includes(currentType)) return;
    setLoading(true);
    setError(false);
    try {
      const data = await getUserListApi(currentType, page, 12);
      setMovies(data.items);
      setTotalPages(data.pages || 1);
    } catch {
      setError(true);
    } finally {
      setLoading(false);
    }
  }, [currentType, page]);

  useEffect(() => {
    setPage(1);
    setRatingMovieId(null);
  }, [currentType]);

  useEffect(() => {
    fetchList();
  }, [fetchList]);

  if (!VALID_TYPES.includes(currentType)) {
    return <Navigate to="/lists/watchlist" replace />;
  }

  const handleToggleFavorite = async (id: string) => {
    try {
      const res = await toggleFavoriteApi(id);
      if (currentType === 'favorite' && !res.is_favorite) {
        setMovies((prev) => prev.filter((m) => m.id !== id));
      } else {
        setMovies((prev) =>
          prev.map((m) => (m.id === id ? { ...m, is_favorite: res.is_favorite } : m))
        );
      }
      showToast(res.is_favorite ? 'Добавлено в избранное' : 'Удалено из избранного');
    } catch {
      showToast('Не удалось обновить избранное');
    }
  };

  // Перенос из watchlist в watched с возможностью отмены
  const handleMarkAsWatched = async (movie: Movie) => {
    try {
      await setMovieStatusApi(movie.id, 'watched');
      setMovies((prev) => prev.filter((m) => m.id !== movie.id));

      showToast('Фильм перенесён', 'Отменить', async () => {
        try {
          await setMovieStatusApi(movie.id, 'watchlist');
          fetchList();
        } catch {
          showToast('Не удалось отменить действие');
        }
      });
    } catch {
      showToast('Не удалось обновить статус');
    }
  };

  // Оценка фильма из списка watched
  const handleRateMovie = async (movieId: string, rating: number) => {
    try {
      await rateMovieApi(movieId, rating);
      setMovies((prev) =>
        prev.map((m) => (m.id === movieId ? { ...m, rating } : m))
      );
      setRatingMovieId(null);
      showToast(`Оценка ${rating} сохранена`);
    } catch {
      showToast('Не удалось сохранить оценку');
    }
  };

  return (
    <div className={styles.container}>
      {/* Табы переключения списков */}
      <ListTabs currentType={currentType} />

      {loading ? (
        <Spinner />
      ) : error ? (
        <ErrorState onRetry={fetchList} />
      ) : movies.length === 0 ? (
        <EmptyState message="Список пуст" />
      ) : (
        <>
          <div className={styles.grid}>
            {movies.map((movie) => (
              <div key={movie.id} className={styles.cardItem}>
                <MovieCard movie={movie} to={`/demo/movies/${movie.id}`} onToggleFavorite={handleToggleFavorite} />

                {/* Действие для "Планирую посмотреть" */}
                {currentType === 'watchlist' && (
                  <button
                    className={styles.actionBtn}
                    onClick={() => handleMarkAsWatched(movie)}
                  >
                    Отметить просмотренным
                  </button>
                )}

                {/* Действие для "Просмотрено" */}
                {currentType === 'watched' && (
                  <div className={styles.ratingBox}>
                    {ratingMovieId === movie.id ? (
                      <div className={styles.ratingPicker}>
                        {Array.from({ length: 10 }, (_, i) => i + 1).map((num) => (
                          <button
                            key={num}
                            className={`${styles.rateNumBtn} ${movie.rating === num ? styles.activeRate : ''}`}
                            onClick={() => handleRateMovie(movie.id, num)}
                          >
                            {num}
                          </button>
                        ))}
                      </div>
                    ) : (
                      <button
                        className={styles.actionBtn}
                        onClick={() => setRatingMovieId(movie.id)}
                      >
                        {movie.rating ? `Ваша оценка: ★ ${movie.rating}` : 'Поставить оценку'}
                      </button>
                    )}
                  </div>
                )}
              </div>
            ))}
          </div>

          {totalPages > 1 && (
            <div className={styles.pagination}>
              <button
                className={styles.pageBtn}
                disabled={page === 1}
                onClick={() => setPage((p) => Math.max(p - 1, 1))}
              >
                Назад
              </button>
              <span className={styles.pageInfo}>
                {page} из {totalPages}
              </span>
              <button
                className={styles.pageBtn}
                disabled={page === totalPages}
                onClick={() => setPage((p) => Math.min(p + 1, totalPages))}
              >
                Вперёд
              </button>
            </div>
          )}
        </>
      )}
    </div>
  );
};
