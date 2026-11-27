import axios from 'axios';
import type { InternalAxiosRequestConfig, AxiosResponse } from 'axios';
const STORAGE_KEY = 'movie_service_mock_db_v3';

interface MockDB {
  currentUser: any | null;
  users: any[];
  movies: any[];
  userLists: Record<string, { watchlist: string[]; watched: string[]; favorite: string[] }>;
  ratings: Record<string, Record<string, number>>;
  reviews: any[];
  friendRequests: any[];
  friendships: Record<string, string[]>;
}

const getInitialDB = (): MockDB => {
  const saved = localStorage.getItem(STORAGE_KEY);
  if (saved) {
    try {
      return JSON.parse(saved);
    } catch {
      // fallback
    }
  }

  const defaultUser = {
    id: 'user_1',
    username: 'alex_cinema',
    email: 'alex@example.com',
    display_name: 'Александр Киноман',
    bio: 'Обожаю хорошее кино и научную фантастику 🚀',
    avatar_url: 'https://images.unsplash.com/photo-1535713875002-d1d0cf377fde?w=150',
    is_private: false,
  };

  const defaultMovies = [
    {
      id: '1',
      title: 'Интерстеллар',
      year: 2014,
      poster_url: 'https://images.unsplash.com/photo-1618005182384-a83a8bd57fbe?w=500',
      genres: ['Фантастика', 'Драма', 'Приключения'],
      duration: 169,
      description: 'Когда засуха, пыльные бури и вымирание растений приводят человечество к продовольственному кризису, коллектив исследователей и ученых отправляется сквозь червоточину в путешествие.',
    },
    {
      id: '2',
      title: 'Начало',
      year: 2010,
      poster_url: 'https://images.unsplash.com/photo-1594909122845-11baa439b7bf?w=500',
      genres: ['Фантастика', 'Боевик', 'Триллеры'],
      duration: 148,
      description: 'Кобб — талантливый вор, лучший в опасном искусстве извлечения: он крадет ценные секреты из глубин подсознания во время сна.',
    },
    {
      id: '3',
      title: 'Побег из Шоушенка',
      year: 1994,
      poster_url: 'https://images.unsplash.com/photo-1485846234645-a62644f84728?w=500',
      genres: ['Драма'],
      duration: 142,
      description: 'Бухгалтер Энди Дюфрейн обвинен в убийстве собственной жены и ее любовника. Оказавшись в Шоушенке, он сталкивается с жестокостью.',
    },
    {
      id: '4',
      title: 'Темный рыцарь',
      year: 2008,
      poster_url: 'https://images.unsplash.com/photo-1509198397868-475647b2a1e5?w=500',
      genres: ['Боевик', 'Криминал', 'Драма'],
      duration: 152,
      description: 'Бэтмен поднимает ставки в войне с криминалом. С помощью лейтенанта Джима Гордона и прокурора Харви Дента он намерен очистить улицы.',
    },
    {
      id: '5',
      title: 'Паразиты',
      year: 2019,
      poster_url: 'https://images.unsplash.com/photo-1536440136628-849c177e76a1?w=500',
      genres: ['Триллер', 'Комедия', 'Драма'],
      duration: 132,
      description: 'Обычная корейская семья Ким живет в сыром полуподвале. Случайная возможность меняет их жизнь.',
    },
    {
      id: '6',
      title: 'Дюна: Часть вторая',
      year: 2024,
      poster_url: 'https://images.unsplash.com/photo-1534447677768-be436bb09401?w=500',
      genres: ['Фантастика', 'Приключения', 'Драма'],
      duration: 166,
      description: 'Пол Атрейдес объединяется с чани и фрименами, пытаясь отомстить заговорщикам.',
    }
  ];

  const initialDB: MockDB = {
    currentUser: defaultUser,
    users: [
      defaultUser,
      {
        id: 'user_2',
        username: 'elena_critic',
        email: 'elena@example.com',
        display_name: 'Елена Кинокритик',
        bio: 'Пишу рецензии на артхаус и блокбастеры ☕',
        avatar_url: 'https://images.unsplash.com/photo-1494790108377-be9c29b29330?w=150',
        is_private: true,
      }
    ],
    movies: defaultMovies,
    userLists: {
      alex_cinema: {
        watchlist: ['3', '6'],
        watched: ['1', '2'],
        favorite: ['1', '4']
      },
      elena_critic: {
        watchlist: ['5'],
        watched: ['3'],
        favorite: ['3', '5']
      }
    },
    ratings: {
      alex_cinema: { '1': 10, '2': 9 }
    },
    reviews: [
      {
        id: 'rev_1',
        movieId: '1',
        authorUsername: 'elena_critic',
        text: 'Шедевр Нолана с потрясающей музыкой Циммера. Концовка заставляет задуматься.',
        created_at: new Date().toISOString(),
        is_spoiler: false,
      }
    ],
    friendRequests: [
      { id: 'req_1', senderUsername: 'elena_critic', receiverUsername: 'alex_cinema' }
    ],
    friendships: {
      alex_cinema: [],
      elena_critic: []
    }
  };

  localStorage.setItem(STORAGE_KEY, JSON.stringify(initialDB));
  return initialDB;
};

