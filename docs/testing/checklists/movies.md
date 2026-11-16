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

Дополнительный тест MOV-DETAIL-005 выполнен отдельно: **1 passed, 28 deselected in 0.19s**. Затем весь блок фильмов/TMDB дал **74 passed, 1 xfailed in 0.69s**, Ruff — **All checks passed!** Блок теперь содержит 75 вариантов. Общий набор с PostgreSQL после добавления этого теста повторно не запускался; результат `121 passed` выше относится к предыдущему состоянию.

Тест TMDB-RECOVERY-001 выполнен отдельно: **1 passed, 29 deselected in 0.19s**. Первый ответ — 502 без сохранения, второй — 200 с точным JSON карточки и одним сохранением. Весь блок после добавления теста дал **75 passed, 1 xfailed in 0.73s**, Ruff прошёл. Теперь в блоке 76 вариантов. Общий набор с PostgreSQL после двух дополнений повторно не запускался.

Тест TMDB-SEC-001 выполнен отдельно: **1 passed, 30 deselected in 0.24s**. Подтверждены отсутствие вымышленного токена в HTTP-ответе и caplog, наличие WARNING от `app.integrations.tmdb`, статус 502 и отсутствие сохранения. Весь блок фильмов/TMDB дал **76 passed, 1 xfailed in 0.69s**, Ruff прошёл. В блоке 77 вариантов. Единственный xfail остаётся BR-MOV-001; полный набор PostgreSQL после дополнений повторно не запускался.

## PostgreSQL — дополнение 15.11.2026

Проверена рабочая копия поверх `bec6a23`, ветка `feature/backend-qa-tests`. Новые сценарии находятся в `backend/tests/test_postgres_integration.py`. Используются настоящее приложение, зависимости БД, репозиторий и PostgreSQL; только внешний HTTP подменён через MockTransport. Lifespan приложения и доступ к живому TMDB не проверяются.

Окружение: Windows, Python 3.13.17, Docker-контейнер `movie-service-test-db`, отдельная локальная БД `movie_service_automation_test`, порт `127.0.0.1:55432`. Перед каждым тестом предметные таблицы очищаются штатной фикстурой модуля. Состояние после HTTP-запроса проверяется через новую сессию.

| ID | Условия | Автоматизация | Результат |
|---|---|---|---|
| MOV-DB-001 | Импорт фиксирует фильм, два жанра и правильные связи; API возвращает полную карточку, чтение по внутреннему ID использует сохранённые данные | `test_movie_import_commits_movie_genres_and_links` | Пройдено |
| MOV-DB-002 | Пустая дата и runtime 0 сохраняются как NULL; карточка без жанров не создаёт Genre и MovieGenre | `test_movie_import_persists_unknown_date_and_runtime` | Пройдено |
| MOV-DB-003 | Два фильма используют общий существующий жанр, его название не перезаписывается; повтор жанра в одном ответе не создаёт лишнюю запись или связь | `test_movie_import_reuses_existing_genres_and_deduplicates_links` | Пройдено |
| MOV-DB-004 | Повторное открытие по tmdb_id и чтение по внутреннему ID дают прежнюю карточку без внешнего вызова и дублей, включая отсутствие токена TMDB | `test_cached_movie_is_read_from_database_without_tmdb`, 2 варианта | Пройдено |
| MOV-DB-005 | 404, adult, несовпадающий ID и таймаут TMDB дают ожидаемые 404/502 и не оставляют записей каталога | `test_failed_movie_import_leaves_catalog_empty`, 4 варианта | Пройдено |
| MOV-DB-006 | Смоделированная ошибка БД после вставки фильма, жанра и связи даёт 503 и откатывает все три записи; следующий запрос сохраняет карточку | `test_movie_import_rolls_back_all_catalog_rows_after_database_failure` | Пройдено |
| MOV-DB-007 | Два запроса одного отсутствующего фильма возвращают одну согласованную карточку без перезаписи и дублей | `test_concurrent_movie_imports_keep_one_card` | Пройдено: целая исходная версия, барьер, ответы, БД и кеш |
| MOV-DB-008 | Конкурентный импорт разных фильмов с новым общим жанром создаёт один жанр и две связи | `test_concurrent_movie_imports_share_one_genre` | Пройдено: карточки, общий жанр, записи и точные пары связей |

