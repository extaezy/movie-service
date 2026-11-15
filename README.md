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

Тесты API фильмов и адаптера TMDB запускаются без PostgreSQL, Docker и внешнего токена:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_tmdb.py tests/test_movies_api.py -q -rx
```

Ответы внешнего API подставляются через HTTPX MockTransport, операции репозитория в API-тестах подменены. Реальное сохранение фильмов в БД этим блоком не проверяется. Сценарии, результаты и известный дефект поиска описаны в [чек-листе фильмов](docs/testing/checklists/movies.md).

Проверки входа и текущего пользователя с подменённым репозиторием также доступны без PostgreSQL:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_auth_api.py -q
```

Их область и ограничения описаны в [отчёте auth API](docs/testing/checklists/auth-api.md). Новые темы для самостоятельных тестов разобраны в [практике JWT](docs/testing/exercises/jwt.md).

Проверка авторизации на базе из текущих настроек запускается явно:

```powershell
$env:MOVIE_SERVICE_RUN_DATABASE_SMOKE = '1'
.\.venv\Scripts\python.exe -m pytest -q tests/test_database_auth_smoke.py
Remove-Item Env:MOVIE_SERVICE_RUN_DATABASE_SMOKE
```

Она проверяет регистрацию, запись пользователя и профиля, конфликты email/username, вход, `/auth/me` и блокировку неактивного пользователя. Тест использует внешнюю транзакцию и savepoint для каждой сессии; в конце откатывает записи и проверяет их отсутствие через отдельное подключение. Схема и миграции не изменяются. Этот тест не проверяет сохранение после перезапуска процесса, поскольку намеренно не фиксирует данные в общей базе.

`tests/test_postgres_integration.py` требует отдельной локальной БД с применёнными миграциями и переменной `MOVIE_SERVICE_TEST_DATABASE_URL`. Эти тесты очищают предметные таблицы; для общей базы они не предназначены. Без переменной они пропускаются. Каталог frontend пока пуст, поэтому frontend-проверок нет.

В этом же модуле проверяется реальное сохранение каталога: фильмы, жанры и связи, повторное чтение, конкурентные импорты, отказы TMDB и откат транзакции. При настроенной тестовой БД этот блок запускается отдельно:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_postgres_integration.py -k 'movie_import or cached_movie_is_read' -q -rs
```

Для новой темы подготовлена [практика конкурентного импорта](docs/testing/exercises/catalog-concurrency.md): синхронизация запросов, примеры и два задания с каркасами.

В `tests/test_movies_api.py` также проверяются безопасный 503 при ошибках чтения БД, доступность поиска после сбоя и успешный следующий запрос к карточке. Используется настоящий get_db с подменёнными репозиторием и фабрикой сессий; Docker для этого блока не нужен. Сценарий и приём side_effect разобраны в [практике временной ошибки БД](docs/testing/exercises/database-recovery.md).

В PostgreSQL-модуле также проверяются настоящий разрыв соединения внутри запроса и замена потерянного свободного соединения отдельного тестового пула. Последующее чтение сохраняет карточку и использует новый PID. Соединение завершается по PID и уникальной метке теста; сервер продолжает работать. Сценарии разобраны в [практике восстановления соединений](docs/testing/exercises/postgres-connections.md).

Полная остановка PostgreSQL проверяется отдельным набором, которому нужны Docker Desktop и локальный образ postgres:17:

```powershell
$env:MOVIE_SERVICE_RUN_DATABASE_OUTAGE = '1'
.\.venv\Scripts\python.exe -m pytest tests/test_database_outage.py -v
Remove-Item Env:MOVIE_SERVICE_RUN_DATABASE_OUTAGE
```

Он создаёт собственный контейнер и БД, применяет миграцию, проверяет 503 для auth и карточек фильмов, а затем восстановление после запуска. Контейнер и его анонимный volume удаляются после набора; текущая БД разработки не используется. MOVIE_SERVICE_TEST_DATABASE_URL этому модулю не требуется. Без флага он пропускается. Сценарии и результаты — в [практике полной недоступности БД](docs/testing/exercises/database-outage.md).

