import { apiClient } from './client';
import { httpClient } from './httpClient';
import { getTmdbPosterUrl } from './movies';
import type { TmdbGenre, TmdbMovie } from './movies';
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

export interface MovieDetail extends Omit<Movie, 'year'> {
  year?: number;
  release_date?: string;
  average_rating?: number | null;
  ratings_count?: number;
  tmdb_vote_average?: number | null;
  tmdb_vote_count?: number | null;
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

interface MovieDetailResponse extends Omit<TmdbMovie, 'genre_ids'> {
  id: number;
  runtime: number | null;
  genres: (TmdbGenre & { id: number })[];
  average_rating: number | null;
  ratings_count: number;
  tmdb_vote_average: number | null;
  tmdb_vote_count: number | null;
  tmdb_rating_updated_at: string | null;
}

export const openTmdbMovieApi = async (id: string, signal: AbortSignal): Promise<number> => {
  const response = await httpClient.get<MovieDetailResponse>(`/movies/tmdb/${id}`, { signal });
  return response.data.id;
};

export const getMovieDetailApi = async (id: string, signal: AbortSignal): Promise<MovieDetail> => {
  const { data } = await httpClient.get<MovieDetailResponse>(`/movies/${id}`, { signal });
  return {
    id: String(data.id),
    title: data.title,
    release_date: data.release_date ?? undefined,
    poster_url: getTmdbPosterUrl(data.poster_path),
    genres: data.genres.map(({ name }) => name),
    duration: data.runtime ?? undefined,
    description: data.overview ?? undefined,
    average_rating: data.average_rating,
    ratings_count: data.ratings_count,
    tmdb_vote_average: data.tmdb_vote_average,
    tmdb_vote_count: data.tmdb_vote_count,
    reviews: [],
    critic_reviews: [],
  };
};

export const getDemoMovieDetailApi = async (id: string, signal: AbortSignal): Promise<MovieDetail> => {
  const response = await apiClient.get<MovieDetail>(`/movies/${encodeURIComponent(id)}`, { signal });
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
