# API-контракт v1

Базовый префикс: `/api`. Формат обмена: JSON. Защищённые методы требуют авторизацию.

## Авторизация

```http
POST /auth/register
POST /auth/login
POST /auth/logout
GET  /auth/me
```

## Фильмы

```http
GET  /movies?page=1&page_size=20&genre_id=&year=&sort=
GET  /movies/search?q=...
GET  /movies/{movie_id}
POST /admin/movies/sync
```

## Пользователи

```http
GET   /users/{username}
PATCH /users/me/profile
GET   /users/{username}/movies?list_type=watched
GET   /users/{username}/reviews
```

## Списки, оценки и рецензии

```http
POST   /movies/{movie_id}/lists          # {"list_type":"watchlist"}
DELETE /movies/{movie_id}/lists/{list_type}
PUT    /movies/{movie_id}/rating         # {"score":8}
DELETE /movies/{movie_id}/rating
POST   /movies/{movie_id}/reviews        # {"text":"...","contains_spoilers":false}
PATCH  /reviews/{review_id}
DELETE /reviews/{review_id}
```

## Друзья

```http
POST   /friends/requests/{user_id}
GET    /friends/requests
POST   /friends/requests/{request_id}/accept
POST   /friends/requests/{request_id}/reject
DELETE /friends/{user_id}
GET    /friends
```

## Рецензии критиков

```http
GET    /movies/{movie_id}/critic-reviews?language=ru
POST   /admin/critic-reviews
POST   /admin/critic-reviews/import
DELETE /admin/critic-reviews/{review_id}
```

## Ошибки

```json
{"detail":{"code":"PRIVATE_PROFILE","message":"Profile data is unavailable"}}
```

Коды: `400`, `401`, `403`, `404`, `409`, `422`, `502`.

