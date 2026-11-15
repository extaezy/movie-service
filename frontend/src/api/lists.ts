import { apiClient } from './client';
import type { Movie } from '../types';

export type ListType = 'watchlist' | 'watched' | 'favorite';

export interface ListResponse {
  items: Movie[];
  total: number;
  page: number;
  pages: number;
}

export const getUserListApi = async (type: ListType, page = 1, limit = 12): Promise<ListResponse> => {
  const response = await apiClient.get<ListResponse>(`/lists/${type}`, {
    params: { page, limit },
  });
  return response.data;
};