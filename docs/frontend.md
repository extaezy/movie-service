# План frontend

## Маршруты

| Route | Страница | Доступ |
|---|---|---|
| `/` | Каталог | публичный |
| `/movies/:id` | Фильм | публичный |
| `/login` | Вход | публичный |
| `/register` | Регистрация | публичный |
| `/profile/:username` | Профиль | с privacy-ограничениями |
| `/profile/me/edit` | Редактирование профиля | авторизованный |
| `/lists/:type` | Список фильмов | авторизованный |
| `/friends` | Друзья и заявки | авторизованный |
| `/admin` | Администрирование | admin |

## Компоненты

`AppLayout`, `Header`, `SearchBar`, `MovieCard`, `MovieGrid`, `MovieFilters`, `Pagination`, `MovieHero`, `RatingSummary`, `CriticReviewList`, `UserReviewList`, `ProfileHeader`, `ProfileTabs`, `PrivacyNotice`, `AuthForm`, `ProfileForm`, `RatingForm`, `ReviewForm`, `FriendRequestList`, `FriendButton`, `AdminSyncPanel`.

## Состояния

Каждая страница должна иметь `loading`, `success`, `empty`, `error`. Для мутаций кнопка блокируется на время запроса и показывает ошибку.

## Клиентская модель

- `AuthContext`: текущий пользователь, вход, выход, загрузка;
- `apiClient`: Axios с базовым URL и обработкой `401`;
- feature-модули `auth`, `movies`, `users`, `lists`, `reviews`, `friends`, `admin`;
- TypeScript-типы должны соответствовать `docs/api.md`.

## Wireframes

### Каталог

```text
[Logo] [Поиск........................] [Войти]
[Жанр v] [Год v] [Сортировка v]
[ MovieCard ][ MovieCard ][ MovieCard ]
[ MovieCard ][ MovieCard ][ MovieCard ]
                 [pagination]
```

### Фильм

```text
[Постер] [Название, дата, жанры]
         [описание]
         [Оценить] [Хочу посмотреть] [Просмотрено] [Избранное]
[Рейтинг зрителей] [Рейтинг критиков]
[Рецензии критиков] [Рецензии пользователей]
```

### Профиль

```text
[Аватар] [Имя] [описание] [Добавить в друзья]
[Рецензии] [Хочу посмотреть] [Просмотрено] [Избранное]
```

