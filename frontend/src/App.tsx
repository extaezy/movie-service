import { createContext, useContext, useEffect, useState } from 'react';
import type { FormEvent, ReactNode } from 'react';
import axios from 'axios';
import { HashRouter, Link, NavLink, Navigate, Route, Routes, useNavigate, useParams, useSearchParams } from 'react-router-dom';

type Genre = { id: number; name: string };
type ListType = 'watchlist' | 'watched' | 'favorite';
type PrivacyMode = 'open' | 'private';
type MovieSummary = { id: number; title: string; poster_url: string | null; release_date: string | null; genres: Genre[]; user_score: number | null; critic_score: number | null };
type MovieDetail = MovieSummary & { overview: string; runtime_minutes: number; vote_count: number; my_rating: number | null; my_lists: ListType[]; my_review: UserReview | null };
type CriticReview = { id: number; source: string; author: string; language: string; excerpt: string; external_url: string; score_original: number | null; score_normalized: number | null; verdict: string | null };
type UserReview = { id: number; movie_id: number; movie_title?: string; author_username: string; author_avatar_url: string | null; text: string; contains_spoilers: boolean; created_at: string };
type UserPublic = { id: number; username: string; display_name: string | null; avatar_url: string | null; bio: string | null; privacy_mode: PrivacyMode };
type UserProfile = UserPublic & { friend_status: 'none' | 'pending_outgoing' | 'pending_incoming' | 'friends'; pending_request_id: number | null; is_restricted_view?: boolean };
type AuthUser = UserPublic & { email: string; role: 'user' | 'admin' };
type FriendItem = { user: UserPublic; friends_since: string };
type FriendRequestItem = { request_id: number; from: UserPublic; to: UserPublic; created_at: string };
type Page<T> = { items: T[]; page: number; total_pages: number };
type Filters = { q: string; genre_id: number | ''; year: number | ''; sort: '' | 'release_date_asc' | 'release_date_desc' | 'rating_asc' | 'rating_desc' };

const GENRES: Genre[] = [
  { id: 1, name: 'Боевик' }, { id: 2, name: 'Драма' }, { id: 3, name: 'Комедия' }, { id: 4, name: 'Фантастика' },
  { id: 5, name: 'Триллер' }, { id: 6, name: 'Приключения' }, { id: 7, name: 'Анимация' }, { id: 8, name: 'Ужасы' },
];
const g = (...ids: number[]) => GENRES.filter((x) => ids.includes(x.id));
const PALETTES = [
  ['#1b2a4a', '#7a5cff'], ['#3a1d1d', '#ff6b6b'], ['#123c33', '#3ddc97'],
  ['#3b2a12', '#ffb454'], ['#241b3a', '#b47aff'], ['#0f2f4a', '#4fc3f7'],
];

function svgToDataUrl(svg: string): string {
  const bytes = new TextEncoder().encode(svg);
  let bin = '';
  bytes.forEach((b) => { bin += String.fromCharCode(b); });
  return 'data:image/svg+xml;base64,' + btoa(bin);
}

function escapeXml(s: string): string {
  return s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
}

function poster(title: string, seed: string): string {
  const [c1, c2] = PALETTES[Math.abs(hash(seed)) % PALETTES.length];
  const words = title.toUpperCase().split(' ');
  const lines: string[] = [];
  let cur = '';
  for (const w of words) {
    if ((cur + ' ' + w).trim().length > 14) { lines.push(cur.trim()); cur = w; }
    else cur = (cur + ' ' + w).trim();
  }
  if (cur) lines.push(cur);
  const shown = lines.slice(0, 3);
  const tspans = shown.map((l, i) =>
    `<tspan x="150" dy="${i === 0 ? 0 : 34}">${escapeXml(l)}</tspan>`).join('');
  const svg = `<svg xmlns="http://www.w3.org/2000/svg" width="300" height="450" viewBox="0 0 300 450">`
    + `<defs><linearGradient id="g" x1="0" y1="0" x2="1" y2="1">`
    + `<stop offset="0" stop-color="${c1}"/><stop offset="1" stop-color="${c2}"/></linearGradient></defs>`
    + `<rect width="300" height="450" fill="url(#g)"/>`
    + `<circle cx="250" cy="80" r="70" fill="#ffffff" opacity="0.08"/>`
    + `<circle cx="40" cy="380" r="110" fill="#000000" opacity="0.15"/>`
    + `<text x="150" y="300" text-anchor="middle" font-family="'Segoe UI',Arial,sans-serif" font-size="26" font-weight="700" fill="#ffffff">${tspans}</text>`
    + `</svg>`;
  return svgToDataUrl(svg);
}

function hash(s: string): number {
  let h = 0;
  for (let i = 0; i < s.length; i++) h = (h * 31 + s.charCodeAt(i)) | 0;
  return h;
}

function initials(name: string): string {
  return name.slice(0, 2).toUpperCase();
}

function avatar(seed: string): string {
  const [c1, c2] = PALETTES[Math.abs(hash(seed)) % PALETTES.length];
  const svg = `<svg xmlns="http://www.w3.org/2000/svg" width="64" height="64" viewBox="0 0 64 64">`
    + `<defs><linearGradient id="a" x1="0" y1="0" x2="1" y2="1">`
    + `<stop offset="0" stop-color="${c1}"/><stop offset="1" stop-color="${c2}"/></linearGradient></defs>`
    + `<rect width="64" height="64" rx="14" fill="url(#a)"/>`
    + `<text x="32" y="40" text-anchor="middle" font-family="'Segoe UI',Arial,sans-serif" font-size="22" font-weight="700" fill="#ffffff">${escapeXml(initials(seed))}</text>`
    + `</svg>`;
  return svgToDataUrl(svg);
}

