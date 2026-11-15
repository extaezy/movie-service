import { apiClient } from './client';
import type { User } from '../types';

export interface FriendRequest {
  id: string;
  sender: User;
  created_at: string;
}

export const getFriendsApi = async (): Promise<User[]> => {
  const response = await apiClient.get<User[]>('/friends');
  return response.data;
};

export const getIncomingRequestsApi = async (): Promise<FriendRequest[]> => {
  const response = await apiClient.get<FriendRequest[]>('/friends/requests/incoming');
  return response.data;
};

export const acceptFriendRequestApi = async (requestId: string): Promise<void> => {
  await apiClient.post(`/friends/requests/${requestId}/accept`);
};

export const declineFriendRequestApi = async (requestId: string): Promise<void> => {
  await apiClient.post(`/friends/requests/${requestId}/decline`);
};

export const removeFriendApi = async (username: string): Promise<void> => {
  await apiClient.delete(`/friends/${username}`);
};