Целевой прогон новых сценариев: **10 passed, 45 deselected in 3.83s**. Полный backend-набор: **174 passed, 1 skipped, 1 xfailed in 22.00s**. Ruff (`check app tests --no-cache`) — **All checks passed!** Пропущен отдельно включаемый smoke, известный BR-MOV-001 остаётся strict xfail. Все 55 вариантов PostgreSQL integration выполнены.

MOV-DB-006 подменяет формирование карточки после SQL-вставок и выбрасывает SQLAlchemyTimeoutError. В той же транзакции предварительно подтверждено наличие всех трёх записей. Тест проверяет реальный rollback и повторную попытку после снятия подмены; остановка сервера PostgreSQL и восстановление соединения не моделируются. MOV-DB-004 запрещает внешний вызов, но не воспроизводит реальный сетевой сбой.

Промежуточный этап MOV-DB-007: обработчик, барьер и статусы дали **1 passed, 55 deselected in 0.41s**. После добавления знакомых проверок ответов, БД и кеша блок каталога дал **11 passed, 45 deselected in 1.06s**. Полный backend-набор после этого этапа повторно не запускался. До проверки согласованности title и жанра с одним исходным payload сценарий не считается завершённым.

MOV-DB-007 завершена: допустимые кортежи `(title, внешний ID жанра, name жанра)` строятся из обоих исходных payload; фактический кортеж должен совпасть с одним из них. Отдельный тест дал **1 passed, 55 deselected in 0.44s**, блок каталога — **11 passed, 45 deselected in 0.94s**, полный backend-набор — **175 passed, 1 skipped, 1 xfailed in 5.36s**. Все 56 вариантов PostgreSQL integration выполнены; пропущен только smoke, xfail — BR-MOV-001. Ruff прошёл. Конкурентный импорт разных фильмов с новым общим жанром остаётся отдельной MOV-DB-008.

MOV-DB-008 завершена: два разных фильма импортируются через общий барьер, получают разные внутренние ID и один общий жанр. Новая сессия подтверждает две записи Movie, одну Genre и две точные пары MovieGenre; внутренние ID, названия и жанр соответствуют ответам API. Отдельный тест дал **1 passed, 56 deselected in 0.44s**, блок каталога — **12 passed, 45 deselected in 1.22s**, полный backend-набор — **176 passed, 1 skipped, 1 xfailed in 5.82s**. Все 57 вариантов PostgreSQL integration выполнены; Ruff прошёл. Пропущен только smoke, xfail — BR-MOV-001. Порядок SQL после барьера свободный, ожидание блокировки PostgreSQL отдельно не устанавливается.

## Ошибки чтения БД — дополнение 15.11.2026

Добавлены знакомые проверки в `backend/tests/test_movies_api.py`, рабочая копия поверх `bec6a23`. Фикстура movie_database_api включает настоящий get_db; фабрика сессий и функции репозитория подменены. Ошибка возникает при чтении карточки и проходит через обработчик зависимости. SQL и реальное состояние PostgreSQL этим блоком не проверяются; вызовы rollback и выхода из контекста сессии контролируются через AsyncMock.

| ID | Условия | Автоматизация | Результат |
|---|---|---|---|
| MOV-DATA-001 | OperationalError, таймаут пула, отказ подключения и TimeoutError при чтении по внутреннему ID или tmdb_id дают безопасный 503; сессия откатывается и выходит из контекста; TMDB и сохранение не вызываются | `test_database_read_errors_return_safe_503`, 8 вариантов | Пройдено на внедрённых ошибках |
| MOV-DATA-002 | После сбоя локального чтения поиск доступен в том же приложении и не вызывает фабрику сессий | `test_database_read_failure_keeps_movie_search_available` | Пройдено на внедрённой ошибке |
| MOV-DATA-003 | После внедрённого сбоя следующий запрос к той же карточке успешен без пересоздания клиента и приложения | `test_local_movie_read_recovers_after_database_error` | Пройдено на внедрённой ошибке |

Новые проверки дали **9 passed, 31 deselected in 0.27s**, блок фильмов/TMDB — **85 passed, 1 xfailed in 0.73s**. Полный backend-набор с PostgreSQL — **185 passed, 1 skipped, 1 xfailed in 5.46s**; Ruff прошёл. Все 57 вариантов PostgreSQL integration выполнены. Пропущен только smoke, xfail — BR-MOV-001.

Реальная недоступность PostgreSQL и восстановление пула остаются отдельной проверкой. В новом блоке подтверждена реакция get_db на предусмотренные исключения и изоляция поиска от сбоя чтения.

