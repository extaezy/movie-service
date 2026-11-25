import { useEffect, useRef, useState } from 'react';
import { Link } from 'react-router-dom';
import { getApiErrorMessage } from '../../api/errors';
import { addMovieListEntryApi, getMovieListApi, removeMovieListEntryApi } from '../../api/lists';
import type { ListType } from '../../api/lists';
import { useToast } from '../../context/ToastContext';
import styles from './Movie.module.css';

const movieLists: { type: ListType; label: string }[] = [
  { type: 'watchlist', label: 'Планирую посмотреть' },
  { type: 'watched', label: 'Просмотрено' },
  { type: 'favorite', label: 'Любимое' },
];

interface MovieListButtonsProps {
  movieId: string;
  username: string | undefined;
  accessToken: string | null;
}

const includesMovie = async (
  movieId: number,
  username: string,
  listType: ListType,
  token: string,
  signal: AbortSignal,
): Promise<boolean> => {
  let page = 1;
  let totalPages = 1;
  while (page <= totalPages && !signal.aborted) {
    const list = await getMovieListApi(username, listType, page, token, signal);
    if (list.results.some((movie) => movie.id === movieId)) return true;
    totalPages = list.total_pages;
    page += 1;
  }
  return false;
};

export const MovieListButtons = ({ movieId, username, accessToken }: MovieListButtonsProps) => {
  const [membership, setMembership] = useState<ListType[] | null>(null);
  const [loadError, setLoadError] = useState('');
  const [loadAttempt, setLoadAttempt] = useState(0);
  const [pending, setPending] = useState<ListType[]>([]);
  const [mutationErrors, setMutationErrors] = useState<Partial<Record<ListType, string>>>({});
  const request = useRef<AbortController | null>(null);
  const submissions = useRef(new Set<ListType>());
  const { showToast } = useToast();

  useEffect(() => {
    if (!username || !accessToken) return;

    const controller = new AbortController();
    const { signal } = controller;
    request.current = controller;
    Promise.all(movieLists.map(async ({ type }) =>
      await includesMovie(Number(movieId), username, type, accessToken, signal) ? type : null,
    ))
      .then((listTypes) => {
        if (!signal.aborted) setMembership(listTypes.filter((type) => type !== null));
      })
      .catch((error: unknown) => {
        if (!signal.aborted) {
          setLoadError(getApiErrorMessage(error, 'Не удалось загрузить состояние списков.'));
          controller.abort();
        }
      });

    return () => {
      controller.abort();
      request.current = null;
      submissions.current.clear();
    };
  }, [movieId, username, accessToken, loadAttempt]);

  const toggleList = async (listType: ListType) => {
    const signal = request.current?.signal;
    if (!accessToken || !membership || !signal || submissions.current.has(listType)) return;

    const removing = membership.includes(listType);
    const fallback = removing ? 'Не удалось удалить фильм из списка.' : 'Не удалось добавить фильм в список.';
    submissions.current.add(listType);
    setPending((previous) => [...previous, listType]);
    setMutationErrors((previous) => ({ ...previous, [listType]: undefined }));

    try {
      if (removing) {
        await removeMovieListEntryApi(Number(movieId), listType, accessToken, signal);
      } else {
        await addMovieListEntryApi(movieId, listType, accessToken, signal);
      }
      if (signal.aborted) return;
      setMembership((previous) => {
        const otherLists = previous?.filter((type) => type !== listType) ?? [];
        return removing ? otherLists : [...otherLists, listType];
      });
      showToast(removing ? 'Фильм удалён из списка' : 'Фильм добавлен в список');
    } catch (error) {
      if (!signal.aborted) {
        setMutationErrors((previous) => ({ ...previous, [listType]: getApiErrorMessage(error, fallback) }));
      }
    } finally {
      if (!signal.aborted) {
        submissions.current.delete(listType);
        setPending((previous) => previous.filter((type) => type !== listType));
      }
    }
  };

  const signedIn = Boolean(username && accessToken);
  const loading = signedIn && !membership && !loadError;

  return (
    <>
      <div className={styles.statusTabs} aria-busy={loading || pending.length > 0}>
        {movieLists.map(({ type, label }) => {
          const active = membership?.includes(type);
          return (
            <button
              key={type}
              type="button"
              className={`${styles.statusBtn} ${active ? styles.activeStatus : ''}`}
              disabled={!membership || pending.includes(type)}
              aria-pressed={active}
              onClick={() => toggleList(type)}
            >
              {label}
            </button>
          );
        })}
      </div>
      {!signedIn && <Link to="/login">Войдите, чтобы управлять списками</Link>}
      {loading && <span role="status">Загружаем списки…</span>}
      {loadError && (
        <div>
          <p role="alert" className={styles.reviewError}>{loadError}</p>
          <button type="button" className={styles.statusBtn} onClick={() => {
            setLoadError('');
            setLoadAttempt((attempt) => attempt + 1);
          }}>
            Повторить
          </button>
        </div>
      )}
      {movieLists.map(({ type, label }) => mutationErrors[type] && (
        <p key={type} role="alert" className={styles.reviewError}>«{label}». {mutationErrors[type]}</p>
      ))}
    </>
  );
};