const MOVIES: MovieSummary[] = [
  { id: 1, title: 'Начало', poster_url: poster('Начало', 'inception'), release_date: '2010-07-16', genres: g(4, 5, 6), user_score: 8.7, critic_score: 7.4 },
  { id: 2, title: 'Интерстеллар', poster_url: poster('Интерстеллар', 'interstellar'), release_date: '2014-11-07', genres: g(4, 2, 6), user_score: 8.6, critic_score: 7.1 },
  { id: 3, title: 'Оппенгеймер', poster_url: poster('Оппенгеймер', 'oppenheimer'), release_date: '2023-07-20', genres: g(2, 5), user_score: 8.4, critic_score: 8.3 },
  { id: 4, title: 'Паразиты', poster_url: poster('Паразиты', 'parasite'), release_date: '2019-05-30', genres: g(2, 5, 3), user_score: 8.8, critic_score: 9.6 },
  { id: 5, title: 'Побег из Шоушенка', poster_url: poster('Побег из Шоушенка', 'shawshank'), release_date: '1994-09-22', genres: g(2), user_score: 9.1, critic_score: 8.0 },
  { id: 6, title: 'Крёстный отец', poster_url: poster('Крёстный отец', 'godfather'), release_date: '1972-03-14', genres: g(2, 5), user_score: 9.0, critic_score: 9.8 },
  { id: 7, title: 'Марсианин', poster_url: poster('Марсианин', 'martian'), release_date: '2015-09-30', genres: g(4, 2, 6), user_score: 8.3, critic_score: 7.7 },
  { id: 8, title: 'Джокер', poster_url: poster('Джокер', 'joker'), release_date: '2019-10-04', genres: g(2, 5), user_score: 8.4, critic_score: 6.0 },
  { id: 9, title: 'Дюна', poster_url: poster('Дюна', 'dune'), release_date: '2021-09-15', genres: g(4, 6), user_score: 8.1, critic_score: 8.4 },
  { id: 10, title: 'Дюна: Часть вторая', poster_url: poster('Дюна: Часть вторая', 'dune2'), release_date: '2024-02-27', genres: g(4, 6), user_score: 8.5, critic_score: 8.1 },
  { id: 11, title: 'Всё везде и сразу', poster_url: poster('Всё везде и сразу', 'multiverse'), release_date: '2022-03-24', genres: g(3, 4, 6), user_score: 8.0, critic_score: 9.2 },
  { id: 12, title: 'Властелин колец: Возвращение короля', poster_url: poster('Властелин колец: Возвращение короля', 'lotr'), release_date: '2003-12-01', genres: g(6, 2), user_score: 8.9, critic_score: 9.3 },
  { id: 13, title: 'Голодные игры', poster_url: poster('Голодные игры', 'hunger'), release_date: '2012-03-12', genres: g(4, 5, 6), user_score: 7.2, critic_score: 6.9 },
  { id: 14, title: 'Бойцовский клуб', poster_url: poster('Бойцовский клуб', 'club'), release_date: '1999-10-15', genres: g(2, 5), user_score: 8.8, critic_score: 7.2 },
  { id: 15, title: 'Матрица', poster_url: poster('Матрица', 'matrix'), release_date: '1999-03-31', genres: g(4, 1), user_score: 8.5, critic_score: 7.5 },
  { id: 16, title: 'Унесённые призраками', poster_url: poster('Унесённые призраками', 'spirited'), release_date: '2001-07-20', genres: g(7, 6), user_score: 8.6, critic_score: 9.7 },
  { id: 17, title: 'Тонкий мир', poster_url: poster('Тонкий мир', 'thinworld'), release_date: '1988-04-16', genres: g(7), user_score: 8.2, critic_score: 9.0 },
  { id: 18, title: 'Дэдпул и Росомаха', poster_url: poster('Дэдпул и Росомаха', 'deadpool'), release_date: '2024-07-24', genres: g(3, 1, 4), user_score: 7.8, critic_score: 7.0 },
  { id: 19, title: 'Гадкий я 4', poster_url: poster('Гадкий я 4', 'gru4'), release_date: '2024-06-20', genres: g(7, 3), user_score: 6.9, critic_score: 5.4 },
  { id: 20, title: 'Оно', poster_url: poster('Оно', 'it'), release_date: '2017-09-06', genres: g(8, 2), user_score: 7.5, critic_score: 7.1 },
  { id: 21, title: 'Оно 2', poster_url: poster('Оно 2', 'it2'), release_date: '2019-09-06', genres: g(8, 5), user_score: 6.8, critic_score: 5.3 },
  { id: 22, title: 'Сонная Лощина', poster_url: poster('Сонная Лощина', 'sleepy'), release_date: '1999-11-19', genres: g(8, 5, 2), user_score: 7.7, critic_score: 7.2 },
  { id: 23, title: 'Дьявол носит Prada', poster_url: poster('Дьявол носит Prada', 'prada'), release_date: '2006-06-30', genres: g(3, 2), user_score: 7.0, critic_score: 6.5 },
  { id: 24, title: 'Целься', poster_url: poster('Целься', 'daylight'), release_date: '2026-02-13', genres: g(7, 3), user_score: 7.4, critic_score: 6.8 },
];
const YEARS = Array.from(new Set(MOVIES.map((m) => Number((m.release_date ?? '2020').slice(0, 4))))).sort((a, b) => b - a);
const OVERVIEW = 'Долгое описание для демо. Карточка фильма показывает постер, название, дату выхода, жанры, длительность и полный синопсис.';

function mkReview(id: number, username: string, text: string, spoilers: boolean, date: string): UserReview {
  return { id, movie_id: (id % 24) + 1, author_username: username, author_avatar_url: avatar(username), text, contains_spoilers: spoilers, created_at: `${date}T12:00:00Z` };
}

function toDetail(id: number): MovieDetail | undefined {
  const m = MOVIES.find((x) => x.id === id);
  if (!m) return undefined;
  return {
    ...m,
    overview: OVERVIEW,
    runtime_minutes: 118 + ((id * 7) % 60),
    vote_count: 120 + id * 37,
    my_rating: id % 4 === 0 ? null : 7 + (id % 3),
    my_lists: id % 3 === 0 ? ['watched', 'favorite'] : id % 2 === 0 ? ['watchlist'] : ['watched'],
    my_review: id % 5 === 0 ? null : mkReview(900 + id, 'cinephile', 'Крепкое кино с сильной второй половиной.', id % 6 === 0, '2026-09-14'),
  };
}

const criticReviewsFor = (movieId: number): CriticReview[] => [
  { id: 1, source: 'Кинотеатр.ru', author: 'Анна Белова', language: 'ru', excerpt: 'Зрелищное и умное высказывание о природе времени и выбора.', external_url: 'https://example.com/review/1', score_original: 9, score_normalized: 9.0, verdict: 'Обязательно к просмотру' },
  { id: 2, source: 'FilmCritic', author: 'Игорь Смирнов', language: 'ru', excerpt: 'Локальные провалы темпа не отменяют общего впечатления.', external_url: 'https://example.com/review/2', score_original: 70, score_normalized: 7.0, verdict: 'Хорошо' },
  { id: 3, source: 'Metacritic', author: 'Alex Rivera', language: 'en', excerpt: 'A confident blockbuster with an unusual emotional core.', external_url: 'https://example.com/review/3', score_original: 78, score_normalized: 7.8, verdict: 'Generally favorable' },
].map((r) => ({ ...r, id: r.id + movieId * 100 }));

const USER_REVIEWS: UserReview[] = [
  mkReview(1, 'cinephile', 'Лучшее, что выходило в этом жанре за последние годы. Саундтрек — отдельный персонаж.', false, '2026-10-02'),
  mkReview(2, 'movie_nomad', 'Первая половина затянутая, зато финал искупает всё.', true, '2026-09-21'),
  mkReview(3, 'darkroom', 'Визуально безупречно. Сюжетно — спорно, но интересно.', false, '2026-08-30'),
  mkReview(4, 'popcorn_cat', 'Смотрел дважды. На третий раз замечаются новые детали.', false, '2026-07-11'),
];

const ME: AuthUser = {
  id: 100, username: 'cinephile', display_name: 'Киноман', avatar_url: avatar('cinephile'),
  bio: 'Пишу рецензии, собираю список «Планирую посмотреть». Люблю фантастику и медленную драму.',
  privacy_mode: 'open', email: 'me@example.com', role: 'admin',
};

const USERS: UserProfile[] = [
  { id: 101, username: 'movie_nomad', display_name: 'Кино-кочевник', avatar_url: avatar('movie_nomad'), bio: 'Каждый вечер — новый фильм.', privacy_mode: 'open', friend_status: 'friends', pending_request_id: null },
  { id: 102, username: 'darkroom', display_name: 'Тёмная комната', avatar_url: avatar('darkroom'), bio: 'Люблю нуар и плохую погоду.', privacy_mode: 'private', friend_status: 'pending_outgoing', pending_request_id: 501 },
  { id: 103, username: 'popcorn_cat', display_name: 'Попкорн-кот', avatar_url: avatar('popcorn_cat'), bio: null, privacy_mode: 'open', friend_status: 'pending_incoming', pending_request_id: 502 },
  { id: 104, username: 'sundance', display_name: null, avatar_url: null, bio: 'Закрытый профиль — посторонний видит только имя и аватар.', privacy_mode: 'private', friend_status: 'none', pending_request_id: null },
];

const FRIENDS: FriendItem[] = [{ user: USERS[0], friends_since: '2026-05-14' }];
const REQUESTS: FriendRequestItem[] = [
  { request_id: 502, from: USERS[2], to: ME, created_at: '2026-10-20T09:15:00Z' },
  { request_id: 501, from: ME, to: USERS[1], created_at: '2026-10-25T19:40:00Z' },
];

const moviesByList = (username: string, listType: string): MovieSummary[] => {
  const seed = [...username].reduce((a, c) => a + c.charCodeAt(0), 0) + listType.length;
  return MOVIES.filter((_, i) => (i + seed) % 3 === 0).slice(0, 9);
};

const USE_MOCKS = import.meta.env.VITE_USE_MOCKS !== '0';

export const api = axios.create({ baseURL: import.meta.env.VITE_API_URL ?? '/api' });

