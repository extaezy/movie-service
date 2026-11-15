# Практика полной недоступности PostgreSQL

Дата подготовки — 15.11.2026. В `backend/tests/test_database_outage.py` подготовлена инфраструктура и выполнены сценарии авторизации и карточек фильмов. Задание MOV-OUTAGE-001 завершено; каркас ниже сохранён как учебный материал.

## Изоляция и область

Фикстура owned_postgres создаёт собственный контейнер postgres:17 с уникальным именем и меткой владельца, временным паролем и отдельным фиксированным loopback-портом. Образ должен уже присутствовать локально: используется --pull=never. В новой БД movie_service_outage_test выполняется настоящий alembic upgrade head текущим интерпретатором pytest.

Контейнер работает с собственным анонимным volume. Он сохраняет данные между stop/start и удаляется вместе с контейнером после набора. Перед stop, start и удалением проверяется метка владельца; операции адресуются точному ID созданного контейнера. Существующий movie-service-test-db в этом сценарии не останавливается.

Фикстура outage_service подготавливает настоящего пользователя, JWT и фильм. Используются приложение через ASGITransport, настоящий get_db, репозитории и SQL. Фабрика сессий временно привязана к engine одноразовой БД с pool_pre_ping=True и короткими тестовыми таймаутами. TMDB подменён HTTPX MockTransport. Клиент, приложение, engine и фабрика сессий сохраняются между фазами одного теста.

