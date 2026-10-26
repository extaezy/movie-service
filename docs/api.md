# API-контракт v1

Базовый префикс: `/api`. Формат обмена: JSON. Защищённые методы требуют авторизацию.

`/api` — часть пути запроса, а не сетевой адрес. Адрес backend задаётся настройкой клиентской части; адрес базы данных и ключи внешних служб в браузер не передаются.

## Авторизация

```http
POST /auth/register
POST /auth/login
POST /auth/logout
GET  /auth/me
```

### Текущий этап: временное хранилище и access JWT

В текущем приложении auth-маршруты доступны без префикса `/api`.

- `POST /auth/register` сохраняет прежний контракт: `username`, `email`, `password`, `password_confirm`; ответ `201` содержит только `username` и `email`. Дубли возвращают `409`, ошибки валидации — `422`.
- `POST /auth/login` принимает JSON `{"identifier":"username или email","password":"пароль"}`. Ответ `200`: `{"access_token":"<jwt>","token_type":"bearer"}`. Неверные учётные данные возвращают `401` с одинаковым сообщением; ошибки структуры запроса — `422`.
- Username сравнивается с учётом регистра. Email при входе нормализуется через `EmailStr`, как при регистрации; дополнительного приведения всего адреса к нижнему регистру нет. Пароль не нормализуется.
- `GET /auth/me` требует `Authorization: Bearer <jwt>` и возвращает `id`, `username`, `email`. Пароль и хеш не возвращаются.
- JWT подписывается HS256 и действует 30 минут. Обязательные claims: `sub` (внутренний UUID пользователя), `iat`, `exp`. Проверяются подпись, алгоритм, время и существование пользователя. Недействительный или отсутствующий токен возвращает `401` с `WWW-Authenticate: Bearer`.
- `JWT_SECRET_KEY` задаётся в окружении или `backend/.env`; требуется случайный секрет длиной не менее 32 символов. Значения по умолчанию нет.
- Временное хранилище работает в одном процессе и очищается при перезапуске. UUID создаётся один раз при регистрации; прежние токены после потери хранилища не авторизуют заново созданные аккаунты.
- Refresh token, отзыв JWT и `POST /auth/logout` пока не реализованы. Требование FR.AUTH.05 остаётся отложенным; выданный токен действует до истечения срока, пока существует пользователь и сохраняется ключ подписи.

## Фильмы

```http
GET  /movies?page=1&page_size=20&genre_id=&year=&sort=
GET  /movies/search?q=...
GET  /movies/{movie_id}
POST /admin/movies/sync
```

## Пользователи и профили

```http
GET   /users/{username}
PATCH /users/me/profile
GET   /users/{username}/movies?list_type=watched
GET   /users/{username}/reviews

Закрытый профиль постороннего не должен раскрывать наличие скрытых списков и рецензий. Владелец видит все данные, принятый друг — закрытые списки и рецензии.
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

Сервер проверяет права на каждую мутацию. Для закрытого профиля ответы не должны позволять определить существование скрытых данных. Ошибки внешних служб преобразуются в понятный ответ `502`; ключи внешних служб остаются только на сервере.