api.interceptors.request.use((config) => {
  const token = localStorage.getItem('token');
  if (token) config.headers.Authorization = `Bearer ${token}`;
  return config;
});

api.interceptors.response.use(
  (r) => r,
  (error) => {
    if (error?.response?.status === 401) {
      localStorage.removeItem('token');
      window.dispatchEvent(new Event('unauthorized'));
    }
    return Promise.reject(error);
  },
);

const delay = (ms = 350) => new Promise((res) => setTimeout(res, ms));

function httpError(message: string, status = 400) {
  const err: any = new Error(message);
  err.response = { status, data: { detail: { message } } };
  return err;
}

export function errorMessage(e: unknown): string {
  const anyErr: any = e;
  return anyErr?.response?.data?.detail?.message
    ?? (typeof anyErr?.response?.data?.detail === 'string' ? anyErr.response.data.detail : null)
    ?? anyErr?.message
    ?? 'Неизвестная ошибка. Попробуйте позже.';
}

async function fetchMovies(params: Filters & { page: number; page_size: number }): Promise<Page<MovieSummary>> {
  if (!USE_MOCKS) return (await api.get('/movies', { params })).data;
  await delay();
  let items = [...MOVIES];
  if (params.q) items = items.filter((m) => m.title.toLowerCase().includes(params.q.toLowerCase()));
  if (params.genre_id) items = items.filter((m) => m.genres.some((x) => x.id === params.genre_id));
  if (params.year) items = items.filter((m) => m.release_date?.startsWith(String(params.year)));
  switch (params.sort) {
    case 'release_date_asc': items.sort((a, b) => (a.release_date ?? '').localeCompare(b.release_date ?? '')); break;
    case 'release_date_desc': items.sort((a, b) => (b.release_date ?? '').localeCompare(a.release_date ?? '')); break;
    case 'rating_asc': items.sort((a, b) => (a.user_score ?? 0) - (b.user_score ?? 0)); break;
    case 'rating_desc': items.sort((a, b) => (b.user_score ?? 0) - (a.user_score ?? 0)); break;
  }
  const size = params.page_size;
  return {
    items: items.slice((params.page - 1) * size, params.page * size),
    page: params.page,
    total_pages: Math.max(1, Math.ceil(items.length / size)),
  };
}

async function fetchMovie(id: number): Promise<MovieDetail> {
  if (!USE_MOCKS) return (await api.get(`/movies/${id}`)).data;
  await delay();
  const d = toDetail(id);
  if (!d) throw httpError('Фильм не найден', 404);
  return d;
}

async function fetchCriticReviews(movieId: number): Promise<CriticReview[]> {
  if (!USE_MOCKS) return (await api.get(`/movies/${movieId}/critic-reviews`)).data.items;
  await delay();
  return criticReviewsFor(movieId);
}

async function fetchUser(username: string): Promise<UserProfile> {
  if (!USE_MOCKS) return (await api.get(`/users/${username}`)).data;
  await delay();
  const u = USERS.find((x) => x.username === username)
    ?? (username === ME.username || username === 'me' ? ({ ...ME, friend_status: 'none', pending_request_id: null } as UserProfile) : undefined);
  if (!u) throw httpError('Пользователь не найден', 404);
  if (u.privacy_mode === 'private' && u.friend_status !== 'friends') return { ...u, bio: null, is_restricted_view: true };
  return u;
}

async function fetchUserReviews(username: string): Promise<UserReview[]> {
  if (!USE_MOCKS) return (await api.get(`/users/${username}/reviews`)).data;
  await delay();
  return USER_REVIEWS.filter((r) => r.author_username === username)
    .map((r) => ({ ...r, movie_title: MOVIES.find((m) => m.id === r.movie_id)?.title ?? 'Фильм' }));
}

async function fetchUserList(username: string, listType: ListType): Promise<MovieSummary[]> {
  if (!USE_MOCKS) return (await api.get(`/users/${username}/movies`, { params: { list_type: listType } })).data;
  await delay();
  return moviesByList(username, listType);
}

async function login(email: string, password: string) {
  if (!USE_MOCKS) return (await api.post('/auth/login', { email, password })).data;
  await delay(500);
  if (!email || !password) throw httpError('Неверный email или пароль', 401);
  return { token: 'demo-token', user: { ...ME } };
}

async function register(payload: { email: string; username: string; password: string }) {
  if (!USE_MOCKS) return (await api.post('/auth/register', payload)).data;
  await delay(500);
  if (payload.username === 'taken') throw httpError('Этот username уже занят', 409);
  return { token: 'demo-token', user: { ...ME, username: payload.username, email: payload.email } };
}

async function me(): Promise<AuthUser | null> {
  if (!USE_MOCKS) {
    try {
      return (await api.get('/auth/me')).data;
    } catch {
      return null;
    }
  }
  await delay(200);
  return localStorage.getItem('token') ? { ...ME } : null;
}

async function patchProfile(payload: Record<string, unknown>): Promise<AuthUser> {
  if (!USE_MOCKS) return (await api.patch('/users/me/profile', payload)).data;
  await delay(500);
  return { ...ME, ...payload } as AuthUser;
}

async function rateMovie(movieId: number, score: number) {
  if (!USE_MOCKS) return (await api.put(`/movies/${movieId}/rating`, { score })).data;
  await delay(400);
  if (score < 1 || score > 10 || !Number.isInteger(score)) throw httpError('Оценка должна быть целым числом от 1 до 10', 422);
  return { ok: true };
}

async function deleteRating(movieId: number) {
  if (!USE_MOCKS) return (await api.delete(`/movies/${movieId}/rating`)).data;
  await delay(300);
  return { ok: true };
}

async function setList(movieId: number, listType: ListType, add: boolean) {
  if (!USE_MOCKS) {
    return add
      ? (await api.post(`/movies/${movieId}/lists`, { list_type: listType })).data
      : (await api.delete(`/movies/${movieId}/lists/${listType}`)).data;
  }
  await delay(300);
  return { ok: true };
}

async function publishReview(movieId: number, text: string, containsSpoilers: boolean) {
  if (!USE_MOCKS) return (await api.post(`/movies/${movieId}/reviews`, { text, contains_spoilers: containsSpoilers })).data;
  await delay(500);
  if (text.trim().length < 10) throw httpError('Рецензия слишком короткая');
  return { ok: true };
}

async function fetchFriends(): Promise<FriendItem[]> {
  if (!USE_MOCKS) return (await api.get('/friends')).data;
  await delay();
  return FRIENDS;
}

async function fetchFriendRequests(): Promise<FriendRequestItem[]> {
  if (!USE_MOCKS) return (await api.get('/friends/requests')).data;
  await delay();
  return REQUESTS;
}

async function sendFriendRequest(userId: number) {
  if (!USE_MOCKS) return (await api.post(`/friends/requests/${userId}`)).data;
  await delay(400);
  return { ok: true };
}

async function respondFriendRequest(requestId: number, accept: boolean) {
  if (!USE_MOCKS) {
    return accept
      ? (await api.post(`/friends/requests/${requestId}/accept`)).data
      : (await api.post(`/friends/requests/${requestId}/reject`)).data;
  }
  await delay(400);
  return { ok: true };
}

async function removeFriend(userId: number) {
  if (!USE_MOCKS) return (await api.delete(`/friends/${userId}`)).data;
  await delay(400);
  return { ok: true };
}

async function syncMovies() {
  if (!USE_MOCKS) return (await api.post('/admin/movies/sync')).data;
  await delay(1200);
  return { synced: MOVIES.length };
}

type AuthState = {
  user: AuthUser | null;
  loading: boolean;
  login: (email: string, password: string) => Promise<void>;
  register: (email: string, username: string, password: string) => Promise<void>;
  logout: () => void;
  updateUser: (patch: Partial<AuthUser>) => void;
};

const AuthContext = createContext<AuthState | null>(null);

