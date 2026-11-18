import React, { useState, useEffect } from 'react';
import { MovieCard } from '../../components/MovieCard/MovieCard';
import { Spinner } from '../../components/Spinner/Spinner';
import { EmptyState } from '../../components/EmptyState/EmptyState';
import { ErrorState } from '../../components/ErrorState/ErrorState';
import { getApiErrorMessage } from '../../api/errors';
import { getDiscoverMoviesApi, getTmdbPosterUrl, searchMoviesApi } from '../../api/movies';
import type { TmdbGenre, TmdbMovie, TmdbSort } from '../../api/movies';
import styles from './Catalog.module.css';

// Загрузка жанров при монтировании
// если жанры не загрузились, не критично для каталога
const tmdbGenres: TmdbGenre[] = [
  { tmdb_id: 28, name: 'Боевик' },
  { tmdb_id: 37, name: 'Вестерн' },
  { tmdb_id: 10752, name: 'Военный' },
  { tmdb_id: 9648, name: 'Детектив' },
  { tmdb_id: 99, name: 'Документальный' },
  { tmdb_id: 18, name: 'Драма' },
  { tmdb_id: 36, name: 'История' },
  { tmdb_id: 35, name: 'Комедия' },
  { tmdb_id: 80, name: 'Криминал' },
  { tmdb_id: 10749, name: 'Мелодрама' },
  { tmdb_id: 10402, name: 'Музыка' },
  { tmdb_id: 16, name: 'Мультфильм' },
  { tmdb_id: 12, name: 'Приключения' },
  { tmdb_id: 10751, name: 'Семейный' },
  { tmdb_id: 10770, name: 'Телефильм' },
  { tmdb_id: 53, name: 'Триллер' },
  { tmdb_id: 27, name: 'Ужасы' },
  { tmdb_id: 878, name: 'Фантастика' },
  { tmdb_id: 14, name: 'Фэнтези' },
];

export const Catalog: React.FC = () => {
  const [movies, setMovies] = useState<TmdbMovie[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState('');
  const [catalogAttempt, setCatalogAttempt] = useState(0);

  // Фильтры и поиск
  const [searchQuery, setSearchQuery] = useState<string>('');
  const [debouncedSearch, setDebouncedSearch] = useState<string>('');
  const [selectedGenre, setSelectedGenre] = useState<string>('');
  const [yearFilter, setYearFilter] = useState<string>('');
  const [sort, setSort] = useState<TmdbSort>('popularity_desc');

  // Пагинация
  const [page, setPage] = useState<number>(1);
  const [totalPages, setTotalPages] = useState<number>(1);

  const searching = Boolean(debouncedSearch);
  const year = yearFilter ? Number(yearFilter) : undefined;
  const invalidYear = !searching && year !== undefined && (!Number.isInteger(year) || year < 1 || year > 9999);
  const invalidSearch = Array.from(debouncedSearch).length > 200;
  let validationError = '';
  if (invalidSearch) validationError = 'Введите до 200 символов для поиска.';
  if (invalidYear) validationError = 'Введите целый год от 1 до 9999.';

  // Debounce для поиска (300ms)
  useEffect(() => {
    const query = searchQuery.trim();
    if (query === debouncedSearch) return;
    const timer = setTimeout(() => {
      setDebouncedSearch(query);
      setPage(1); // сброс на первую страницу при новом поиске
    }, 300);
    return () => clearTimeout(timer);
  }, [searchQuery, debouncedSearch]);

  // Загрузка фильмов
  useEffect(() => {
    if (validationError) {
      setLoading(false);
      return;
    }
    const controller = new AbortController();
    setLoading(true);
    setError('');

    const request = debouncedSearch
      ? searchMoviesApi(debouncedSearch, page, controller.signal)
      : getDiscoverMoviesApi({
          page,
          tmdb_genre_id: selectedGenre ? Number(selectedGenre) : undefined,
          year,
          sort,
        }, controller.signal);

    request
      .then((data) => {
        if (controller.signal.aborted) return;
        setMovies(data.results);
        setTotalPages(Math.min(data.total_pages, 500));
      })
      .catch((requestError) => {
        if (!controller.signal.aborted) {
          setError(getApiErrorMessage(requestError, 'Не удалось загрузить фильмы.'));
        }
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false);
      });

    return () => controller.abort();
  }, [debouncedSearch, selectedGenre, year, sort, page, catalogAttempt, validationError]);

  const retryCatalog = () => setCatalogAttempt((attempt) => attempt + 1);

  return (
    <div className={styles.container}>
      <div className={styles.filtersBar}>
        <input
          type="text"
          className={styles.searchInput}
          placeholder="Поиск по названию..."
          aria-label="Поиск по названию"
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
        />
        <select
          className={styles.select}
          aria-label="Жанр"
          disabled={searching}
          value={selectedGenre}
          onChange={(e) => {
            setSelectedGenre(e.target.value);
            setPage(1);
          }}
        >
          <option value="">Все жанры</option>
          {tmdbGenres.map((genre) => (
            <option key={genre.tmdb_id} value={genre.tmdb_id}>
              {genre.name}
            </option>
          ))}
        </select>
        <input
          type="number"
          className={styles.yearInput}
          placeholder="Год"
          aria-label="Год выпуска"
          min={1}
          max={9999}
          disabled={searching}
          value={yearFilter}
          onChange={(e) => {
            setYearFilter(e.target.value);
            setPage(1);
          }}
        />
        <select
          className={styles.select}
          aria-label="Сортировка"
          disabled={searching}
          value={sort}
          onChange={(e) => {
            setSort(e.target.value as TmdbSort);
            setPage(1);
          }}
        >
          <option value="popularity_desc">По популярности</option>
          <option value="release_date_desc">Сначала новые</option>
          <option value="release_date_asc">Сначала старые</option>
        </select>
      </div>

      {loading ? (
        <Spinner />
      ) : validationError ? (
        <ErrorState message={validationError} />
      ) : error ? (
        <ErrorState message={error} onRetry={retryCatalog} />
      ) : (
        <>
          {movies.length === 0 ? (
            <EmptyState message="Ничего не найдено" />
          ) : (
            <div className={styles.grid}>
              {movies.map((movie) => (
                <MovieCard
                  key={movie.tmdb_id}
                  to={`/movies/tmdb/${movie.tmdb_id}`}
                  movie={{
                    id: String(movie.tmdb_id),
                    title: movie.title,
                    poster_url: getTmdbPosterUrl(movie.poster_path),
                    year: movie.release_date ? Number(movie.release_date.slice(0, 4)) : undefined,
                  }}
                />
              ))}
            </div>
          )}

          {(totalPages > 1 || page > 1) && (
            <div className={styles.pagination}>
              <button
                className={styles.pageBtn}
                disabled={page === 1}
                onClick={() => setPage((p) => Math.max(p - 1, 1))}
              >
                Назад
              </button>
              <span className={styles.pageInfo}>
                {page} из {Math.max(page, totalPages)}
              </span>
              <button
                className={styles.pageBtn}
                disabled={page >= totalPages}
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
