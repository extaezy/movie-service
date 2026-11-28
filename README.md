# Movie Service

Импорт рецензий NYT: укажите `NYT_API_KEY` в `backend/.env`, установите зависимости (`.\.venv\Scripts\python.exe -m pip install -r requirements.txt`) и примените миграции (`.\.venv\Scripts\python.exe -m alembic upgrade head`) из backend. После запуска backend ежедневно в 04:00 UTC (07:00 Москвы) загружает новые публикации NYT и сопоставляет рецензии с нашим каталогом; при старте догоняет пропущенные дни. По умолчанию первый запуск читает два последних завершённых дня, прогресс хранится в БД. Настройки: `NYT_SYNC_ENABLED=true`, `NYT_SYNC_HOUR_UTC=4`. Для архивных рецензий администратор по-прежнему вызывает `POST /admin/critic-reviews/import` с `{"movie_ids": [7]}` (до 5 фильмов). Дубли пропускаются. Контракт, перекрытие дат и ограничения описаны в `docs/api.md`.

Веб-сервис для поиска фильмов, пользовательских оценок и рецензий. Пользователи могут вести списки фильмов, общаться через профили и просматривать рецензии профессиональных критиков.

## Документация

- [Требования](docs/requirements.md)
- [Архитектура](docs/architecture.md)
- [База данных и ER-схема](docs/database.md)
- [API](docs/api.md)
- [План клиентской части](docs/frontend.md)

## Текущее хранение пользователей

Регистрация, вход и `/auth/me` используют PostgreSQL через `backend/app/repositories/user_repository.py`. Пользователь и профиль создаются одной транзакцией. Словаря пользователей в памяти и резервного хранения без БД нет. Подключение и ключ JWT задаются в `backend/.env` по образцу `backend/.env.example`.

Авторизация: access JWT живёт до 30 минут, refresh и сессия — фиксированные 7 дней от входа. Refresh передаётся только в HttpOnly cookie и заменяется при каждом `/auth/refresh`; `/auth/logout` немедленно отзывает сессию, другие устройства остаются авторизованными. Frontend хранит access в памяти и восстанавливает вход через refresh после перезагрузки. Примените миграцию `20261128_0005`; старые JWT без sid потребуют повторного входа. Для локального HTTP используйте `AUTH_COOKIE_SECURE=false`, для production HTTPS — `true`; `AUTH_ALLOWED_ORIGINS` задаёт допустимые адреса frontend. Cookie-операции login/refresh/logout требуют `X-Auth-Request: 1`, frontend добавляет его автоматически. Подробности — в `docs/api.md`.

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

Ответы внешнего API подставляются через HTTPX MockTransport, операции репозитория в API-тестах подменены. Реальное сохранение фильмов в БД этим блоком не проверяется. Сценарии, результаты и история исправленного дефекта поиска описаны в [чек-листе фильмов](docs/testing/checklists/movies.md).

Проверки входа и текущего пользователя с подменённым репозиторием также доступны без PostgreSQL:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_auth_api.py -q
```

Их область и ограничения описаны в [отчёте auth API](docs/testing/checklists/auth-api.md).

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

В `tests/test_movies_api.py` также проверяются безопасный 503 при ошибках чтения БД, доступность поиска после сбоя и успешный следующий запрос к карточке. Используется настоящий get_db с подменёнными репозиторием и фабрикой сессий; Docker для этого блока не нужен.

В PostgreSQL-модуле также проверяются настоящий разрыв соединения внутри запроса и замена потерянного свободного соединения отдельного тестового пула. Последующее чтение сохраняет карточку и использует новый PID. Соединение завершается по PID и уникальной метке теста; сервер продолжает работать.

Полная остановка PostgreSQL проверяется отдельным набором, которому нужны Docker Desktop и локальный образ postgres:17:

```powershell
$env:MOVIE_SERVICE_RUN_DATABASE_OUTAGE = '1'
.\.venv\Scripts\python.exe -m pytest tests/test_database_outage.py -v
Remove-Item Env:MOVIE_SERVICE_RUN_DATABASE_OUTAGE
```

Он создаёт собственный контейнер и БД, применяет миграцию, проверяет 503 для auth и карточек фильмов, а затем восстановление после запуска. Контейнер и его анонимный volume удаляются после набора; текущая БД разработки не используется. MOVIE_SERVICE_TEST_DATABASE_URL этому модулю не требуется. Без флага он пропускается. Сценарии и результаты описаны в [чек-листе авторизации](docs/testing/checklists/auth.md#полная-недоступность-postgresql-15112026) и [чек-листе фильмов](docs/testing/checklists/movies.md#полная-недоступность-postgresql--дополнение-15112026).

