import { apiClient } from './client';
import type { User } from '../types';

export interface LoginCredentials {
  username_or_email: string;
  password: string;
}

export interface RegisterData {
  username: string;
  email: string;
  password: string;
  password_confirm: string;
}

export const loginApi = async (data: LoginCredentials): Promise<User> => {
  const response = await apiClient.post<User>('/auth/login', data);
  return response.data;
};

export const registerApi = async (data: RegisterData): Promise<void> => {
  await apiClient.post('/auth/register', data);
};