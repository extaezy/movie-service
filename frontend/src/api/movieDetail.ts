import { apiClient } from './client';
import type { Movie } from '../types';

export interface Review {
  id: string;
  author: {
    username: string;
    display_name?: string;
    avatar_url?: string;
  };
  text: string;
  created_at: string;
  is_spoiler: boolean;
}

export interface CriticReview {
  id: string;
  source: string;
  critic: string;
  excerpt: string;
  rating?: string;
  url: string;
}

export interface MovieDetail extends Movie {
  duration?: number;
  description?: string;
  user_rating?: number | null;
  user_status?: 'watchlist' | 'watched' | 'favorite' | null;
  user_review?: {
    id: string;
    text: string;
    is_spoiler: boolean;
  } | null;
  reviews: Review[];
  critic_reviews: CriticReview[];
}

export const getMovieDetailApi = async (id: string): Promise<MovieDetail> => {
  const response = await apiClient.get<MovieDetail>(`/movies/${id}`);
  return response.data;
};

export const rateMovieApi = async (id: string, rating: number | null): Promise<void> => {
  await apiClient.post(`/movies/${id}/rating`, { rating });
};

export const setMovieStatusApi = async (id: string, status: string | null): Promise<void> => {
  await apiClient.post(`/movies/${id}/status`, { status });
};

export const saveReviewApi = async (id: string, text: string, is_spoiler: boolean): Promise<any> => {
  const response = await apiClient.post(`/movies/${id}/review`, { text, is_spoiler });
  return response.data;
};

export const deleteReviewApi = async (id: string): Promise<void> => {
  await apiClient.delete(`/movies/${id}/review`);
};