function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<AuthUser | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    me().then((u) => !cancelled && setUser(u)).finally(() => !cancelled && setLoading(false));
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    const onUnauth = () => setUser(null);
    window.addEventListener('unauthorized', onUnauth);
    return () => window.removeEventListener('unauthorized', onUnauth);
  }, []);

  const value: AuthState = {
    user,
    loading,
    login: async (email, password) => {
      const res = await login(email, password);
      localStorage.setItem('token', res.token);
      setUser(res.user);
    },
    register: async (email, username, password) => {
      const res = await register({ email, username, password });
      localStorage.setItem('token', res.token);
      setUser(res.user);
    },
    logout: () => {
      localStorage.removeItem('token');
      setUser(null);
    },
    updateUser: (patch) => setUser((prev) => (prev ? { ...prev, ...patch } : prev)),
  };

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

function useAuth(): AuthState {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error('useAuth должен вызываться внутри AuthProvider');
  return ctx;
}

function Spinner({ label = 'Загрузка…' }: { label?: string }) {
  return (
    <div className="state state--loading" role="status">
      <span className="spinner" aria-hidden="true" />
      <span>{label}</span>
    </div>
  );
}

function EmptyState({ title, hint }: { title: string; hint?: string }) {
  return (
    <div className="state state--empty">
      <div className="state__icon" aria-hidden="true">🗂️</div>
      <p className="state__title">{title}</p>
      {hint && <p className="state__hint">{hint}</p>}
    </div>
  );
}

function ErrorState({ message, onRetry }: { message: string; onRetry?: () => void }) {
  return (
    <div className="state state--error" role="alert">
      <div className="state__icon" aria-hidden="true">⚠️</div>
      <p className="state__title">Не удалось загрузить данные</p>
      <p className="state__hint">{message}</p>
      {onRetry && <button className="btn btn--secondary" onClick={onRetry}>Повторить</button>}
    </div>
  );
}

function ScoreBadge({ score, kind }: { score: number | null; kind: 'user' | 'critic' }) {
  const cls = ['score', score == null ? 'score--na' : score >= 7.5 ? 'score--good' : score >= 5 ? 'score--ok' : 'score--bad'].filter(Boolean).join(' ');
  return (
    <span className={cls} title={kind === 'user' ? 'Рейтинг зрителей' : 'Рейтинг критиков'}>
      <span className="score__kind">{kind === 'user' ? 'Зрители' : 'Критики'}</span>
      <span className="score__value">{score == null ? '—' : score.toFixed(1)}</span>
      <span className="score__max">/10</span>
    </span>
  );
}

function Avatar({ user, size = 'md' }: { user: { username: string; avatar_url: string | null }; size?: 'sm' | 'md' | 'lg' }) {
  return <img className={`avatar avatar--${size}`} src={user.avatar_url ?? avatar(user.username)} alt={`Аватар ${user.username}`} />;
}

const yearOf = (iso: string | null) => (iso ? iso.slice(0, 4) : '—');

function SearchBar({ initial = '', onSubmit }: { initial?: string; onSubmit: (q: string) => void }) {
  const [value, setValue] = useState(initial);
  return (
    <form className="searchbar" role="search" onSubmit={(e) => { e.preventDefault(); onSubmit(value.trim()); }}>
      <input type="search" placeholder="Поиск по названию фильма…" aria-label="Поиск фильмов" value={value} onChange={(e) => setValue(e.target.value)} />
      <button className="btn btn--primary" type="submit">Найти</button>
    </form>
  );
}

function Header() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  return (
    <header className="header">
      <div className="header__inner">
        <Link to="/" className="logo" aria-label="Movie Service — на главную">
          <span className="logo__mark">🎬</span> Movie<span>Service</span>
        </Link>
        <SearchBar onSubmit={(q) => navigate(q ? `/?q=${encodeURIComponent(q)}` : '/')} />
        <nav className="nav" aria-label="Основная навигация">
          <NavLink to="/lists/watchlist">Мои списки</NavLink>
          <NavLink to="/friends">Друзья</NavLink>
          {user?.role === 'admin' && <NavLink to="/admin">Админ</NavLink>}
          {user ? (
            <div className="nav__user">
              <NavLink to={`/profile/${user.username}`} className="nav__profile">
                <Avatar user={user} size="sm" />
                <span>{user.display_name ?? user.username}</span>
              </NavLink>
              <button className="btn btn--ghost" onClick={logout}>Выйти</button>
            </div>
          ) : (
            <Link className="btn btn--secondary" to="/login">Войти</Link>
          )}
        </nav>
      </div>
    </header>
  );
}

function AppLayout({ children }: { children: ReactNode }) {
  return (
    <div className="layout">
      <Header />
      <main className="layout__main">{children}</main>
      <footer className="footer">
        <p>Movie Service — макет интерфейса. Данные демонстрационные, источник каталога — TMDB (через backend).</p>
      </footer>
    </div>
  );
}

function MovieCard({ movie }: { movie: MovieSummary }) {
  return (
    <article className="movie-card">
      <Link to={`/movies/${movie.id}`} className="movie-card__poster-link">
        {movie.poster_url ? (
          <img className="movie-card__poster" src={movie.poster_url} alt={`Постер: ${movie.title}`} loading="lazy" />
        ) : (
          <div className="movie-card__poster movie-card__poster--missing">Нет постера</div>
        )}
      </Link>
      <div className="movie-card__body">
        <h3 className="movie-card__title"><Link to={`/movies/${movie.id}`}>{movie.title}</Link></h3>
        <p className="movie-card__meta">{yearOf(movie.release_date)} · {movie.genres.map((x) => x.name).join(', ') || 'Без жанра'}</p>
        <div className="movie-card__scores">
          <ScoreBadge score={movie.user_score} kind="user" />
          <ScoreBadge score={movie.critic_score} kind="critic" />
        </div>
      </div>
    </article>
  );
}

function MovieGrid({ movies }: { movies: MovieSummary[] }) {
  return <div className="movie-grid">{movies.map((m) => <MovieCard key={m.id} movie={m} />)}</div>;
}

function MovieFilters({ filters, onChange }: { filters: Filters; onChange: (patch: Partial<Filters>) => void }) {
  return (
    <div className="filters" aria-label="Фильтры каталога">
      <label>
        Жанр
        <select value={String(filters.genre_id)} onChange={(e) => onChange({ genre_id: e.target.value ? Number(e.target.value) : '' })}>
          <option value="">Все жанры</option>
          {GENRES.map((x) => <option key={x.id} value={x.id}>{x.name}</option>)}
        </select>
      </label>
      <label>
        Год
        <select value={String(filters.year)} onChange={(e) => onChange({ year: e.target.value ? Number(e.target.value) : '' })}>
          <option value="">Любой год</option>
          {YEARS.map((y) => <option key={y} value={y}>{y}</option>)}
        </select>
      </label>
      <label>
        Сортировка
        <select value={filters.sort} onChange={(e) => onChange({ sort: e.target.value as Filters['sort'] })}>
          <option value="">По популярности</option>
          <option value="release_date_desc">Сначала новые</option>
          <option value="release_date_asc">Сначала старые</option>
          <option value="rating_desc">Рейтинг ↓</option>
          <option value="rating_asc">Рейтинг ↑</option>
        </select>
      </label>
    </div>
  );
}

function Pagination({ page, totalPages, onPage }: { page: number; totalPages: number; onPage: (p: number) => void }) {
  if (totalPages <= 1) return null;
  return (
    <nav className="pagination" aria-label="Страницы">
      <button className="btn btn--ghost" disabled={page === 1} onClick={() => onPage(page - 1)}>←</button>
      {Array.from({ length: totalPages }, (_, i) => i + 1).map((p) => (
        <button key={p} className={p === page ? 'page page--active' : 'page'} onClick={() => onPage(p)} aria-current={p === page ? 'page' : undefined}>{p}</button>
      ))}
      <button className="btn btn--ghost" disabled={page === totalPages} onClick={() => onPage(page + 1)}>→</button>
    </nav>
  );
}

