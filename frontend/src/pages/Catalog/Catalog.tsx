import React, { useState, useEffect, useCallback } from 'react';
import { MovieCard } from '../../components/MovieCard/MovieCard';
import { Spinner } from '../../components/Spinner/Spinner';
import { EmptyState } from '../../components/EmptyState/EmptyState';
import { ErrorState } from '../../components/ErrorState/ErrorState';
import { useToast } from '../../context/ToastContext';
import { getMoviesApi, getGenresApi, toggleFavoriteApi } from '../../api/movies';
import { setMovieStatusApi } from '../../api/movieDetail'; 
import type { Movie } from '../../types';
import styles from './Catalog.module.css';

export const Catalog: React.FC = () => {
  const [movies, setMovies] = useState<Movie[]>([]);
  const [genres, setGenres] = useState<string[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<boolean>(false);

  // Фильтры и поиск
  const [searchQuery, setSearchQuery] = useState<string>('');
  const [debouncedSearch, setDebouncedSearch] = useState<string>('');
  const [selectedGenre, setSelectedGenre] = useState<string>('');
  const [yearFilter, setYearFilter] = useState<string>('');

  // Пагинация
  const [page, setPage] = useState<number>(1);
  const [totalPages, setTotalPages] = useState<number>(1);

  const { showToast } = useToast();

  // Debounce для поиска (300ms)
  useEffect(() => {
    const timer = setTimeout(() => {
      setDebouncedSearch(searchQuery);
      setPage(1); // сброс на первую страницу при новом поиске
    }, 300);
    return () => clearTimeout(timer);
  }, [searchQuery]);

  // Загрузка жанров при монтировании
  useEffect(() => {
    getGenresApi()
      .then((data) => setGenres(data))
      .catch(() => {
        // если жанры не загрузились, не критично для каталога
      });
  }, []);

  // Загрузка фильмов
  const fetchMovies = useCallback(async () => {
    setLoading(true);
    setError(false);
    try {
      const data = await getMoviesApi({
        search: debouncedSearch || undefined,
        genre: selectedGenre || undefined,
        year: yearFilter ? Number(yearFilter) : undefined,
        page,
        limit: 12,
      });
      setMovies(data.items);
      setTotalPages(data.pages || 1);
    } catch {
      setError(true);
    } finally {
      setLoading(false);
    }
  }, [debouncedSearch, selectedGenre, yearFilter, page]);

  useEffect(() => {
    fetchMovies();
  }, [fetchMovies]);

  // Переключение избранного
  const handleToggleFavorite = async (id: string) => {
    try {
      const res = await toggleFavoriteApi(id);
      setMovies((prev) =>
        prev.map((movie) => (movie.id === id ? { ...movie, is_favorite: res.is_favorite } : movie))
      );
      showToast(res.is_favorite ? 'Добавлено в избранное' : 'Удалено из избранного');
    } catch {
      showToast('Не удалось обновить избранное');
    }
  };
  const handleAddToWatchlist = async (movieId: string) => {
  try {
    const target = movies.find((m) => m.id === movieId);
    const nextWatchlist = !target?.is_watchlist;
    await setMovieStatusApi(movieId, nextWatchlist ? 'watchlist' : null);
    setMovies((prev) =>
      prev.map((m) =>
        m.id === movieId ? { ...m, is_watchlist: nextWatchlist } : m
      )
    );
    showToast(nextWatchlist ? 'Добавлено в «Буду смотреть»' : 'Удалено из списка');
  } catch {
    showToast('Не удалось обновить список');
  }
};
  return (
    <div className={styles.container}>
      <div className={styles.filtersBar}>
        <input
          type="text"
          className={styles.searchInput}
          placeholder="Поиск по названию..."
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
        />
        <select
          className={styles.select}
          value={selectedGenre}
          onChange={(e) => {
            setSelectedGenre(e.target.value);
            setPage(1);
          }}
        >
          <option value="">Все жанры</option>
          {genres.map((genre) => (
            <option key={genre} value={genre}>
              {genre}
            </option>
          ))}
        </select>
        <input
          type="number"
          className={styles.yearInput}
          placeholder="Год"
          value={yearFilter}
          onChange={(e) => {
            setYearFilter(e.target.value);
            setPage(1);
          }}
        />
      </div>

      {loading ? (
        <Spinner />
      ) : error ? (
        <ErrorState onRetry={fetchMovies} />
      ) : movies.length === 0 ? (
        <EmptyState message="Ничего не найдено" />
      ) : (
        <>
          <div className={styles.grid}>
            {movies.map((movie) => (
              <MovieCard key={movie.id} 
               movie={movie} 
               onToggleFavorite={handleToggleFavorite}
               onAddToWatchlist={handleAddToWatchlist}
               />
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
                Вперед
              </button>
            </div>
          )}
        </>
      )}
    </div>
  );
};