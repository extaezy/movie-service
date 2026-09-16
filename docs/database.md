# База данных и ER-схема

```mermaid
erDiagram
    USERS ||--|| PROFILES : has
    USERS ||--o{ RATINGS : gives
    USERS ||--o{ USER_REVIEWS : writes
    USERS ||--o{ USER_MOVIE_ENTRIES : saves
    USERS ||--o{ FRIENDSHIPS : participates
    MOVIES ||--o{ RATINGS : receives
    MOVIES ||--o{ USER_REVIEWS : has
    MOVIES ||--o{ USER_MOVIE_ENTRIES : appears_in
    MOVIES ||--o{ MOVIE_GENRES : classified_as
    GENRES ||--o{ MOVIE_GENRES : contains
    MOVIES ||--o{ CRITIC_REVIEWS : receives
    CRITIC_SOURCES ||--o{ CRITICS : publishes
    CRITICS ||--o{ CRITIC_REVIEWS : writes

    USERS { int id PK; string username UK; string email UK; string password_hash; string role; boolean is_active; datetime created_at }
    PROFILES { int user_id PK,FK; string display_name; string bio; string avatar_url; boolean is_private }
    FRIENDSHIPS { int id PK; int user_low_id FK; int user_high_id FK; int requested_by_id FK; string status; datetime created_at; datetime updated_at }
    MOVIES { int id PK; int tmdb_id UK; string title; string original_title; text overview; date release_date; string poster_path; int runtime; string original_language; datetime updated_at }
    GENRES { int id PK; int tmdb_id UK; string name }
    MOVIE_GENRES { int movie_id PK,FK; int genre_id PK,FK }
    USER_MOVIE_ENTRIES { int user_id PK,FK; int movie_id PK,FK; string list_type PK; datetime created_at }
    RATINGS { int user_id PK,FK; int movie_id PK,FK; int score; datetime created_at; datetime updated_at }
    USER_REVIEWS { int id PK; int user_id FK; int movie_id FK; text text; boolean contains_spoilers; datetime created_at; datetime updated_at }
    CRITIC_SOURCES { int id PK; string name; string website_url; string language; string source_type; boolean is_active }
    CRITICS { int id PK; string name; int source_id FK; string profile_url }
    CRITIC_REVIEWS { int id PK; int movie_id FK; int critic_id FK; int source_id FK; string external_id; string title; text excerpt; string external_url; string language; decimal original_score; decimal score_scale; decimal normalized_score; string verdict; datetime published_at; string moderation_status }
```

## Ограничения

- `movies.tmdb_id` уникален;
- одна оценка на пару пользователь/фильм;
- один элемент списка на пару пользователь/фильм/тип списка;
- одна дружба на пару пользователей, ID хранятся в нормализованном порядке;
- рецензия критика уникальна по `external_id` или `external_url`;
- оценка пользователя — целое число от 1 до 10;
- `friendship.status`: `pending`, `accepted`, `rejected`.

