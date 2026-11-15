import { apiClient } from './client';
import type { Movie } from '../types';

export interface MoviesResponse {
  items: Movie[];
  total: number;
  page: number;
  pages: number;
}

export interface MoviesParams {
  search?: string;
  genre?: string;
  year?: number;
  page?: number;
  limit?: number;
}

export const getMoviesApi = async (params: MoviesParams): Promise<MoviesResponse> => {
  const response = await apiClient.get<MoviesResponse>('/movies', { params });
  return response.data;
};

export const getGenresApi = async (): Promise<string[]> => {
  const response = await apiClient.get<string[]>('/movies/genres');
  return response.data;
};

export const toggleFavoriteApi = async (movieId: string): Promise<{ is_favorite: boolean }> => {
  const response = await apiClient.post<{ is_favorite: boolean }>(`/movies/${movieId}/favorite`);
  return response.data;
};