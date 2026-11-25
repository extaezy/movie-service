import { apiClient } from './client';
import { httpClient } from './httpClient';
import type { Movie } from '../types';

export type ListType = 'watchlist' | 'watched' | 'favorite';

export interface ListResponse {
  items: Movie[];
  total: number;
  page: number;
  pages: number;
}

export interface MovieListPage {
  page: number;
  page_size: number;
  total_results: number;
  total_pages: number;
  results: {
    id: number;
    tmdb_id: number;
    title: string;
    poster_path: string | null;
    release_date: string | null;
    added_at: string;
  }[];
}

interface MovieListFilters {
  q?: string;
  genre_id?: number;
}

export const getMovieListApi = async (
  username: string,
  listType: ListType,
  page: number,
  token: string,
  signal: AbortSignal,
  filters?: MovieListFilters,
): Promise<MovieListPage> => {
  const { data } = await httpClient.get<MovieListPage>(`/users/${encodeURIComponent(username)}/movies`, {
    params: { list_type: listType, page, ...filters },
    headers: { Authorization: `Bearer ${token}` },
    signal,
  });
  return data;
};

export const addMovieListEntryApi = async (
  movieId: string,
  listType: ListType,
  token: string,
  signal: AbortSignal,
) => {
  const response = await httpClient.post<{ movie_id: number; list_type: ListType }>(
    `/movies/${movieId}/lists`,
    { list_type: listType },
    { headers: { Authorization: `Bearer ${token}` }, signal },
  );
  return response.status === 201;
};

export const removeMovieListEntryApi = async (
  movieId: number,
  listType: ListType,
  token: string,
  signal: AbortSignal,
): Promise<void> => {
  await httpClient.delete(`/movies/${movieId}/lists/${listType}`, {
    headers: { Authorization: `Bearer ${token}` },
    signal,
  });
};

export const getUserListApi = async (type: ListType, page = 1, limit = 12): Promise<ListResponse> => {
  const response = await apiClient.get<ListResponse>(`/lists/${type}`, {
    params: { page, limit },
  });
  return response.data;
};
