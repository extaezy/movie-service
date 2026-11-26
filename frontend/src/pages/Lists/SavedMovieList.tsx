import { useEffect, useRef, useState } from 'react';
import type { FormEvent } from 'react';
import { useSearchParams } from 'react-router-dom';
import { getApiErrorMessage } from '../../api/errors';
import { getMovieListApi, removeMovieListEntryApi } from '../../api/lists';
import type { ListType, MovieListPage } from '../../api/lists';
import { getTmdbPosterUrl } from '../../api/movies';
import { EmptyState } from '../../components/EmptyState/EmptyState';
import { ErrorState } from '../../components/ErrorState/ErrorState';
import { MovieCard } from '../../components/MovieCard/MovieCard';
import { Spinner } from '../../components/Spinner/Spinner';
import { useAuth } from '../../context/AuthContext';
import { useToast } from '../../context/ToastContext';
import { ListTabs } from './Lists';
import styles from './Lists.module.css';

export const SavedMovieList = ({ listType }: { listType: ListType }) => {
  const [searchParams, setSearchParams] = useSearchParams();
  const isWatched = listType === 'watched';
  const query = isWatched ? (searchParams.get('q') ?? '').trim().slice(0, 200) : '';
  const genreParam = isWatched ? Number(searchParams.get('genre_id')) : 0;
  const genreId = Number.isInteger(genreParam) && genreParam > 0 && genreParam <= 2147483647
    ? genreParam
    : undefined;
  const genreName = genreId ? searchParams.get('genre_name') : null;
  const [titleInput, setTitleInput] = useState(query);

  useEffect(() => setTitleInput(query), [query]);

  const searchByTitle = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const title = titleInput.trim();
    setTitleInput(title);
    if (title === query) return;
    const params = new URLSearchParams(searchParams);
    if (title) params.set('q', title);
    else params.delete('q');
    setSearchParams(params);
  };

  const clearGenre = () => {
    const params = new URLSearchParams(searchParams);
    params.delete('genre_id');
    params.delete('genre_name');
    setSearchParams(params);
  };

  return (
    <div className={styles.container}>
      <ListTabs currentType={listType} />
      {isWatched && (
        <form className={styles.filtersBar} onSubmit={searchByTitle}>
          <input
            type="search"
            aria-label="Поиск по названию"
            placeholder="Название фильма"
            value={titleInput}
            maxLength={200}
            onChange={(event) => setTitleInput(event.target.value)}
            className={styles.searchInput}
          />
          <button type="submit" className={styles.pageBtn}>Найти</button>
          {genreId !== undefined && (
            <button
              type="button"
              className={styles.pageBtn}
              onClick={clearGenre}
            >
              {genreName ? `Сбросить жанр «${genreName}»` : 'Сбросить жанр'}
            </button>
          )}
        </form>
      )}
      <MovieListResults
        key={`${listType}:${genreId ?? ''}:${query}`}
        listType={listType}
        query={query}
        genreId={genreId}
      />
    </div>
  );
};

interface MovieListResultsProps {
  listType: ListType;
  query: string;
  genreId?: number;
}

const MovieListResults = ({ listType, query, genreId }: MovieListResultsProps) => {
  const { user, accessToken } = useAuth();
  const { showToast } = useToast();
  const username = user?.username;
  const [list, setList] = useState<MovieListPage | null>(null);
  const [page, setPage] = useState(1);
  const [attempt, setAttempt] = useState(0);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState('');
  const [removeError, setRemoveError] = useState('');
  const [removingId, setRemovingId] = useState<number | null>(null);
  const removal = useRef<AbortController | null>(null);

  useEffect(() => () => removal.current?.abort(), []);

  useEffect(() => {
    if (!username || !accessToken) return;
    const controller = new AbortController();
    const { signal } = controller;
    setLoading(true);
    setLoadError('');
    setRemoveError('');

    getMovieListApi(username, listType, page, accessToken, signal, { q: query || undefined, genre_id: genreId })
      .then((data) => {
        if (signal.aborted) return;
        const lastPage = Math.max(data.total_pages, 1);
        if (page > lastPage) {
          setPage(lastPage);
        } else {
          setList(data);
        }
      })
      .catch((requestError) => {
        if (!signal.aborted) {
          setLoadError(getApiErrorMessage(requestError, 'Не удалось открыть список.'));
        }
      })
      .finally(() => {
        if (!signal.aborted) setLoading(false);
      });

    return () => controller.abort();
  }, [username, listType, accessToken, page, attempt, query, genreId]);

  const reload = () => {
    setLoading(true);
    setAttempt((previous) => previous + 1);
  };

  const removeMovie = async (movieId: number) => {
    if (!accessToken || removal.current) return;
    const controller = new AbortController();
    removal.current = controller;
    setRemovingId(movieId);
    setRemoveError('');

    try {
      await removeMovieListEntryApi(movieId, listType, accessToken, controller.signal);
      if (controller.signal.aborted) return;
      showToast('Фильм удалён из списка');
      reload();
    } catch (requestError) {
      if (!controller.signal.aborted) {
        setRemoveError(getApiErrorMessage(requestError, 'Не удалось удалить фильм из списка.'));
      }
    } finally {
      if (!controller.signal.aborted) {
        removal.current = null;
        setRemovingId(null);
      }
    }
  };

  if (!accessToken) return <ErrorState message="Войди снова, чтобы открыть список." />;
  if (loadError) return <ErrorState message={loadError} onRetry={reload} />;
  if (loading || list?.page !== page) return <Spinner />;
  if (list.results.length === 0) {
    return <EmptyState message={query || genreId ? 'Фильмы по этим условиям не найдены' : 'Список пуст'} />;
  }

  return (
    <>
      {removeError && <ErrorState message={removeError} />}
      <div className={styles.grid}>
        {list.results.map((movie) => (
          <div key={movie.id} className={styles.cardItem}>
            <MovieCard
              movie={{
                id: String(movie.id),
                title: movie.title,
                poster_url: getTmdbPosterUrl(movie.poster_path),
                is_favorite: listType === 'favorite',
                year: movie.release_date ? Number(movie.release_date.slice(0, 4)) : undefined,
              }}
              to={`/movies/${movie.id}`}
            />
            <button
              type="button"
              className={styles.actionBtn}
              disabled={removingId !== null}
              onClick={() => removeMovie(movie.id)}
            >
              {removingId === movie.id ? 'Удаляем…' : 'Удалить из списка'}
            </button>
          </div>
        ))}
      </div>
      {list.total_pages > 1 && (
        <div className={styles.pagination}>
          <button
            type="button"
            className={styles.pageBtn}
            disabled={page === 1 || removingId !== null}
            onClick={() => setPage(page - 1)}
          >
            Назад
          </button>
          <span className={styles.pageInfo}>{page} из {list.total_pages}</span>
          <button
            type="button"
            className={styles.pageBtn}
            disabled={page === list.total_pages || removingId !== null}
            onClick={() => setPage(page + 1)}
          >
            Вперёд
          </button>
        </div>
      )}
    </>
  );
};