Справка: [Docker create](https://docs.docker.com/reference/cli/docker/container/create/), [жизненный цикл volumes](https://docs.docker.com/engine/storage/volumes/), [удаление анонимных volumes контейнера](https://docs.docker.com/reference/cli/docker/container/rm/).

## Что уже проверено

T-AUTH-31, `test_auth_returns_503_during_database_outage_and_recovers`, закрывает AUTH-DATA-003 и AUTH-DATA-004. После реальной остановки контейнера регистрация, вход и /auth/me с действующим JWT дают 503 с точным безопасным JSON. Корневой маршрут и поиск через подменённый TMDB остаются доступны. После запуска того же контейнера вход успешен, /auth/me возвращает прежние UUID и данные, а повторная регистрация ранее не записанного пользователя даёт 201.

Отдельный тест дал **1 passed in 12.87s**. Полный backend-набор с `MOVIE_SERVICE_RUN_DATABASE_OUTAGE=1` и отдельной обычной БД автоматизации — **189 passed, 1 skipped, 1 xfailed in 21.07s**. Все 59 вариантов обычного PostgreSQL integration выполнены. Ruff прошёл, smoke пропущен, xfail — BR-MOV-001. Временный контейнер после прогона отсутствует; исходный movie-service-test-db принимает подключения.

Это управляемая остановка одного PostgreSQL 17 и восстановление его работы. Проверки остальных модулей, длительного сетевого разделения, перезапуска процесса backend и аварийного повреждения БД этим результатом не устанавливаются. Выполнение миграции на чистой БД входит в подготовку; отдельные проверки переходов версий и downgrade ещё не добавлены.

## Новая тема — async with и finally

Контекстный менеджер управляет входом в блок и выходом из него. В `async with outage_service.unavailable():` вход останавливает контейнер и подтверждает State.Running=false. Выход запускает его и ждёт готовности TCP PostgreSQL через pg_isready.

Внутри helper используется asynccontextmanager: код до yield подготавливает недоступность, тело теста выполняется во время yield, finally запускает восстановление при выходе, включая выход с исключением из тела. Ошибка проверки при этом остаётся ошибкой теста после выполнения завершающих действий.

| Фаза | Сервер | Ожидаемый ответ чтения фильма |
|---|---|---|
| До async with | Работает | 200 |
| Внутри блока | Остановлен | 503 |
| После блока | Запущен и готов | 200 с прежней карточкой |

Пример 1 — finally выполняется после успешного try:

```python
events = []
try:
    events.append("проверка")
finally:
    events.append("завершение")
assert events == ["проверка", "завершение"]
```

Пример 2 — завершающие действия выполняются и при исключении:

```python
events = []
with pytest.raises(RuntimeError):
    try:
        raise RuntimeError("Учебный сбой")
    finally:
        events.append("завершение")
assert events == ["завершение"]
```

Пример 3 — готовый асинхронный менеджер в нашем тесте:

```python
async with outage_service.unavailable():
    response = await outage_service.client.get(outage_service.movie_endpoint)
```

В этом примере response получен при остановленной БД. Для проверки восстановления после блока нужен новый HTTP-запрос: ранее созданный объект ответа сохраняет свой статус. В HTTP-тесте get_db преобразует ошибку подключения в ответ 503, поэтому здесь проверяем status_code и JSON, а не pytest.raises ошибки SQLAlchemy.

Справка: [asynccontextmanager и завершение контекста](https://docs.python.org/3.13/library/contextlib.html#contextlib.asynccontextmanager).

## Готовые объекты

| Объект | Назначение |
|---|---|
| outage_service.client | Настоящий HTTP-клиент приложения в пределах теста |
| outage_service.movie_endpoint | Чтение подготовленного фильма по внутреннему ID |
| outage_service.tmdb_endpoint | Чтение той же сохранённой карточки по tmdb_id |
| outage_service.unavailable() | Асинхронный контекстный менеджер остановки и восстановления собственного PostgreSQL |
| outage_service.upstream_requests | Обращения к подменённому TMDB; чтение сохранённого фильма оставляет список пустым |

Для менеджера используй `async with outage_service.unavailable():`. Вызов метода создаёт менеджер; действие выполняется при входе в его контекст.

## Задание — карточка фильма во время отказа и после восстановления

Добавь тест в `backend/tests/test_database_outage.py`. Импорты, фикстуры и маркер asyncio уже подготовлены:

```python
async def test_movie_reads_recover_after_database_outage(outage_service):
    client = outage_service.client
    local_endpoint = outage_service.movie_endpoint
    tmdb_endpoint = outage_service.tmdb_endpoint

    expected_success_status = 200
    expected_error_status = 503
    expected_error_json = {"detail": "База данных временно недоступна"}
    expected_upstream_requests = 0

    ...
```

1. До остановки прочитай local_endpoint, проверь 200 и сохрани исходный JSON.
2. Войди в `async with outage_service.unavailable():`.
3. Внутри блока отдельно прочитай local_endpoint и tmdb_endpoint. У каждого ответа проверь 503 и точный JSON ошибки.
4. После выхода из блока повтори оба запроса. Проверь 200 и равенство каждого JSON исходной карточке.
5. Проверь отсутствие запросов к TMDB по длине upstream_requests.

Остановка и запуск выполняются внутри готового менеджера; новых Docker-команд в тесте не требуется. Все запросы отправляй через тот же client.

## Результат задания

MOV-OUTAGE-001 завершена 15.11.2026 в `test_movie_reads_recover_after_database_outage`. До остановки прочитана исходная карточка. Во время подтверждённой остановки PostgreSQL оба маршрута чтения дают 503 с точным JSON ошибки. После выхода из контекста оба маршрута возвращают 200 и прежнюю карточку через тот же клиент и engine. Обращений к TMDB нет.

При ревью исправлена проверка начального статуса: local_endpoint содержит строку адреса, status_code читается у local_response. Лишний try/finally после контекста заменён обычными запросами и assertions: восстановление уже выполняет менеджер unavailable, а assertions в finally могли бы скрыть исходную ошибку HTTP-запроса. Для подсчёта обращений используется подготовленный expected_upstream_requests. Форматирование нового теста приведено к обычному оформлению.

Отдельный тест дал **1 passed, 1 deselected in 10.70s**. Полный backend-набор с включёнными обоими outage-сценариями — **190 passed, 1 skipped, 1 xfailed in 28.71s**; Ruff прошёл. Все 59 вариантов обычного PostgreSQL integration выполнены. Smoke пропущен, xfail — BR-MOV-001. Одноразовый контейнер удалён, исходный movie-service-test-db принимает подключения.

Проверены управляемые остановка/запуск PostgreSQL 17 и реальные SQL через приложение в ASGITransport. Перезапуск процесса backend, длительное сетевое разделение и нагрузка остаются отдельными сценариями.

## Запуск

Нужны работающий Docker Desktop и локальный образ postgres:17. MOVIE_SERVICE_TEST_DATABASE_URL этому отдельному модулю не требуется: он создаёт собственную БД. Без `MOVIE_SERVICE_RUN_DATABASE_OUTAGE=1` тесты модуля пропускаются, а контейнер не создаётся.

Из каталога backend:

```powershell
$env:MOVIE_SERVICE_RUN_DATABASE_OUTAGE = '1'
.\.venv\Scripts\python.exe -m pytest tests/test_database_outage.py -k movie_reads_recover -v
```

После завершения задания весь модуль:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_database_outage.py -v
.\.venv\Scripts\python.exe -m ruff check app tests
Remove-Item Env:MOVIE_SERVICE_RUN_DATABASE_OUTAGE
```

AUTH-DATA-003–004 и MOV-OUTAGE-001 пройдены. Результаты фиксируются в [чек-листе авторизации](../checklists/auth.md) и [чек-листе фильмов](../checklists/movies.md).
