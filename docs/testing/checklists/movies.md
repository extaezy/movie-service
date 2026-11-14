# Проверки API фильмов и адаптера TMDB

Дата прогона — 14.11.2026. Проверена рабочая копия поверх `6417a7c`, ветка `feature/auth-qa-tests`, с новыми незакоммиченными тестами.

Основание — текущий этап поиска и открытия фильмов в [API](../../api.md#поиск-и-открытие-фильма), FR.MOV.04–06 в [требованиях](../../requirements.md) и раздел подключения TMDB в [архитектуре](../../architecture.md#подключение-tmdb).

## Область и окружение

Windows, Python 3.13.17, интерпретатор `backend/.venv/Scripts/python.exe`. Внешний HTTP заменён `httpx.MockTransport`: выполняются настоящий код адаптера, валидация Pydantic, формирование запросов и обработка ответов, но обращения в интернет отсутствуют. Используется вымышленный токен, реальные настройки TMDB не требуются.

API-тесты подключают существующий movies-router к тестовому FastAPI и вызывают его через `ASGITransport`, без JWT. Зависимость БД и три функции репозитория подменены. Проверяются HTTP-контракт и вызовы границ хранения, а не реальные SQL-запросы. Основное приложение, его lifespan и подключение PostgreSQL в этот блок не входят.

Общие входные данные и настройки находятся в `backend/tests/conftest.py`, тесты адаптера — в `test_tmdb.py`, тесты маршрутов — в `test_movies_api.py`.

## Проверки

| ID | Условия | Автоматизация | Результат |
|---|---|---|---|
| MOV-SEARCH-001 | Поиск публичен, запрос к TMDB содержит обрезанную строку, страницу, язык и исключение adult; ответ содержит внешние tmdb_id; БД не вызывается | `test_search_sends_expected_request_and_normalizes_response`, `test_search_is_public_and_uses_external_ids_without_database` | Пройдено |
| MOV-SEARCH-002 | Пустая выдача возвращается как успешный ответ с пустым results | `test_search_accepts_empty_results`, `test_search_returns_empty_results` | Пройдено |
| MOV-SEARCH-003 | Пустой, отсутствующий, пробельный и слишком длинный q, неверная страница; запрос к TMDB не отправляется. Границы адаптера: длина 1/200, страница 1/500 | `test_search_rejects_invalid_parameters_before_http`, `test_search_accepts_parameter_boundaries`, `test_search_rejects_invalid_parameters_without_external_calls` | Пройдено |
| MOV-SEARCH-004 | Ограничение длины q применяется после удаления пробелов по краям | `test_search_validates_length_after_trimming` | Не пройдено: BR-MOV-001, strict xfail |
| MOV-DETAIL-001 | Карточка нормализует неизвестные дату и длительность; жанры сохраняют внешние ID; 404 и adult дают 404 | `test_get_movie_sends_id_and_normalizes_missing_values`, `test_get_movie_handles_adult_content`, `test_get_movie_preserves_not_found_status` | Пройдено |
| MOV-DETAIL-002 | Публичное чтение по внутреннему ID вызывает только локальный репозиторий; неизвестный ID даёт 404 без импорта | `test_local_movie_is_public_and_does_not_use_tmdb`, `test_unknown_local_movie_is_not_found_without_import` | Пройдено на подменённом репозитории |
| MOV-DETAIL-003 | Сохранённая карточка по tmdb_id доступна без настройки TMDB; отсутствующая получается из TMDB и передаётся в сохранение | `test_cached_movie_is_available_without_tmdb_configuration`, `test_missing_movie_is_fetched_and_passed_to_repository` | Пройдено на подменённом репозитории |
| MOV-DETAIL-004 | Неверные ID дают 422 без вызовов репозитория/TMDB; ошибки получения и adult не приводят к сохранению | `test_invalid_movie_ids_do_not_reach_repositories`, `test_failed_movie_import_does_not_save_data`, `test_adult_movie_is_not_saved` | Пройдено |
| MOV-DETAIL-005 | Пустая дата и нулевая длительность из TMDB передаются на сохранение как None с правильными сессией и tmdb_id, без повторного запроса | `test_import_passes_normalized_fields_to_repository` | Пройдено на подменённом репозитории |
| TMDB-ERROR-001 | HTTP-ошибки, включая 429, перенаправления, сетевые ошибки и таймауты преобразуются в 502; нет перехода по Location и автоматического повтора | `test_upstream_http_errors_are_safe_bad_gateway_responses`, `test_network_failures_become_safe_bad_gateway_responses`, `test_tmdb_timeout_reaches_http_client_as_safe_502` | Пройдено |
| TMDB-ERROR-002 | Невалидный JSON, структура выдачи и карточки, несовпадающий ID дают 502 | `test_invalid_json_becomes_bad_gateway`, `test_invalid_movie_details_become_bad_gateway`, `test_invalid_search_response_becomes_bad_gateway` | Пройдено |
| TMDB-RECOVERY-001 | После таймаута первый запрос даёт 502 без сохранения, следующий запрос в том же приложении даёт 200 и одно сохранение; всего два обращения к TMDB | `test_movie_import_recovers_after_timeout` | Пройдено на подменённом репозитории |
| TMDB-SEC-001 | Токен из тела ошибки внешнего сервиса не отражается в HTTP-ответе и логах; backend возвращает 502, сохранение не вызывается, предупреждение логгера действительно записано | `test_tmdb_error_does_not_expose_token` | Пройдено для ошибки поиска |
| TMDB-CONFIG-001 | Отсутствующий токен даёт 503 без HTTP-запроса; небезопасный base URL отвергается; вымышленный токен не отражается в проверенных ошибках, ответе поиска и логах | `test_missing_token_is_configuration_error_without_http`, `test_unsafe_base_url_is_rejected`, `test_unconfigured_tmdb_returns_503_without_saving`, проверки ответов и caplog | Пройдено в указанных сценариях |

## Результаты запуска

Команда блока из каталога `backend`:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_tmdb.py tests/test_movies_api.py -q -rx
```

В новом блоке 74 варианта: 46 для адаптера и 28 для API. В полном прогоне они дали **73 passed, 1 xfailed**. Перед отметкой xfail тест MOV-SEARCH-004 запускался отдельно и дал **1 failed**: фактический статус 422 вместо 200. Дефект подтверждён и описан в [BR-MOV-001](../bug-reports/BR-MOV-001.md).

Полный запуск backend без включения проверок PostgreSQL дал **76 passed, 46 skipped, 1 xfailed in 2.65s**. В процессе запуска `MOVIE_SERVICE_TEST_DATABASE_URL` не задана, `MOVIE_SERVICE_RUN_DATABASE_SMOKE=0`. Из 46 пропусков 45 относятся к PostgreSQL integration и один к smoke. Они не считаются пройденными. Docker недоступен; старые результаты прогонов с БД не заменены результатом этого запуска.

Ruff (`ruff check app tests --no-cache`) — **All checks passed!** Форматирование применено только к трём новым Python-файлам.

После запуска Docker 14.11.2026 PostgreSQL завершила автоматическое восстановление и стала принимать подключения. Повторный полный прогон с `MOVIE_SERVICE_TEST_DATABASE_URL` для `movie_service_automation_test` дал **121 passed, 1 skipped, 1 xfailed in 4.19s**. Все 45 вариантов PostgreSQL integration выполнены успешно. Остался только отдельно включаемый smoke-тест (`MOVIE_SERVICE_RUN_DATABASE_SMOKE=0`); известный BR-MOV-001 по-прежнему даёт xfail. Реальные записи каталога в новом movies-блоке всё ещё подменены.

`xfail(strict=True)` означает известное несоответствие контракту. При успешном выполнении этого теста после исправления backend набор получит ошибку XPASS, пока отметка не будет удалена. Тест не пропущен и не считается успешным.

Дополнительный учебный тест MOV-DETAIL-005 выполнен отдельно: **1 passed, 28 deselected in 0.19s**. Затем весь блок фильмов/TMDB дал **74 passed, 1 xfailed in 0.69s**, Ruff — **All checks passed!** Блок теперь содержит 75 вариантов. Общий набор с PostgreSQL после добавления этого теста повторно не запускался; результат `121 passed` выше относится к предыдущему состоянию.

Учебный тест TMDB-RECOVERY-001 выполнен отдельно: **1 passed, 29 deselected in 0.19s**. Первый ответ — 502 без сохранения, второй — 200 с точным JSON карточки и одним сохранением. Весь блок после добавления теста дал **75 passed, 1 xfailed in 0.73s**, Ruff прошёл. Теперь в блоке 76 вариантов. Общий набор с PostgreSQL после двух учебных дополнений повторно не запускался.

Учебный тест TMDB-SEC-001 выполнен отдельно: **1 passed, 30 deselected in 0.24s**. Подтверждены отсутствие вымышленного токена в HTTP-ответе и caplog, наличие WARNING от `app.integrations.tmdb`, статус 502 и отсутствие сохранения. Весь блок фильмов/TMDB дал **76 passed, 1 xfailed in 0.69s**, Ruff прошёл. В блоке 77 вариантов. Единственный xfail остаётся BR-MOV-001; полный набор PostgreSQL после учебных дополнений повторно не запускался.

## Следующие проверки

- Реальное сохранение фильмов, жанров и связей, откат транзакций, повторные и конкурентные открытия в отдельной PostgreSQL.
- Ошибка БД 503 и восстановление доступа к локальным карточкам.
- Обработка отсутствующих/неверных claims, подписи и срока JWT; auth API с неверной структурой запросов.
- Локальный каталог, списки, оценки, рецензии, дружба и администрирование — после появления соответствующих endpoint'ов.
