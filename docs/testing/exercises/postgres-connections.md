# Практика восстановления соединений PostgreSQL

Дата подготовки — 15.11.2026. MOV-CONN-001 и MOV-CONN-002 реализованы и выполнены в `backend/tests/test_postgres_integration.py`. Каркас ниже сохранён как учебный материал.

## Термины и ожидаемое поведение

Engine управляет подключением к БД и пулом. Пул хранит открытые физические соединения для повторного использования. AsyncSession получает соединение при SQL-операции; завершение контекста сессии позволяет вернуть его в пул.

pool_pre_ping проверяет соединение при выдаче из пула. Если оно потеряно в простое, запрос может успешно выполниться через новое соединение. Потеря соединения внутри выполняемой транзакции прерывает операцию: в нашем API ожидается 503, а следующий запрос должен успешно прочитать прежнюю карточку.

| Сценарий | Ожидание | Проверка |
|---|---|---|
| Разрыв после получения соединения внутри запроса | 503, следующий запрос 200 с прежней карточкой и новым PID | MOV-CONN-001, пройдено |
| Разрыв свободного соединения, возвращённого в пул | Следующий запрос сразу 200 с прежней карточкой и новым PID | MOV-CONN-002, пройдено |
| Полная недоступность сервера PostgreSQL | Зависимые запросы 503, возобновление после восстановления | Отдельный будущий сценарий |

