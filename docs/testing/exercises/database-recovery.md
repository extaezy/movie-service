# Практика обработки временной ошибки БД

Дата подготовки — 15.11.2026. Знакомые проверки ошибок чтения и учебная MOV-DATA-003 завершены в `backend/tests/test_movies_api.py`. Каркас ниже сохранён как учебный материал.

## Что уже подготовлено

Фикстура `movie_database_api` использует то же тестовое приложение и подменённый репозиторий, что movie_api, но включает настоящий get_db. Фабрика сессий подменена: выполняется реальный код перехвата ошибки, вызова rollback и формирования HTTP 503, а настоящих SQL-запросов нет.

Восемь вариантов MOV-DATA-001 проверяют OperationalError, таймаут пула SQLAlchemy, ConnectionRefusedError и встроенный TimeoutError для чтения по внутреннему ID и tmdb_id. MOV-DATA-002 подтверждает, что после сбоя локального чтения поиск в том же приложении работает через TMDB и не обращается к фабрике сессий.

Новые тесты дали **9 passed, 31 deselected in 0.27s**. Блок фильмов/TMDB — **85 passed, 1 xfailed in 0.73s**. Полный backend-набор с PostgreSQL — **185 passed, 1 skipped, 1 xfailed in 5.46s**, Ruff прошёл. Smoke пропущен, xfail — BR-MOV-001.

Эти тесты подтверждают обработку внедрённых ошибок. Они не устанавливают восстановление настоящего соединения PostgreSQL или его пула. Реальный rollback записей проверяется отдельно в MOV-DB-006.

## Как ошибка превращается в ответ

Маршрут получает сессию из get_db и вызывает репозиторий. Если репозиторий выбрасывает предусмотренное исключение, FastAPI передаёт его обратно в зависимость с yield. В get_db выполняются rollback и raise HTTPException с кодом 503. Клиент получает HTTP-ответ.

Поэтому в HTTP-тесте нужно проверять response.status_code и response.json(). Само исключение SQLAlchemy не должно выходить из await movies_client.get(...). Использование pytest.raises ниже показывает поведение отдельного мока, а не ожидаемое поведение HTTP-клиента нашего приложения.

## Новая тема — последовательность side_effect

AsyncMock заменяет асинхронную функцию. return_value задаёт обычный результат, а side_effect позволяет выбросить исключение или задать последовательность исходов. Для AsyncMock результат получается при await.

Пример 1 — обычный результат:

```python
load = AsyncMock(return_value={"title": "Учебный фильм"})
card = await load()
assert card == {"title": "Учебный фильм"}
```

Пример 2 — постоянная ошибка:

```python
load = AsyncMock(side_effect=TimeoutError("Временный сбой"))
with pytest.raises(TimeoutError):
    await load()
```

Пример 3 — первый вызов ошибочный, следующий успешный:

```python
load = AsyncMock(side_effect=[TimeoutError("Временный сбой"), {"title": "Учебный фильм"}])
with pytest.raises(TimeoutError):
    await load()
card = await load()
assert card == {"title": "Учебный фильм"}
assert load.await_count == 2
```

Исключение внутри списка выбрасывается, следующий элемент возвращается как результат следующего await. После исчерпания последовательности AsyncMock выбрасывает StopAsyncIteration: список должен покрывать все ожидаемые обращения. await_count показывает количество await этого мока, включая завершившийся исключением.

