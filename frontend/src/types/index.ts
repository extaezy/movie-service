export interface User {
  id: string;
  username: string;
  email: string;
  display_name?: string;
  bio?: string;
  avatar_url?: string;
  is_private: boolean;
}

export interface Movie {
  id: string;
  title: string;
  year: number;
  poster_url: string;
  genres: string[];
  duration?: number;
  description?: string;
  is_favorite?: boolean;
  rating?: number;
}

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

export interface ToastMessage {
  id: string;
  message: string;
  actionText?: string;
  onAction?: () => void;
}