function AsyncBoundary({ status, error, onRetry, isEmpty, emptyTitle, children }: {
  status: 'loading' | 'success' | 'error';
  error?: string;
  onRetry?: () => void;
  isEmpty?: boolean;
  emptyTitle?: string;
  children: ReactNode;
}) {
  if (status === 'loading') return <Spinner />;
  if (status === 'error') return <ErrorState message={error ?? 'Ошибка сети'} onRetry={onRetry} />;
  if (isEmpty) return <EmptyState title={emptyTitle ?? 'Здесь пока пусто'} />;
  return <>{children}</>;
}

function RequireAuth({ children }: { children: ReactNode }) {
  const { user, loading } = useAuth();
  if (loading) return <Spinner />;
  if (!user) return <Navigate to="/login" replace />;
  return <>{children}</>;
}

function PrivacyNotice({ profile }: { profile: UserProfile }) {
  if (profile.is_restricted_view) {
    return (
      <div className="privacy-notice" role="status">
        🔒 Это закрытый профиль. Доступны только имя пользователя и аватар. Добавьте пользователя в друзья, чтобы
        видеть его списки и рецензии.
      </div>
    );
  }
  if (profile.privacy_mode === 'private') {
    return <div className="privacy-notice">🔒 Профиль закрытый — данные видны вам и подтверждённым друзьям.</div>;
  }
  return null;
}

function FriendButton({ profile }: { profile: UserProfile }) {
  const { user } = useAuth();
  const [status, setStatus] = useState(profile.friend_status);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  if (!user || user.username === profile.username) return null;

  const act = async (fn: () => Promise<unknown>, next: UserProfile['friend_status']) => {
    setBusy(true);
    setError(null);
    const prev = status;
    setStatus(next);
    try {
      await fn();
    } catch (e) {
      setStatus(prev);
      setError(errorMessage(e));
    } finally {
      setBusy(false);
    }
  };

  switch (status) {
    case 'friends':
      return (
        <>
          <button className="btn btn--secondary" disabled={busy} onClick={() => act(() => removeFriend(profile.id), 'none')}>
            Вы в друзьях · удалить
          </button>
          {error && <p className="form__error">{error}</p>}
        </>
      );
    case 'pending_outgoing':
      return <button className="btn btn--active" disabled>Заявка отправлена</button>;
    case 'pending_incoming':
      return (
        <>
          {profile.pending_request_id != null && (
            <button className="btn btn--primary" disabled={busy} onClick={() => act(() => respondFriendRequest(profile.pending_request_id!, true), 'friends')}>
              Принять заявку
            </button>
          )}
          {error && <p className="form__error">{error}</p>}
        </>
      );
    default:
      return (
        <>
          <button className="btn btn--primary" disabled={busy} onClick={() => act(() => sendFriendRequest(profile.id), 'pending_outgoing')}>
            ➕ Добавить в друзья
          </button>
          {error && <p className="form__error">{error}</p>}
        </>
      );
  }
}

function ProfileHeader({ profile }: { profile: UserProfile }) {
  const { user } = useAuth();
  const isMe = user?.username === profile.username;
  return (
    <header className="profile-header panel">
      <Avatar user={profile} size="lg" />
      <div className="profile-header__info">
        <h1>{profile.display_name ?? profile.username}</h1>
        <p className="profile-header__username">@{profile.username}</p>
        {profile.bio && <p className="profile-header__bio">{profile.bio}</p>}
        <div className="profile-header__actions">
          {!isMe && <FriendButton profile={profile} />}
          {isMe && <Link className="btn btn--secondary" to="/profile/me/edit">Редактировать профиль</Link>}
        </div>
      </div>
      <PrivacyNotice profile={profile} />
    </header>
  );
}

const PROFILE_TABS = [
  { key: 'reviews', label: 'Рецензии' },
  { key: 'watchlist', label: 'Хочу посмотреть' },
  { key: 'watched', label: 'Просмотрено' },
  { key: 'favorite', label: 'Избранное' },
] as const;

type ProfileTabKey = (typeof PROFILE_TABS)[number]['key'];

function ProfileTabs({ active, onChange }: { active: ProfileTabKey; onChange: (k: ProfileTabKey) => void }) {
  return (
    <nav className="profile-tabs" role="tablist" aria-label="Разделы профиля">
      {PROFILE_TABS.map((t) => (
        <button key={t.key} role="tab" aria-selected={active === t.key} className={active === t.key ? 'tab tab--active' : 'tab'} onClick={() => onChange(t.key)}>
          {t.label}
        </button>
      ))}
    </nav>
  );
}

function FriendList({ friends }: { friends: FriendItem[] }) {
  const [items, setItems] = useState(friends);

  const drop = async (userId: number) => {
    await removeFriend(userId);
    setItems((prev) => prev.filter((f) => f.user.id !== userId));
  };

  if (items.length === 0) return <p className="form__hint">Список друзей пуст.</p>;

  return (
    <ul className="friend-list">
      {items.map((f) => (
        <li key={f.user.id} className="friend">
          <Avatar user={f.user} size="sm" />
          <div className="friend__who">
            <Link to={`/profile/${f.user.username}`}>{f.user.display_name ?? f.user.username}</Link>
            <span className="form__hint">В друзьях с {f.friends_since}</span>
          </div>
          <button className="btn btn--secondary" onClick={() => drop(f.user.id)}>Удалить</button>
        </li>
      ))}
    </ul>
  );
}

function FriendRequestList({ requests }: { requests: FriendRequestItem[] }) {
  const { user } = useAuth();
  const [items, setItems] = useState(requests);
  const [busyId, setBusyId] = useState<number | null>(null);

  const respond = async (id: number, accept: boolean) => {
    setBusyId(id);
    try {
      await respondFriendRequest(id, accept);
      setItems((prev) => prev.filter((r) => r.request_id !== id));
    } finally {
      setBusyId(null);
    }
  };

  if (items.length === 0) return <p className="form__hint">Новых заявок нет.</p>;

  return (
    <ul className="request-list">
      {items.map((r) => {
        const incoming = r.to.username === user?.username;
        const person = incoming ? r.from : r.to;
        return (
          <li key={r.request_id} className="request">
            <Avatar user={person} size="sm" />
            <div className="request__who">
              <Link to={`/profile/${person.username}`}>{person.display_name ?? person.username}</Link>
              <span className="form__hint">
                {incoming ? 'входящая заявка' : 'исходящая заявка'} · {new Date(r.created_at).toLocaleDateString('ru-RU')}
              </span>
            </div>
            {incoming ? (
              <div className="request__actions">
                <button className="btn btn--primary" disabled={busyId === r.request_id} onClick={() => respond(r.request_id, true)}>Принять</button>
                <button className="btn btn--ghost" disabled={busyId === r.request_id} onClick={() => respond(r.request_id, false)}>Отклонить</button>
              </div>
            ) : (
              <button className="btn btn--active" disabled>Ожидает ответа</button>
            )}
          </li>
        );
      })}
    </ul>
  );
}

function CatalogPage() {
  const [params, setParams] = useSearchParams();
  const filters: Filters = {
    q: params.get('q') ?? '',
    genre_id: params.get('genre_id') ? Number(params.get('genre_id')) : '',
    year: params.get('year') ? Number(params.get('year')) : '',
    sort: (params.get('sort') as Filters['sort']) ?? '',
  };
  const page = Math.max(1, Number(params.get('page') ?? 1));

  const patch = (p: Partial<Filters & { page: number }>) => {
    const next = { ...filters, page, ...p };
    const sp = new URLSearchParams();
    if (next.q) sp.set('q', next.q);
    if (next.genre_id) sp.set('genre_id', String(next.genre_id));
    if (next.year) sp.set('year', String(next.year));
    if (next.sort) sp.set('sort', next.sort);
    if (next.page > 1) sp.set('page', String(next.page));
    setParams(sp);
  };

  return (
    <section>
      <h1 className="page-title">Каталог фильмов</h1>
      <MovieFilters filters={filters} onChange={(p) => patch({ ...p, page: 1 })} />
      <CatalogResults key={params.toString()} filters={filters} page={page} onPage={(p) => patch({ page: p })} />
    </section>
  );
}