MOV-DATA-003 завершена: существующему моку чтения задан side_effect из ошибки и карточки. Первый запрос даёт точный 503, второй через тот же клиент — точный 200. Подтверждены два await чтения, один rollback, два вызова фабрики сессий и её контекста, отсутствие другого способа чтения, сохранения и TMDB. Отдельный запуск дал **1 passed, 40 deselected in 0.25s**; после дополнения проверок блок дал **10 passed, 31 deselected in 0.30s**. Полный backend-набор — **186 passed, 1 skipped, 1 xfailed in 6.70s**; Ruff прошёл. Пропущен smoke, xfail — BR-MOV-001. Реальное восстановление соединения PostgreSQL остаётся непроверенным.

## Реальный разрыв соединения — дополнение 15.11.2026

Рабочая копия поверх `bec6a23`. В `backend/tests/test_postgres_integration.py` добавлена isolated_movie_database: отдельный engine с pool_pre_ping=True, одним слотом и уникальным application_name. get_db временно использует его настоящую фабрику сессий. Обрыв ограничен PID этого пула, меткой теста и текущей локальной БД; управляющий SQL идёт через другой engine. После теста исходная фабрика восстанавливается, отдельный engine освобождается.

| ID | Условия | Автоматизация | Результат |
|---|---|---|---|
| MOV-CONN-001 | Разрыв полученного соединения внутри чтения даёт 503; следующий запрос через прежнее приложение возвращает ту же карточку с новым PID; запись сохраняется, TMDB не вызывается | `test_local_movie_read_recovers_after_connection_termination` | Пройдено на реальном соединении |
| MOV-CONN-002 | Разрыв свободного соединения из пула скрывается при следующем чтении: 200 с прежней карточкой и новый PID | `test_local_movie_read_replaces_dead_idle_connection` | Пройдено на реальном соединении |

Отдельный тест MOV-CONN-001 дал **1 passed, 57 deselected in 1.12s**, полный backend-набор — **187 passed, 1 skipped, 1 xfailed in 11.50s**; Ruff прошёл. Все 58 вариантов PostgreSQL integration выполнены. Пропущен smoke, xfail — BR-MOV-001.

Момент разрыва задаётся обёрткой репозитория; исключение возникает в настоящем SQL-чтении после pg_terminate_backend. Сервер PostgreSQL продолжает работать. Полная недоступность сервера, отказ новых соединений и восстановление после перезапуска пока не проверены.

MOV-CONN-002 завершена: сохранена исходная карточка, свободное соединение завершено один раз после выхода из контекста сессии. Первое обращение пула после разрыва — HTTP-чтение — дало 200 с прежним JSON; последующий SQL подтвердил другой PID. Проверены точная история завершений и отсутствие TMDB. Отдельно получено **1 passed, 58 deselected in 0.55s**, оба сценария — **2 passed, 57 deselected in 0.65s**, полный backend-набор — **188 passed, 1 skipped, 1 xfailed in 5.67s**. Все 59 вариантов PostgreSQL integration выполнены; Ruff прошёл. Пропущен smoke, xfail — BR-MOV-001. Полная недоступность сервера остаётся отдельным сценарием.

## Полная недоступность PostgreSQL — дополнение 15.11.2026

В `backend/tests/test_database_outage.py` готова изолированная инфраструктура: собственный контейнер PostgreSQL 17, новая БД с миграцией, настоящий engine и контекстный менеджер остановки/запуска. Существующий movie-service-test-db в сценарии не останавливается. Пройденный auth-сценарий также подтверждает доступность поиска через MockTransport во время остановки БД. Чтение карточек при полном отказе проверено отдельным MOV-OUTAGE-001.

| ID | Условия | Автоматизация | Результат |
|---|---|---|---|
| MOV-OUTAGE-001 | До отказа карточка доступна; во время остановки чтение по внутреннему ID и tmdb_id даёт безопасный 503; после запуска оба маршрута возвращают прежнюю карточку без TMDB | `test_movie_reads_recover_after_database_outage` | Пройдено |

Инфраструктура и auth-сценарий отдельно дали **1 passed in 12.87s**, полный набор с outage — **189 passed, 1 skipped, 1 xfailed in 21.07s**; Ruff прошёл. Число не означает завершение MOV-OUTAGE-001. Набор включается переменной MOVIE_SERVICE_RUN_DATABASE_OUTAGE=1.

