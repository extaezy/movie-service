import { httpClient } from './httpClient';
import type { CurrentUser } from '../types';

export interface LoginCredentials {
  identifier: string;
  password: string;
}

export interface RegisterData {
  username: string;
  email: string;
  password: string;
  password_confirm: string;
}

export interface RegisterResponse {
  username: string;
  email: string;
}

export interface TokenResponse {
  access_token: string;
  token_type: 'bearer';
}

export const loginApi = async (data: LoginCredentials): Promise<TokenResponse> => {
  const response = await httpClient.post<TokenResponse>('/auth/login', data);
  return response.data;
};

export const getCurrentUserApi = async (token: string): Promise<CurrentUser> => {
  const response = await httpClient.get<CurrentUser>('/auth/me', {
    headers: { Authorization: `Bearer ${token}` },
  });
  return response.data;
};

export const registerApi = async (data: RegisterData): Promise<RegisterResponse> => {
  const response = await httpClient.post<RegisterResponse>('/auth/register', data);
  return response.data;
};