Справка: [SQLAlchemy: обработка потери соединений](https://docs.sqlalchemy.org/en/20/core/pooling.html#disconnect-handling-pessimistic).

## Подготовленная фикстура

isolated_movie_database использует отдельный реальный engine с pool_pre_ping=True, pool_size=1 и max_overflow=0. Параметры соединения берутся из настроенного локального тестового подключения. Фабрика сессий get_db временно привязана к этому engine; настоящее приложение и репозиторий выполняют SQL.

Один слот пула делает проверку PID определённой: последовательные операции используют одно соединение, пока оно исправно. Фикстура готовит фильм через существующие records. В конце возвращается исходная фабрика сессий и освобождается тестовый engine.

| Поле | Назначение |
|---|---|
| isolated_movie_database.endpoint | Маршрут готового локального фильма |
| isolated_movie_database.sessions() | Новая реальная AsyncSession отдельного пула |
| isolated_movie_database.terminate_connection(pid) | Асинхронное завершение только помеченного тестового соединения; возвращает None |
| isolated_movie_database.terminated_pids | PID успешно завершённых соединений |
| catalog_tmdb.upstream_requests | История обращений к TMDB; локальное чтение должно оставить её пустой |

terminate_connection выполняет управляющий SQL через отдельный основной тестовый engine. Цель ограничена точным PID, уникальным application_name этого теста и текущей БД; управляющий PID исключён. pg_terminate_backend с таймаутом 5000 мс ожидает завершения выбранного соединения, результат True проверяется внутри helper. Никакие команды остановки контейнера не выполняются.

Справка: [pg_terminate_backend в PostgreSQL 17](https://www.postgresql.org/docs/17/functions-admin.html#FUNCTIONS-ADMIN-SIGNAL).

## Три примера

Пример 1 — получить единственное значение SQL-запроса:

```python
async with isolated_movie_database.sessions() as session:
    value = await session.scalar(text("SELECT 42"))
assert value == 42
```

text(...) превращает SQL-строку в объект запроса SQLAlchemy. scalar возвращает первое значение первой строки, поэтому .all() здесь не требуется. Для выборки нескольких объектов Movie ранее использовались scalars и .all().

Пример 2 — получить PID физического соединения:

```python
async with isolated_movie_database.sessions() as session:
    pid = await session.scalar(text("SELECT pg_backend_pid()"))
```

pg_backend_pid() возвращает целочисленный ID серверного процесса PostgreSQL, обслуживающего текущее соединение. Это отдельное понятие от внутреннего id фильма и tmdb_id. После выхода из async with соединение доступно пулу. [Справка PostgreSQL](https://www.postgresql.org/docs/17/functions-info.html).

Пример 3 — завершить подготовленное соединение после выхода из контекста сессии:

```python
await isolated_movie_database.terminate_connection(pid)
```

Helper выполняет SQL и проверку результата самостоятельно. Вызывать его нужно через await; он не возвращает HTTP-ответ или флаг True.

## Что уже проверено

MOV-CONN-001 сначала читает сохранённую карточку. Затем обёртка настоящего репозитория получает соединение, узнаёт его PID, завершает его через helper и пытается выполнить обычное SQL-чтение. Возникает настоящая ошибка драйвера; get_db формирует 503. Обёртка снимается, следующий запрос в прежнем приложении и через тот же engine возвращает 200 с прежней карточкой. Новый PID отличается, запись фильма сохраняется, TMDB не вызывается.

Отдельный тест дал **1 passed, 57 deselected in 1.12s**. Полный backend-набор с PostgreSQL — **187 passed, 1 skipped, 1 xfailed in 11.50s**; Ruff прошёл. Все 58 вариантов PostgreSQL integration выполнены. Smoke пропущен, xfail — BR-MOV-001.

Это реальная потеря клиентского соединения при работающем сервере. Проверка использует отдельный тестовый pool_pre_ping=True; остановка сервера, отказ новых соединений и восстановление после перезапуска PostgreSQL не входят в результат.

## Задание — потерянное свободное соединение

Добавь тест в `backend/tests/test_postgres_integration.py`. Нужные импорты и маркер asyncio уже есть:

```python
async def test_local_movie_read_replaces_dead_idle_connection(
    client, isolated_movie_database, catalog_tmdb
):
    endpoint = isolated_movie_database.endpoint
    pid_query = text("SELECT pg_backend_pid()")
    expected_status = 200
    expected_terminated_count = 1

    ...
```

1. Прочитай endpoint через client, проверь 200 и сохрани JSON исходной карточки.
2. Через isolated_movie_database.sessions() получи before_pid с помощью session.scalar(pid_query). Выйди из async with, чтобы соединение вернулось в пул.
3. Вызови terminate_connection(before_pid) через await.
4. Следующей операцией этого пула должен стать HTTP-запрос к прежнему endpoint. Проверь 200 и точное равенство JSON исходной карточке.
5. После HTTP-запроса открой новую сессию и получи after_pid. Проверь отличие от before_pid.
6. Проверь expected_terminated_count и содержимое terminated_pids, а также пустую историю TMDB.

Между шагами 3 и 4 не выполняй SQL-проверок через sessions(): такая проверка сама может заменить соединение до HTTP-запроса. Engine, клиент и приложение сохраняются; dispose в тесте не нужен. Завершение тестового engine уже выполняет фикстура после проверки.

## Результат задания

MOV-CONN-002 завершена 15.11.2026. Исходная карточка прочитана до разрыва. PID получен через отдельную сессию, контекст завершён и соединение возвращено в пул. После одного вызова terminate_connection первым обращением этого пула стал HTTP-запрос: получены 200 и прежний JSON. Последующий SQL подтвердил новый PID. История завершений содержит только before_pid, TMDB не вызывался.

В пользовательском тесте дополнительно добавлена проверка статуса повторного HTTP-запроса. Отдельный тест дал **1 passed, 58 deselected in 0.55s**, оба сценария разрыва — **2 passed, 57 deselected in 0.65s**. Полный backend-набор — **188 passed, 1 skipped, 1 xfailed in 5.67s**; Ruff прошёл. Все 59 вариантов PostgreSQL integration выполнены. Пропущен отдельно включаемый smoke, xfail — BR-MOV-001.

Подтверждена замена потерянного свободного соединения в отдельном тестовом пуле с pool_pre_ping=True. Сервер PostgreSQL оставался доступным; полная недоступность сервера и восстановление после его перезапуска этим тестом не проверяются.

## Запуск

Нужны запущенная отдельная локальная БД с миграциями и MOVIE_SERVICE_TEST_DATABASE_URL. Модуль очищает предметные таблицы. Тестовое подключение должно иметь право завершать собственные соединения; локальный Docker postgres это позволяет.

Из каталога backend:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_postgres_integration.py -k dead_idle_connection -v
```

Оба сценария после завершения задания:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_postgres_integration.py -k 'connection_termination or dead_idle_connection' -v
.\.venv\Scripts\python.exe -m ruff check app tests
```

MOV-CONN-001 и MOV-CONN-002 пройдены. Результаты фиксируются в [чек-листе фильмов](../checklists/movies.md).