const PAGE_SIZE = 12;

function CatalogResults({ filters, page, onPage }: { filters: Filters; page: number; onPage: (p: number) => void }) {
  const [status, setStatus] = useState<'loading' | 'success' | 'error'>('loading');
  const [data, setData] = useState<Page<MovieSummary> | null>(null);
  const [error, setError] = useState<string | undefined>();

  useEffect(() => {
    let cancelled = false;
    setStatus('loading');
    fetchMovies({ ...filters, page, page_size: PAGE_SIZE })
      .then((res) => !cancelled && (setData(res), setStatus('success')))
      .catch((e) => !cancelled && (setError(errorMessage(e)), setStatus('error')));
    return () => { cancelled = true; };
  }, [filters, page]);

  return (
    <AsyncBoundary status={status} error={error} onRetry={() => onPage(page)} isEmpty={!!data && data.items.length === 0} emptyTitle="По текущий фильтрам ничего не найдено">
      {data && (
        <>
          <MovieGrid movies={data.items} />
          <Pagination page={data.page} totalPages={data.total_pages} onPage={onPage} />
        </>
      )}
    </AsyncBoundary>
  );
}

function CriticReviewCard({ review }: { review: CriticReview }) {
  return (
    <li className="review">
      <div className="review__head">
        <span className="review__source">{review.source}</span>
        <span className="review__author">{review.author}</span>
        <span className={`chip ${review.language !== 'ru' ? 'chip--lang' : ''}`}>{review.language.toUpperCase()}</span>
        {review.score_normalized != null && <ScoreBadge score={review.score_normalized} kind="critic" />}
      </div>
      <p className="review__excerpt">«{review.excerpt}»</p>
      {review.verdict && <p className="review__verdict">{review.verdict}</p>}
      <a className="review__link" href={review.external_url} target="_blank" rel="noreferrer noopener">Читать целиком →</a>
    </li>
  );
}

function UserReviewCard({ review }: { review: UserReview }) {
  return (
    <li className="review">
      <div className="review__head">
        <Avatar user={{ username: review.author_username, avatar_url: review.author_avatar_url }} size="sm" />
        <Link to={`/profile/${review.author_username}`} className="review__author">@{review.author_username}</Link>
        <span className="review__date">{new Date(review.created_at).toLocaleDateString('ru-RU')}</span>
        {review.contains_spoilers && <span className="chip chip--spoiler">⚠ Спойлер</span>}
      </div>
      {review.contains_spoilers ? (
        <details className="review__spoiler">
          <summary>Текст скрыт — содержит спойлеры. Показать</summary>
          <p className="review__text">{review.text}</p>
        </details>
      ) : (
        <p className="review__text">{review.text}</p>
      )}
    </li>
  );
}

function ReviewForm({ movieId, initialText = '', initialSpoilers = false, onPublished }: {
  movieId: number;
  initialText?: string;
  initialSpoilers?: boolean;
  onPublished: (text: string, spoilers: boolean) => void;
}) {
  const [text, setText] = useState(initialText);
  const [spoilers, setSpoilers] = useState(initialSpoilers);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await publishReview(movieId, text, spoilers);
      onPublished(text.trim(), spoilers);
      setText('');
      setSpoilers(false);
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setBusy(false);
    }
  };

  return (
    <form className="review-form" onSubmit={submit}>
      <label>
        Ваша рецензия
        <textarea rows={5} value={text} onChange={(e) => setText(e.target.value)} placeholder="Не менее 10 символов…" required />
      </label>
      <label className="checkbox">
        <input type="checkbox" checked={spoilers} onChange={(e) => setSpoilers(e.target.checked)} />
        Содержит спойлеры
      </label>
      {error && <p className="form__error">{error}</p>}
      <button className="btn btn--primary" disabled={busy || text.trim().length < 10}>
        {busy ? 'Публикация…' : initialText ? 'Обновить рецензию' : 'Опубликовать рецензию'}
      </button>
    </form>
  );
}

function RatingPanel({ movie }: { movie: MovieDetail }) {
  const { user } = useAuth();
  const [rating, setRating] = useState<number | null>(movie.my_rating);
  const [lists, setLists] = useState<Set<ListType>>(new Set(movie.my_lists));
  const [review, setReview] = useState<UserReview | null>(movie.my_review);
  const [scoreInput, setScoreInput] = useState(rating?.toString() ?? '');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  if (!user) {
    return (
      <div className="hero__guest-note panel">
        Войдите, чтобы ставить оценки, вести списки и писать рецензии.{' '}
        <Link className="btn btn--primary" to="/login">Войти</Link>
      </div>
    );
  }

  const submitRating = async (e: FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setError(null);
    setNotice(null);
    const score = Number(scoreInput);
    try {
      await rateMovie(movie.id, score);
      setRating(score);
      setNotice(`Ваша оценка: ${score}/10`);
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setBusy(false);
    }
  };

  const removeRating = async () => {
    setBusy(true);
    try {
      await deleteRating(movie.id);
      setRating(null);
      setScoreInput('');
      setNotice('Оценка удалена.');
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setBusy(false);
    }
  };

  const toggleList = async (type: ListType) => {
    setBusy(true);
    setError(null);
    const prev = new Set(lists);
    const add = !prev.has(type);
    if (add) prev.add(type); else prev.delete(type);
    setLists(prev);
    try {
      await setList(movie.id, type, add);
    } catch (err) {
      setLists(new Set(movie.my_lists));
      setError(errorMessage(err));
    } finally {
      setBusy(false);
    }
  };

  const LIST_LABELS: Record<ListType, string> = { watchlist: '📌 Планирую посмотреть', watched: '👁 Просмотрено', favorite: '★ Избранное' };

  return (
    <section className="panel">
      <h2>Моя активность</h2>
      <div className="rating-form">
        {rating == null ? (
          <form onSubmit={submitRating} aria-label="Поставить оценку">
            <label>
              Оценка (целое от 1 до 10)
              <div className="rating-form__row">
                <input type="number" min={1} max={10} step={1} value={scoreInput} onChange={(e) => setScoreInput(e.target.value)} required />
                <button className="btn btn--primary" disabled={busy}>Поставить</button>
              </div>
            </label>
          </form>
        ) : (
          <div className="rating-form__row">
            <ScoreBadge score={rating} kind="user" />
            <button className="btn btn--secondary" disabled={busy} onClick={() => setScoreInput(String(rating))}>Изменить</button>
            <button className="btn btn--ghost" disabled={busy} onClick={removeRating}>Удалить оценку</button>
            {scoreInput !== '' && scoreInput !== String(rating) && (
              <form onSubmit={submitRating} className="rating-form__row">
                <input type="number" min={1} max={10} step={1} value={scoreInput} onChange={(e) => setScoreInput(e.target.value)} aria-label="Новая оценка" />
                <button className="btn btn--primary" disabled={busy}>Сохранить</button>
              </form>
            )}
            {scoreInput === '' && (
              <form onSubmit={submitRating} className="rating-form__row">
                <input type="number" min={1} max={10} step={1} placeholder="N" aria-label="Новая оценка" onChange={(e) => setScoreInput(e.target.value)} />
                <button className="btn btn--primary" disabled={busy}>OK</button>
              </form>
            )}
          </div>
        )}
        {error && <p className="form__error">{error}</p>}
        {notice && <p className="form__ok">{notice}</p>}
      </div>
      <div className="hero__actions">
        {(Object.keys(LIST_LABELS) as ListType[]).map((t) => (
          <button key={t} className={lists.has(t) ? 'btn btn--active' : 'btn btn--secondary'} disabled={busy} onClick={() => toggleList(t)}>
            {LIST_LABELS[t]}
          </button>
        ))}
      </div>
      {review ? (
        <>
          <UserReviewCard review={review} />
          <ReviewForm movieId={movie.id} initialText={review.text} initialSpoilers={review.contains_spoilers} onPublished={(text, spoilers) => setReview({ ...review, text, contains_spoilers: spoilers })} />
        </>
      ) : (
        <ReviewForm movieId={movie.id} onPublished={(text, spoilers) => setReview({ id: Date.now(), movie_id: movie.id, author_username: user.username, author_avatar_url: user.avatar_url, text, contains_spoilers: spoilers, created_at: new Date().toISOString() })} />
      )}
    </section>
  );
}