MOV-OUTAGE-001 завершена: во время остановки оба способа чтения карточки дают точный безопасный 503; после восстановления — 200 и исходный JSON без TMDB. Клиент, FastAPI и engine сохраняются. Отдельный тест — **1 passed, 1 deselected in 10.70s**, полный набор с обоими outage-сценариями — **190 passed, 1 skipped, 1 xfailed in 28.71s**; Ruff прошёл. Все 59 вариантов обычного PostgreSQL integration выполнены. Пропущен smoke, xfail — BR-MOV-001. Временный контейнер удалён, исходная тестовая БД доступна.

## Локальный каталог — после слияния test 15.11.2026

Основание — [API локального каталога](../../api.md#локальный-каталог), задача #54. Проверена рабочая копия поверх `83c24ef` с реализацией из `origin/test` (`0472125`). SQL-сценарии используют `movie_service_automation_test` с миграцией `20261113_0002`.

| ID | Условия | Автоматизация | Результат |
|---|---|---|---|
| MOV-CAT-001 | Публичный доступ, параметры по умолчанию, сочетание параметров, допустимые границы; неверные параметры дают 422 до вызова репозитория | `test_catalog_is_public_and_passes_valid_parameters`, 4 варианта; `test_catalog_rejects_invalid_parameters_before_repository_calls`, 13 вариантов | Пройдено на API с моками репозитория |
| MOV-CAT-002 | Сохранённые фильмы, фильтр по внутреннему genre_id, весь год включая 1 января и 31 декабря, AND двух фильтров; внешний ID вместо внутреннего и неизвестные фильтры дают пустую выдачу | `test_catalog_filters_saved_movies_without_tmdb`, 10 вариантов | Пройдено с PostgreSQL, точными карточками и запретом TMDB |
| MOV-CAT-003 | Дата по возрастанию и убыванию; внутренний ID возрастает при равенстве; неизвестные даты в конце | `test_catalog_sorts_dates_with_id_ties_and_nulls_last`, 2 варианта | Пройдено на одной странице с PostgreSQL |
| MOV-CAT-004 | Пустой каталог; размеры 1, 19, 20, 21, 40, 41; счётчики после фильтрации; страница за пределами выдачи и максимальный page | `test_catalog_pagination_counts_at_page_boundaries`, 8 вариантов; `test_catalog_out_of_range_page_preserves_filtered_totals`, 2 варианта | Пройдено с PostgreSQL |
| MOV-CAT-005 | Четыре предусмотренных исключения БД дают точный безопасный 503 и rollback без внешнего вызова | `test_catalog_database_errors_return_safe_503`, 4 варианта | Пройдено на внедрённых ошибках через настоящий get_db |
| MOV-CAT-006 | Одинаковые даты пересекают границу страниц; нет пропусков/дублей, полный порядок правильный, повтор страницы стабилен | `test_catalog_keeps_stable_order_across_page_boundary`, 2 варианта | Пройдено с PostgreSQL |

Целевой прогон каталога и 8 вариантов безопасной регистрации: **51 passed, 100 deselected in 1.86s**. Полный backend-набор с обоими outage-сценариями: **241 passed, 1 skipped, 1 xfailed in 23.30s**; Ruff прошёл. Пропущен smoke, xfail — BR-MOV-001. Все 89 вариантов обычного PostgreSQL integration выполнены.

MOV-CAT-006 завершена: отдельно **2 passed, 89 deselected in 0.66s**. Проверены номера страниц, метаданные каждого ответа, точные ID обеих страниц, объединённый порядок и уникальность всех 24 ID, повтор первой страницы с тем же JSON и отсутствие TMDB. Полный набор после завершения: **243 passed, 1 skipped, 1 xfailed in 23.27s**, все 91 вариант PostgreSQL integration и оба outage-сценария выполнены. Ruff прошёл; skip и xfail прежние. Все сценарии MOV-CAT-001–006 пройдены, статусы во внешнем taskboard не менялись.

Восстановлена совместимость старых тестов карточки с новыми полями `average_rating`, `ratings_count`, `tmdb_vote_average`, `tmdb_vote_count`, `tmdb_rating_updated_at`. Это не заменяет отдельные сценарии оценок и сохранения голосов TMDB. Живой TMDB, нагрузка и изменение каталога между запросами страниц в результат не входят.

## Витрина TMDB — 15.11.2026

Основание — [API витрины TMDB](../../api.md#витрина-tmdb), задача #55. Проверена рабочая копия поверх `83c24ef`. Настоящие роутер, клиент TMDB и Pydantic выполняются; внешний HTTP заменён MockTransport с вымышленным токеном. Моки репозиториев позволяют проверять отсутствие обращений к БД. Отдельный outage-сценарий использует настоящее приложение и свой PostgreSQL.

| ID | Условия | Автоматизация | Результат |
|---|---|---|---|
| MOV-DISC-001 | Публичный доступ; параметры по умолчанию, фильтры отдельно и вместе; все три сортировки, допустимые границы; имена параметров TMDB, авторизация провайдера, таймаут и полный нормализованный JSON | `test_discover_is_public_and_translates_request_parameters`, 7 вариантов | Пройдено; БД и сохранение не вызываются |
| MOV-DISC-002 | Неверные page, tmdb_genre_id, year, sort дают 422 до внешнего HTTP и обращения к БД | `test_discover_rejects_invalid_parameters_without_http_or_database`, 13 вариантов | Пройдено |
| MOV-DISC-003 | Пустая выдача; total_pages 1, 499, 500, 501, 1000 нормализуется с пределом 500; результаты и total_results сохраняются | `test_discover_returns_empty_page_without_database`, 1 вариант; `test_discover_caps_total_pages_and_preserves_results`, 5 вариантов | Пройдено |
| MOV-DISC-004 | Отсутствующий токен TMDB даёт 503 без внешнего запроса и сохранения | Вариант `/movies/discover` в `test_unconfigured_tmdb_returns_503_without_saving` | Пройдено |
| MOV-DISC-005 | HTTP 302/401/403/404/429/500/503, сетевые ошибки, неверные JSON и данные дают безопасный 502; токен не раскрывается, переход по редиректу не выполняется | `test_discover_http_errors_are_safe_and_do_not_follow_redirects`, 7; `test_discover_invalid_upstream_data_returns_safe_502`, 6; timeout API, 1; варианты discover общих тестов `test_tmdb.py`, 9 | Пройдено, всего 23 варианта |
| MOV-DISC-006 | После ConnectError тот же API-клиент получает успешный ответ следующего запроса без БД | `test_discover_recovers_after_network_failure_without_database` | Пройдено |
| MOV-DISC-007 | Витрина возвращает прежний JSON до остановки PostgreSQL, при остановке и после запуска; локальное чтение при остановке даёт 503 | `test_discover_stays_available_during_database_outage` | Пройдено на собственном одноразовом контейнере |
| MOV-DISC-008 | Неизвестные поля на уровне страницы и фильма не меняют нормализованный JSON, исходные тестовые данные независимы | `test_discover_ignores_unknown_upstream_fields`, 3 варианта | Пройдено |

Целевой блок без outage: **51 passed, 108 deselected in 0.78s**. Полный backend-набор с тремя outage-сценариями: **295 passed, 1 skipped, 1 xfailed in 26.29s**. Все 91 вариант обычного PostgreSQL integration выполнены. Ruff прошёл. Пропущен отдельный smoke; strict xfail — BR-MOV-001. Новые выполненные варианты discover: 52; три дополнительных варианта MOV-DISC-008 в число не входят.

MOV-DISC-008 завершена: отдельно **3 passed, 104 deselected in 0.42s**. Подтверждены независимость исходных данных, точный исходный ответ, сохранение JSON после добавления неизвестных полей на двух уровнях, отсутствие строки-маркера, два внешних вызова и отсутствие обращений к БД и репозиториям. Полный набор после завершения: **298 passed, 1 skipped, 1 xfailed in 29.34s**; Ruff прошёл. Все 91 вариант PostgreSQL integration и три outage-сценария выполнены. Теперь для discover выполнены 55 вариантов; все MOV-DISC-001–008 пройдены.

Живой TMDB и frontend не проверяются. Внешние фильтрация и сортировка здесь проверены как правильный запрос провайдеру; результаты выдачи формирует MockTransport. Нагрузку, устойчивость живого TMDB и корректность его реального каталога этот результат не подтверждает. Для outage останавливается отдельный контейнер теста, исходный `movie-service-test-db` не останавливается.

## Следующие проверки

- Дополнительные типы claims JWT; базовые сценарии подписи, срока и структуры auth-запросов уже выполнены в `test_tokens.py` и [auth API](auth-api.md).
- Проверить оценки, списки и рецензии. Дружба и администрирование требуют отдельной проверки готовности endpoint'ов.
