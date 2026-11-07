# Movie Service

Веб-сервис для поиска фильмов, пользовательских оценок и рецензий. Пользователи могут вести списки фильмов, общаться через профили и просматривать рецензии профессиональных критиков.

## Документация

- [Требования](docs/requirements.md)
- [Архитектура](docs/architecture.md)
- [База данных и ER-схема](docs/database.md)
- [API](docs/api.md)
- [План клиентской части](docs/frontend.md)

## Текущее хранение пользователей

Регистрация, вход и `/auth/me` используют PostgreSQL через `backend/app/repositories/user_repository.py`. Пользователь и профиль создаются одной транзакцией. Словаря пользователей в памяти и резервного хранения без БД нет. Подключение и ключ JWT задаются в `backend/.env` по образцу `backend/.env.example`.

## Проверка backend

Команды PowerShell из каталога `backend` с установленными зависимостями:

```powershell
.\.venv\Scripts\python.exe -m app.db.check
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m ruff check app tests
```

Проверка авторизации на базе из текущих настроек запускается явно:

```powershell
$env:MOVIE_SERVICE_RUN_DATABASE_SMOKE = '1'
.\.venv\Scripts\python.exe -m pytest -q tests/test_database_auth_smoke.py
Remove-Item Env:MOVIE_SERVICE_RUN_DATABASE_SMOKE
```

Она проверяет регистрацию, запись пользователя и профиля, конфликты email/username, вход, `/auth/me` и блокировку неактивного пользователя. Тест использует внешнюю транзакцию и savepoint для каждой сессии; в конце откатывает записи и проверяет их отсутствие через отдельное подключение. Схема и миграции не изменяются. Этот тест не проверяет сохранение после перезапуска процесса, поскольку намеренно не фиксирует данные в общей базе.

`tests/test_postgres_integration.py` требует отдельной локальной БД с применёнными миграциями и переменной `MOVIE_SERVICE_TEST_DATABASE_URL`. Эти тесты очищают предметные таблицы; для общей базы они не предназначены. Без переменной они пропускаются. Каталог frontend пока пуст, поэтому frontend-проверок нет.