function MovieDetailPage() {
  const { id: rawId } = useParams();
  const movieId = Number(rawId);
  const [status, setStatus] = useState<'loading' | 'success' | 'error'>('loading');
  const [movie, setMovie] = useState<MovieDetail | null>(null);
  const [reviews, setReviews] = useState<CriticReview[]>([]);
  const [langFilter, setLangFilter] = useState<'all' | 'ru' | 'en'>('all');
  const [error, setError] = useState<string | undefined>();

  useEffect(() => {
    let cancelled = false;
    setStatus('loading');
    Promise.all([fetchMovie(movieId), fetchCriticReviews(movieId)])
      .then(([m, cr]) => {
        if (cancelled) return;
        setMovie(m);
        setReviews(cr);
        setStatus('success');
      })
      .catch((e) => !cancelled && (setError(errorMessage(e)), setStatus('error')));
    return () => { cancelled = true; };
  }, [movieId]);

  if (status !== 'success' || !movie) {
    return <AsyncBoundary status={status} error={error} onRetry={() => setMovie(toDetail(movieId) ?? null)} children={null} />;
  }

  const visibleReviews = langFilter === 'all' ? reviews : reviews.filter((r) => r.language === langFilter);

  return (
    <article>
      <header className="hero">
        {movie.poster_url ? (
          <img className="hero__poster" src={movie.poster_url} alt={`Постер: ${movie.title}`} />
        ) : (
          <div className="hero__poster hero__poster--missing">Нет постера</div>
        )}
        <div className="hero__info">
          <h1 className="hero__title">{movie.title}</h1>
          <p className="hero__meta">
            {yearOf(movie.release_date)} · {movie.runtime_minutes} мин · {movie.genres.map((x) => x.name).join(', ') || 'Без жанра'}
          </p>
          <div className="movie-card__scores">
            <ScoreBadge score={movie.user_score} kind="user" />
            <ScoreBadge score={movie.critic_score} kind="critic" />
          </div>
          <p className="hero__overview">{movie.overview}</p>
          <RatingPanel movie={movie} />
        </div>
      </header>

      <section className="panel review-list" aria-label="Рецензии критиков">
        <h2>Рецензии критиков</h2>
        <div className="hero__actions" role="group" aria-label="Фильтр по языку">
          {(['all', 'ru', 'en'] as const).map((l) => (
            <button key={l} className={langFilter === l ? 'btn btn--active' : 'btn btn--secondary'} onClick={() => setLangFilter(l)}>
              {l === 'all' ? 'Все' : l.toUpperCase()}
            </button>
          ))}
        </div>
        {visibleReviews.length === 0 ? (
          <EmptyState title="Рецензий на выбранном языке нет" hint="Переключите фильтр, чтобы увидеть другие публикации." />
        ) : (
          <ul>
            {visibleReviews.map((r) => <CriticReviewCard key={r.id} review={r} />)}
          </ul>
        )}
      </section>
    </article>
  );
}

function AuthTabs({ mode, onMode }: { mode: 'login' | 'register'; onMode: (m: 'login' | 'register') => void }) {
  return (
    <nav className="profile-tabs" role="tablist" aria-label="Форма входа">
      <button role="tab" aria-selected={mode === 'login'} className={mode === 'login' ? 'tab tab--active' : 'tab'} onClick={() => onMode('login')}>Вход</button>
      <button role="tab" aria-selected={mode === 'register'} className={mode === 'register' ? 'tab tab--active' : 'tab'} onClick={() => onMode('register')}>Регистрация</button>
    </nav>
  );
}

function AuthPage() {
  const [mode, setMode] = useState<'login' | 'register'>('login');
  const [email, setEmail] = useState('');
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const { login: doLogin, register: doRegister, user } = useAuth();
  const navigate = useNavigate();

  useEffect(() => {
    if (user) navigate('/', { replace: true });
  }, [user, navigate]);

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      if (mode === 'login') await doLogin(email, password);
      else await doRegister(email, username, password);
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setBusy(false);
    }
  };

  return (
    <section className="page-narrow">
      <h1 className="page-title">{mode === 'login' ? 'Вход в Movie Service' : 'Создать аккаунт'}</h1>
      <AuthTabs mode={mode} onMode={setMode} />
      <form className="auth-form panel" onSubmit={submit}>
        <label>Email<input type="email" value={email} onChange={(e) => setEmail(e.target.value)} autoComplete="email" required /></label>
        {mode === 'register' && (
          <label>
            Username
            <input value={username} onChange={(e) => setUsername(e.target.value)} minLength={3} maxLength={30} pattern="[a-zA-Z0-9_]+" required />
            <span className="form__hint">3–30 символов: латиница, цифры, знак подчёркивания.</span>
          </label>
        )}
        <label>
          Пароль
          <input type="password" value={password} onChange={(e) => setPassword(e.target.value)} minLength={mode === 'register' ? 8 : undefined} required />
          {mode === 'register' && <span className="form__hint">Минимум 8 символов.</span>}
        </label>
        {error && <p className="form__error" role="alert">{error}</p>}
        <button className="btn btn--primary btn--block" disabled={busy}>{busy ? 'Подождите…' : mode === 'login' ? 'Войти' : 'Зарегистрироваться'}</button>
      </form>
    </section>
  );
}

function EditProfilePage() {
  const { user, updateUser } = useAuth();
  const [displayName, setDisplayName] = useState(user?.display_name ?? '');
  const [bio, setBio] = useState(user?.bio ?? '');
  const [privacy, setPrivacy] = useState<PrivacyMode>(user?.privacy_mode ?? 'open');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [saved, setSaved] = useState(false);
  const navigate = useNavigate();

  if (!user) return <Navigate to="/login" replace />;

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setError(null);
    setSaved(false);
    try {
      const updated = await patchProfile({ display_name: displayName || null, bio: bio || null, privacy_mode: privacy });
      updateUser(updated);
      setSaved(true);
      setTimeout(() => navigate(`/profile/${user.username}`), 600);
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setBusy(false);
    }
  };

  return (
    <section className="page-narrow">
      <h1 className="page-title">Редактирование профиля</h1>
      <form className="profile-form panel" onSubmit={submit}>
        <label>Имя для отображения<input value={displayName} onChange={(e) => setDisplayName(e.target.value)} maxLength={60} /></label>
        <label>
          О себе
          <textarea rows={4} value={bio} onChange={(e) => setBio(e.target.value)} maxLength={500} />
          <span className="form__hint">{bio.length}/500</span>
        </label>
        <fieldset>
          <legend>Приватность</legend>
          <label className="radio">
            <input type="radio" name="privacy" value="open" checked={privacy === 'open'} onChange={() => setPrivacy('open')} />
            Открытый — списки и рецензии видят все
          </label>
          <label className="radio">
            <input type="radio" name="privacy" value="private" checked={privacy === 'private'} onChange={() => setPrivacy('private')} />
            Закрытый — только подтверждённые друзья
          </label>
        </fieldset>
        {error && <p className="form__error">{error}</p>}
        {saved && <p className="form__ok">Профиль обновлён ✓</p>}
        <button className="btn btn--primary" disabled={busy}>{busy ? 'Сохранение…' : 'Сохранить'}</button>
      </form>
    </section>
  );
}