Справка: [AsyncMock в Python 3.13](https://docs.python.org/3.13/library/unittest.mock.html#unittest.mock.AsyncMock), [зависимости FastAPI с yield](https://fastapi.tiangolo.com/tutorial/dependencies/dependencies-with-yield/).

## Готовая фикстура

| Поле movie_database_api | Назначение |
|---|---|
| get_by_id | AsyncMock чтения карточки по внутреннему ID; именно ему задаём side_effect |
| movie | Подготовленная MovieResponse для успешного исхода |
| session.rollback | AsyncMock отката, который вызывает настоящий get_db |
| session_factory | Подменённая фабрика сессий, вызываемая get_db |
| upstream_requests | Обращения к подменённому TMDB; локальное чтение оставляет список пустым |
| save | AsyncMock сохранения, который локальное чтение вызывать не должно |

## Задание — ошибка, затем успешное чтение

Проверка MOV-DATA-003. Добавь тест в `backend/tests/test_movies_api.py`. Все нужные импорты и маркер asyncio уже есть. Каркас:

```python
async def test_local_movie_read_recovers_after_database_error(
    movies_client, movie_database_api
):
    endpoint = f"/movies/{movie_database_api.movie.id}"
    read_movie = movie_database_api.get_by_id
    temporary_error = SQLAlchemyTimeoutError("Simulated temporary database failure")
    expected_error_status = 503
    expected_success_status = 200
    expected_error_json = {"detail": "База данных временно недоступна"}
    expected_movie_json = movie_database_api.movie.model_dump(mode="json")
    expected_read_count = 2

    ...
```

1. Задай read_movie.side_effect списком из temporary_error и movie_database_api.movie. Второй элемент должен быть подготовленной MovieResponse, которую обычно возвращает репозиторий.
2. Отправь первый запрос к endpoint. Проверь status_code и JSON ошибки.
3. Через тот же movies_client отправь второй запрос к тому же endpoint. Проверь 200 и точный JSON карточки.
4. Проверь read_movie.await_count: два await, по одному на каждый запрос.

Приложение и клиент остаются прежними; не пересоздавай их и не меняй side_effect между запросами. Преобразование model_dump(mode="json") в каркасе подготавливает ожидаемый словарь с датой в формате JSON. Не обращайся к status_code у словаря, возвращённого response.json().

`read_movie = movie_database_api.get_by_id` сохраняет ссылку на уже подключённый мок. Присваивание `read_movie.side_effect = ...` настраивает этот объект. Присваивание нового `AsyncMock` локальной переменной read_movie создаст другой объект, который маршрут сам по себе использовать не начнёт.

## Результат задания

MOV-DATA-003 завершена 15.11.2026. Существующему get_by_id задана последовательность `[temporary_error, movie]`; два последовательных запроса через прежний клиент и приложение дают 503 с точным JSON ошибки, затем 200 с точным JSON карточки. Проверены два await репозитория. Учебная часть отдельно дала **1 passed, 40 deselected in 0.25s**.

Знакомые assertions дополнены автоматически: rollback вызван один раз после первого запроса и остаётся единственным после второго; фабрика сессий и вход/выход из контекста вызваны дважды. Другой способ чтения по tmdb_id, сохранение и TMDB не вызываются. Форматирование нового теста приведено к обычному оформлению.

Весь блок ошибок чтения и следующего успешного запроса дал **10 passed, 31 deselected in 0.30s**. Полный backend-набор с локальной PostgreSQL — **186 passed, 1 skipped, 1 xfailed in 6.70s**; Ruff прошёл. Все 57 вариантов PostgreSQL integration выполнены. Пропущен отдельно включаемый smoke, xfail — BR-MOV-001.

Сбой внедрён в мок репозитория, фабрика сессий тоже подменена. Проверена обработка последовательных HTTP-запросов после управляемой ошибки; восстановление настоящего соединения или пула PostgreSQL этим результатом не устанавливается.

## Запуск

Из каталога backend, без Docker и реальных настроек подключения:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_movies_api.py -k local_movie_read_recovers_after_database_error -v
```

Весь блок ошибок чтения и восстановления:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_movies_api.py -k 'database_read or local_movie_read_recovers' -q
.\.venv\Scripts\python.exe -m ruff check app tests
```

MOV-DATA-003 пройдена на внедрённой ошибке. Результаты фиксируются в [чек-листе фильмов](../checklists/movies.md).
