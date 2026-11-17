import { apiClient } from './client';
import type { User, Movie, Review } from '../types';

export interface RatedMovie {
  movie: Movie;
  rating: number;
}

export interface UserReviewItem extends Review {
  movie: {
    id: string;
    title: string;
  };
}

export interface UserProfile extends User {
  is_private: boolean;
  is_friend?: boolean;
  pending_request?: boolean;
  lists?: {
    watchlist: Movie[];
    watched: Movie[];
    favorite: Movie[];
  };
  ratings?: RatedMovie[];
  reviews?: UserReviewItem[];
}

export const getUserProfileApi = async (username: string): Promise<UserProfile> => {
  const response = await apiClient.get<UserProfile>(`/users/${username}`);
  return response.data;
};

export const updateProfileApi = async (data: {
  display_name?: string;
  bio?: string;
  avatar_url?: string;
  is_private?: boolean;
}): Promise<User> => {
  const response = await apiClient.put<User>('/users/me', data);
  return response.data;
};

export const sendFriendRequestApi = async (username: string): Promise<void> => {
  await apiClient.post(`/friends/request`, { username });
};