function ProfilePage() {
  const { username } = useParams();
  const [status, setStatus] = useState<'loading' | 'success' | 'error'>('loading');
  const [profile, setProfile] = useState<UserProfile | null>(null);
  const [tab, setTab] = useState<ProfileTabKey>('reviews');
  const [reviews, setReviews] = useState<UserReview[]>([]);
  const [movies, setMovies] = useState<MovieSummary[]>([]);
  const [error, setError] = useState<string | undefined>();

  useEffect(() => {
    if (!username) return;
    let cancelled = false;
    setStatus('loading');
    fetchUser(username)
      .then(async (u) => {
        if (cancelled) return;
        setProfile(u);
        setStatus('success');
      })
      .catch((e) => !cancelled && (setError(errorMessage(e)), setStatus('error')));
    return () => { cancelled = true; };
  }, [username]);

  useEffect(() => {
    if (!username || !profile || profile.is_restricted_view) return;
    let cancelled = false;
    if (tab === 'reviews') {
      fetchUserReviews(username).then((r) => !cancelled && setReviews(r)).catch(() => undefined);
    } else {
      fetchUserList(username, tab).then((m) => !cancelled && setMovies(m)).catch(() => undefined);
    }
    return () => { cancelled = true; };
  }, [username, tab, profile]);

  if (status === 'loading') return <Spinner />;
  if (status === 'error' || !profile) return <ErrorState message={error ?? 'Пользователь не найден'} onRetry={() => username && fetchUser(username).then(setProfile)} />;

  return (
    <section>
      <ProfileHeader profile={profile} />
      {!profile.is_restricted_view && <ProfileTabs active={tab} onChange={setTab} />}
      {profile.is_restricted_view ? null : tab === 'reviews' ? (
        <ul className="profile-reviews panel">
          {reviews.length === 0 && <EmptyState title="Рецензий пока нет" />}
          {reviews.map((r) => (
            <li key={r.id}>
              <Link to={`/movies/${r.movie_id}`}>{r.movie_title}</Link>
              <p>{r.text}</p>
              {r.contains_spoilers && <span className="chip chip--spoiler">⚠ Спойлер</span>}
            </li>
          ))}
        </ul>
      ) : (
        <AsyncBoundary status="success" isEmpty={movies.length === 0} emptyTitle="В этом списке пока пусто">
          <MovieGrid movies={movies} />
        </AsyncBoundary>
      )}
    </section>
  );
}

const LIST_TYPES: Record<string, string> = {
  watchlist: 'Планирую посмотреть',
  watched: 'Просмотрено',
  favorite: 'Избранное',
};

function ListsPage() {
  const { type } = useParams();
  const { user } = useAuth();
  const listType = (type ?? 'watchlist') as ListType;
  const [status, setStatus] = useState<'loading' | 'success' | 'error'>('loading');
  const [items, setItems] = useState<MovieSummary[]>([]);
  const [error, setError] = useState<string | undefined>();

  useEffect(() => {
    if (!user) return;
    let cancelled = false;
    setStatus('loading');
    fetchUserList(user.username, listType)
      .then((res) => !cancelled && (setItems(res), setStatus('success')))
      .catch((e) => !cancelled && (setError(errorMessage(e)), setStatus('error')));
    return () => { cancelled = true; };
  }, [user, listType]);

  if (!(listType in LIST_TYPES)) return <Navigate to="/lists/watchlist" replace />;

  return (
    <section>
      <h1 className="page-title">{LIST_TYPES[listType]}</h1>
      <nav className="profile-tabs" aria-label="Списки">
        {(Object.keys(LIST_TYPES) as ListType[]).map((t) => (
          <NavLink key={t} to={`/lists/${t}`} className={t === listType ? 'tab tab--active' : 'tab'}>{LIST_TYPES[t]}</NavLink>
        ))}
      </nav>
      <AsyncBoundary status={status} error={error} isEmpty={items.length === 0} emptyTitle="Список пуст — добавьте фильмы из каталога">
        <MovieGrid movies={items} />
      </AsyncBoundary>
    </section>
  );
}

function FriendsPage() {
  const [status, setStatus] = useState<'loading' | 'success' | 'error'>('loading');
  const [friends, setFriends] = useState<FriendItem[]>([]);
  const [requests, setRequests] = useState<FriendRequestItem[]>([]);
  const [error, setError] = useState<string | undefined>();

  useEffect(() => {
    let cancelled = false;
    setStatus('loading');
    Promise.all([fetchFriends(), fetchFriendRequests()])
      .then(([f, r]) => !cancelled && (setFriends(f), setRequests(r), setStatus('success')))
      .catch((e) => !cancelled && (setError(errorMessage(e)), setStatus('error')));
    return () => { cancelled = true; };
  }, []);

  return (
    <section>
      <h1 className="page-title">Друзья</h1>
      <AsyncBoundary status={status} error={error} onRetry={() => setStatus('loading')}>
        <div className="panel">
          <h2>Заявки в друзья</h2>
          <FriendRequestList requests={requests} />
        </div>
        <div className="panel">
          <h2>Мои друзья</h2>
          <FriendList friends={friends} />
        </div>
      </AsyncBoundary>
    </section>
  );
}

function AdminPage() {
  const { user } = useAuth();
  const [syncing, setSyncing] = useState(false);
  const [syncLog, setSyncLog] = useState<string[]>([]);
  const [reviews, setReviews] = useState<CriticReview[]>(() => criticReviewsFor(1));

  if (!user || user.role !== 'admin') {
    return <EmptyState title="Доступ запрещён" hint="Раздел администрирования доступен только роли admin." />;
  }

  const runSync = async () => {
    setSyncing(true);
    setSyncLog((l) => [...l, `[${new Date().toLocaleTimeString('ru-RU')}] Запущена синхронизация каталога с TMDB…`]);
    try {
      const res = await syncMovies();
      setSyncLog((l) => [...l, `[${new Date().toLocaleTimeString('ru-RU')}] Готово: обновлено ${res.synced} фильмов.`]);
    } catch (e) {
      setSyncLog((l) => [...l, `[${new Date().toLocaleTimeString('ru-RU')}] Ошибка: ${errorMessage(e)}`]);
    } finally {
      setSyncing(false);
    }
  };

  return (
    <section>
      <h1 className="page-title">Администрирование</h1>
      <div className="panel">
        <h2>Синхронизация каталога</h2>
        <div className="admin-actions">
          <button className="btn btn--primary" onClick={runSync} disabled={syncing}>{syncing ? 'Синхронизация…' : '▶ Запустить синхронизацию'}</button>
        </div>
        {syncLog.length > 0 && (
          <pre style={{ whiteSpace: 'pre-wrap', background: 'var(--bg-soft)', padding: 12, borderRadius: 8 }}>
            {syncLog.join('\n')}
          </pre>
        )}
      </div>
      <div className="panel">
        <h2>Модерация рецензий критиков</h2>
        {reviews.length === 0 ? (
          <EmptyState title="Все рецензии проверены" />
        ) : (
          <ul className="admin-review-list">
            {reviews.map((r) => (
              <li key={r.id}>
                <span>{r.source} — {r.author}</span>
                <button className="btn btn--ghost" onClick={() => setReviews((prev) => prev.filter((x) => x.id !== r.id))}>
                  Удалить
                </button>
              </li>
            ))}
          </ul>
        )}
      </div>
    </section>
  );
}

export default function App() {
  return (
    <HashRouter>
      <AuthProvider>
        <AppLayout>
          <Routes>
            <Route path="/" element={<CatalogPage />} />
            <Route path="/movies/:id" element={<MovieDetailPage />} />
            <Route path="/login" element={<AuthPage />} />
            <Route path="/register" element={<AuthPage />} />
            <Route path="/profile/me/edit" element={<RequireAuth><EditProfilePage /></RequireAuth>} />
            <Route path="/profile/:username" element={<ProfilePage />} />
            <Route path="/lists/:type" element={<RequireAuth><ListsPage /></RequireAuth>} />
            <Route path="/friends" element={<RequireAuth><FriendsPage /></RequireAuth>} />
            <Route path="/admin" element={<RequireAuth><AdminPage /></RequireAuth>} />
            <Route path="*" element={<EmptyState title="Страница не найдена" hint="Проверьте адрес или вернитесь в каталог." />} />
          </Routes>
        </AppLayout>
      </AuthProvider>
    </HashRouter>
  );
}
