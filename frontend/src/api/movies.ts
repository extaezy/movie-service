import { apiClient } from './client';
import { httpClient } from './httpClient';

export interface TmdbGenre {
  tmdb_id: number;
  name: string;
}

export interface TmdbMovie {
  tmdb_id: number;
  title: string;
  original_title: string | null;
  overview: string | null;
  release_date: string | null;
  poster_path: string | null;
  original_language: string | null;
  genre_ids: number[];
}

interface TmdbMoviePage {
  page: number;
  total_pages: number;
  total_results: number;
  results: TmdbMovie[];
}

type ReleaseDateSort = 'release_date_asc' | 'release_date_desc';

export type TmdbSort = 'popularity_desc' | ReleaseDateSort;

interface LocalMovie extends Omit<TmdbMovie, 'genre_ids'> {
  id: number;
  runtime: number | null;
  genres: (TmdbGenre & { id: number })[];
}

interface LocalMoviePage extends Omit<TmdbMoviePage, 'results'> {
  page_size: number;
  results: LocalMovie[];
}

interface LocalCatalogParams {
  page: number;
  year?: number;
  sort: ReleaseDateSort;
}

interface DiscoverParams {
  page: number;
  tmdb_genre_id?: number;
  year?: number;
  sort: TmdbSort;
}

export const getLocalMoviesApi = async (
  params: LocalCatalogParams,
  signal: AbortSignal,
): Promise<LocalMoviePage> => {
  const { data } = await httpClient.get<LocalMoviePage>('/movies', { params, signal });
  return data;
};

export const getDiscoverMoviesApi = async (
  params: DiscoverParams,
  signal: AbortSignal,
): Promise<TmdbMoviePage> => {
  const response = await httpClient.get<TmdbMoviePage>('/movies/discover', { params, signal });
  return response.data;
};

export const searchMoviesApi = async (q: string, page: number, signal: AbortSignal): Promise<TmdbMoviePage> => {
  const response = await httpClient.get<TmdbMoviePage>('/movies/search', { params: { q, page }, signal });
  return response.data;
};

export const getTmdbPosterUrl = (path: string | null): string =>
  path?.startsWith('/') ? `https://image.tmdb.org/t/p/w500${path}` : '';

export const toggleFavoriteApi = async (movieId: string): Promise<{ is_favorite: boolean }> => {
  const response = await apiClient.post<{ is_favorite: boolean }>(`/movies/${movieId}/favorite`);
  return response.data;
};