const saveDB = (db: MockDB) => {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(db));
};

export const apiClient = axios.create({
  baseURL: '/api',
  withCredentials: true,
  headers: { 'Content-Type': 'application/json' },
});

// Используем кастомный адаптер Axios для полной эмуляции бэкенда
apiClient.defaults.adapter = async (config: InternalAxiosRequestConfig): Promise<AxiosResponse> => {
  const db = getInitialDB();
  const rawUrl = config.url || '';
  const url = rawUrl.startsWith('/api') ? rawUrl.replace(/^\/api/, '') : rawUrl;
  const method = config.method?.toLowerCase();
  
  let parsedData: any = null;
  if (config.data) {
    try {
      parsedData = typeof config.data === 'string' ? JSON.parse(config.data) : config.data;
    } catch {
      parsedData = config.data;
    }
  }

  await new Promise((res) => setTimeout(res, 100));
  console.log(`[MockAdapter] ${method?.toUpperCase()} -> ${url}`, parsedData || '');

  const createResponse = (status: number, data: any): AxiosResponse => ({
    data,
    status,
    statusText: status >= 200 && status < 300 ? 'OK' : 'Error',
    headers: {},
    config,
  });

  try {
    if (url === '/auth/me' && method === 'get') {
      if (!db.currentUser) return createResponse(401, { detail: 'Unauthorized' });
      return createResponse(200, db.currentUser);
    }

    if (url === '/auth/login' && method === 'post') {
      const { username_or_email } = parsedData || {};
      const found = db.users.find(
        (u) => u.username === username_or_email || u.email === username_or_email
      );
      if (!found) return createResponse(400, { detail: 'Пользователь не найден' });
      db.currentUser = found;
      saveDB(db);
      return createResponse(200, found);
    }

    if (url === '/auth/register' && method === 'post') {
      const { username, email } = parsedData || {};
      if (db.users.some((u) => u.username === username)) {
        return createResponse(400, { detail: 'Имя пользователя уже занято' });
      }
      const newUser = {
        id: 'user_' + Date.now(),
        username,
        email,
        display_name: username,
        bio: '',
        avatar_url: 'https://images.unsplash.com/photo-1570295999919-56ceb5ecca61?w=150',
        is_private: false,
      };
      db.users.push(newUser);
      db.userLists[username] = { watchlist: [], watched: [], favorite: [] };
      saveDB(db);
      return createResponse(200, { success: true });
    }

    if (url === '/auth/logout' && method === 'post') {
      db.currentUser = null;
      saveDB(db);
      return createResponse(200, { success: true });
    }

    if (url === '/movies' && method === 'get') {
      const params = config.params || {};
      let result = [...db.movies];

      const currUsername = db.currentUser?.username;
      const userFavs = currUsername ? db.userLists[currUsername]?.favorite || [] : [];

      result = result.map((m) => ({
        ...m,
        is_favorite: userFavs.includes(m.id),
      }));

      if (params.search) {
        const q = params.search.toLowerCase();
        result = result.filter((m) => m.title.toLowerCase().includes(q));
      }
      if (params.genre) {
        result = result.filter((m) => m.genres.includes(params.genre));
      }
      if (params.year) {
        result = result.filter((m) => m.year === Number(params.year));
      }

      const page = Number(params.page) || 1;
      const limit = Number(params.limit) || 12;
      const total = result.length;
      const pages = Math.ceil(total / limit) || 1;
      const items = result.slice((page - 1) * limit, page * limit);

      return createResponse(200, { items, total, page, pages });
    }

    if (url === '/movies/genres' && method === 'get') {
      const allGenres = Array.from(new Set(db.movies.flatMap((m) => m.genres)));
      return createResponse(200, allGenres);
    }

    const favMatch = url.match(/^\/movies\/([^/]+)\/favorite$/);
    if (favMatch && method === 'post') {
      const movieId = favMatch[1];
      const username = db.currentUser?.username;
      if (!username) return createResponse(401, { detail: 'Unauthorized' });

      if (!db.userLists[username]) {
        db.userLists[username] = { watchlist: [], watched: [], favorite: [] };
      }
      const favs = db.userLists[username].favorite;
      const idx = favs.indexOf(movieId);
      let is_favorite = false;
      if (idx > -1) {
        favs.splice(idx, 1);
      } else {
        favs.push(movieId);
        is_favorite = true;
      }
      saveDB(db);
      return createResponse(200, { is_favorite });
    }

    const movieDetailMatch = url.match(/^\/movies\/([^/]+)$/);
    if (movieDetailMatch && method === 'get') {
      const movieId = movieDetailMatch[1];
      const movie = db.movies.find((m) => m.id === movieId);
      if (!movie) return createResponse(404, { detail: 'Not found' });

      const username = db.currentUser?.username;
      let user_status = null;
      if (username && db.userLists[username]) {
        if (db.userLists[username].watchlist.includes(movieId)) user_status = 'watchlist';
        else if (db.userLists[username].watched.includes(movieId)) user_status = 'watched';
        else if (db.userLists[username].favorite.includes(movieId)) user_status = 'favorite';
      }

      const user_rating = username ? db.ratings[username]?.[movieId] || null : null;
      const user_review = username
        ? db.reviews.find((r) => r.movieId === movieId && r.authorUsername === username) || null
        : null;

      const movieReviews = db.reviews
        .filter((r) => r.movieId === movieId)
        .map((r) => {
          const author = db.users.find((u) => u.username === r.authorUsername);
          return {
            ...r,
            author: {
              username: author?.username || r.authorUsername,
              display_name: author?.display_name || r.authorUsername,
              avatar_url: author?.avatar_url,
            },
          };
        });

      return createResponse(200, {
        ...movie,
        user_rating,
        user_status,
        user_review,
        reviews: movieReviews,
        critic_reviews: [
          {
            id: 'c_1',
            source: 'КиноПоиск',
            critic: 'Иван Петров',
            excerpt: 'Впечатляющая визуальная составляющая и глубокая атмосфера.',
            url: 'https://google.com',
          }
        ],
      });
    }

    const rateMatch = url.match(/^\/movies\/([^/]+)\/rating$/);
    if (rateMatch && method === 'post') {
      const movieId = rateMatch[1];
      const { rating } = parsedData || {};
      const username = db.currentUser?.username;
      if (!username) return createResponse(401, { detail: 'Unauthorized' });

      if (!db.ratings[username]) db.ratings[username] = {};
      if (rating === null) {
        delete db.ratings[username][movieId];
      } else {
        db.ratings[username][movieId] = rating;
      }
      saveDB(db);
      return createResponse(200, { success: true });
    }

    const statusMatch = url.match(/^\/movies\/([^/]+)\/status$/);
    if (statusMatch && method === 'post') {
      const movieId = statusMatch[1];
      const { status } = (parsedData || {}) as { status: 'watchlist' | 'watched' | 'favorite' | null };
      const username = db.currentUser?.username;
      if (!username) return createResponse(401, { detail: 'Unauthorized' });

      if (!db.userLists[username]) {
        db.userLists[username] = { watchlist: [], watched: [], favorite: [] };
      }
      const lists = db.userLists[username];
      lists.watchlist = lists.watchlist.filter((id: string) => id !== movieId);
      lists.watched = lists.watched.filter((id: string) => id !== movieId);
      lists.favorite = lists.favorite.filter((id: string) => id !== movieId);

      if (status && (status === 'watchlist' || status === 'watched' || status === 'favorite')) {
        lists[status].push(movieId);
      }
      saveDB(db);
      return createResponse(200, { success: true });
    }

    const reviewMatch = url.match(/^\/movies\/([^/]+)\/review$/);
    if (reviewMatch) {
      const movieId = reviewMatch[1];
      const username = db.currentUser?.username;
      if (!username) return createResponse(401, { detail: 'Unauthorized' });

      if (method === 'post') {
        const { text, is_spoiler } = parsedData || {};
        db.reviews = db.reviews.filter((r) => !(r.movieId === movieId && r.authorUsername === username));
        const newRev = {
          id: 'rev_' + Date.now(),
          movieId,
          authorUsername: username,
          text,
          created_at: new Date().toISOString(),
          is_spoiler: Boolean(is_spoiler),
        };
        db.reviews.push(newRev);
        saveDB(db);
        return createResponse(200, newRev);
      }
      if (method === 'delete') {
        db.reviews = db.reviews.filter((r) => !(r.movieId === movieId && r.authorUsername === username));
        saveDB(db);
        return createResponse(200, { success: true });
      }
    }

    const profileMatch = url.match(/^\/users\/([^/]+)$/);
    if (profileMatch && method === 'get') {
      const targetUsername = profileMatch[1];
      const user = db.users.find((u) => u.username === targetUsername);
      if (!user) return createResponse(404, { detail: 'User not found' });

      const currUsername = db.currentUser?.username;
      const is_friend = currUsername ? (db.friendships[currUsername] || []).includes(targetUsername) : false;
      const pending_request = db.friendRequests.some(
        (r) => r.senderUsername === currUsername && r.receiverUsername === targetUsername
      );

      const userListsData = db.userLists[targetUsername] || { watchlist: [], watched: [], favorite: [] };
      const listsResolved = {
        watchlist: userListsData.watchlist.map((id: string) => db.movies.find((m) => m.id === id)).filter(Boolean),
        watched: userListsData.watched.map((id: string) => db.movies.find((m) => m.id === id)).filter(Boolean),
        favorite: userListsData.favorite.map((id: string) => db.movies.find((m) => m.id === id)).filter(Boolean),
      };

      const userRatings = db.ratings[targetUsername] || {};
      const ratingsResolved = Object.entries(userRatings).map(([movieId, rating]) => ({
        movie: db.movies.find((m) => m.id === movieId),
        rating,
      })).filter((item) => item.movie);

      const userReviewsResolved = db.reviews
        .filter((r) => r.authorUsername === targetUsername)
        .map((r) => ({
          ...r,
          movie: db.movies.find((m) => m.id === r.movieId) || { id: r.movieId, title: 'Фильм' },
        }));

      return createResponse(200, {
        ...user,
        is_friend,
        pending_request,
        lists: listsResolved,
        ratings: ratingsResolved,
        reviews: userReviewsResolved,
      });
    }

    if (url === '/users/me' && method === 'put') {
      const username = db.currentUser?.username;
      if (!username) return createResponse(401, { detail: 'Unauthorized' });

      const user = db.users.find((u) => u.username === username);
      if (user) {
        Object.assign(user, parsedData || {});
        db.currentUser = { ...user };
        saveDB(db);
      }
      return createResponse(200, db.currentUser);
    }

    const listMatch = url.match(/^\/lists\/(watchlist|watched|favorite)$/);
    if (listMatch && method === 'get') {
      const listType = listMatch[1] as 'watchlist' | 'watched' | 'favorite';
      const username = db.currentUser?.username;
      if (!username) return createResponse(401, { detail: 'Unauthorized' });

      if (!db.userLists[username]) {
        db.userLists[username] = { watchlist: [], watched: [], favorite: [] };
      }
      const ids = db.userLists[username][listType] || [];
      const items = ids.map((id: string) => {
        const m = db.movies.find((movie) => movie.id === id);
        const userFavs = db.userLists[username].favorite || [];
        const userRating = db.ratings[username]?.[id];
        return m ? { ...m, is_favorite: userFavs.includes(m.id), rating: userRating } : null;
      }).filter(Boolean);

      return createResponse(200, { items, total: items.length, page: 1, pages: 1 });
    }

    if (url === '/friends' && method === 'get') {
      const username = db.currentUser?.username;
      const friendNames = username ? db.friendships[username] || [] : [];
      const friends = friendNames.map((fn: string) => db.users.find((u) => u.username === fn)).filter(Boolean);
      return createResponse(200, friends);
    }

    if (url === '/friends/request' && method === 'post') {
      const { username: targetName } = parsedData || {};
      const currName = db.currentUser?.username;
      if (!currName) return createResponse(401, { detail: 'Unauthorized' });

      db.friendRequests.push({
        id: 'req_' + Date.now(),
        senderUsername: currName,
        receiverUsername: targetName,
      });
      saveDB(db);
      return createResponse(200, { success: true });
    }

    if (url === '/friends/requests/incoming' && method === 'get') {
      const username = db.currentUser?.username;
      const incoming = db.friendRequests.filter((r) => r.receiverUsername === username);
      const result = incoming.map((req) => ({
        id: req.id,
        sender: db.users.find((u) => u.username === req.senderUsername),
        created_at: new Date().toISOString(),
      })).filter((item) => item.sender);
      return createResponse(200, result);
    }

    const acceptMatch = url.match(/^\/friends\/requests\/([^/]+)\/accept$/);
    if (acceptMatch && method === 'post') {
      const reqId = acceptMatch[1];
      const req = db.friendRequests.find((r) => r.id === reqId);
      if (req) {
        db.friendRequests = db.friendRequests.filter((r) => r.id !== reqId);
        if (!db.friendships[req.senderUsername]) db.friendships[req.senderUsername] = [];
        if (!db.friendships[req.receiverUsername]) db.friendships[req.receiverUsername] = [];
        if (!db.friendships[req.senderUsername].includes(req.receiverUsername)) {
          db.friendships[req.senderUsername].push(req.receiverUsername);
        }
        if (!db.friendships[req.receiverUsername].includes(req.senderUsername)) {
          db.friendships[req.receiverUsername].push(req.senderUsername);
        }
        saveDB(db);
      }
      return createResponse(200, { success: true });
    }

    const declineMatch = url.match(/^\/friends\/requests\/([^/]+)\/decline$/);
    if (declineMatch && method === 'post') {
      const reqId = declineMatch[1];
      db.friendRequests = db.friendRequests.filter((r) => r.id !== reqId);
      saveDB(db);
      return createResponse(200, { success: true });
    }

    const removeFriendMatch = url.match(/^\/friends\/([^/]+)$/);
    if (removeFriendMatch && method === 'delete') {
      const targetName = removeFriendMatch[1];
      const currName = db.currentUser?.username;
      if (currName) {
        db.friendships[currName] = (db.friendships[currName] || []).filter((n: string) => n !== targetName);
        db.friendships[targetName] = (db.friendships[targetName] || []).filter((n: string) => n !== currName);
        saveDB(db);
      }
      return createResponse(200, { success: true });
    }

    console.warn(`[MockAdapter] Route not found: ${method} ${url}`);
    return createResponse(404, { detail: 'Mock route not found: ' + url });
  } catch (err: any) {
    return createResponse(500, { detail: 'Mock server error: ' + err.message });
  }
};
