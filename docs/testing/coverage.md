# Матрица покрытия требований

Область — действующие требования и API-контракт MVP. Основной текст требований имеет приоритет перед ошибочными соответствиями ID в RTM. Команды запуска приведены в [инструкции](README.md).

Наличие теста означает наличие проверки перечисленного условия. Полное покрытие бизнес-требования устанавливается по всем его сценариям, включая ещё не реализованные и не проверенные.

## Авторизация

| Требование / условие | Основная автоматизация | Границы |
|---|---|---|
| FR.AUTH.01; создание пользователя и профиля, Argon2id | test_registration_commits_user_and_profile | Настоящие commit и повторное подключение PostgreSQL |
| FR.AUTH.01 и API; обязательность полей, типы, email, безопасный 422 | test_registration_validation_errors_do_not_expose_input | 17 вариантов; ошибка нужного поля, отсутствие значений запроса и записей в БД |
| FR.AUTH.01 и БД; длина и формат username | test_registration_validates_username_length; test_registration_validates_username_format | Границы и разрешённые/запрещённые форматы сохранены |
| FR.AUTH.02; последовательные и конкурентные дубли | test_duplicate_registration_is_conflict; test_concurrent_registration_rejects_duplicates | Username и email проверяются отдельно |
| API; регистр username | test_registration_treats_usernames_as_case_sensitive; test_login_preserves_username_case | Разные учётные записи и точный поиск |
| API; атомарность регистрации | test_registration_rolls_back_when_profile_creation_fails | Ошибка после flush пользователя не оставляет пользователя и профиль |
| FR.AUTH.03–04; вход по username/email, выдача и применение токена | test_login_and_me | PostgreSQL, оба предусмотренных идентификатора |
| FR.AUTH.04, NFR.SEC.05; нормализация email и параметры JWT | test_login_issues_usable_token_without_sensitive_fields | Один HTTP-вход с верхним регистром домена; HS256, sub/iat/exp, 1800 секунд и /auth/me |
| FR.AUTH.03 и API; неверная структура входа | test_login_requires_fields_without_repository_calls; test_login_rejects_invalid_field_types_without_repository_calls | Отсутствие, null и объект для обоих полей |
| FR.AUTH.03, NFR.SEC.02; неверные данные и неактивность | test_inactive_user_and_wrong_credentials_are_rejected; test_unknown_user_and_wrong_password_have_same_unauthorized_response | Реальная деактивация; в API отдельно остаются неизвестный и некорректный email |
| API; пароль не нормализуется | test_login_does_not_trim_password | Пробел в начале и конце |
| NFR.SEC.02; текущая учётная запись | test_me_returns_token_owner; test_me_rejects_unknown_token_owner | Два владельца проверяются с PostgreSQL; отсутствующий UUID — на API с подменённым чтением |
| NFR.SEC.05; недействительный токен | test_me_rejects_missing_or_malformed_credentials_without_lookup; test_me_rejects_invalid_jwt_before_user_lookup | 4 варианта заголовка и 9 вариантов JWT; HTTP 401 и WWW-Authenticate |
| FR.AUTH.05 | Отложено в API | Logout и отзыв JWT не реализованы |
| FR.USER.01 | Только /auth/me | Проверка полного профиля сюда не входит |

## Фильмы и внешняя интеграция

| Требование / условие | Основная автоматизация | Границы |
|---|---|---|
| FR.MOV.04; поиск, пустая выдача, границы q/page | test_search_is_public_and_uses_external_ids_without_database; test_search_returns_empty_results; test_search_accepts_parameter_boundaries; test_search_rejects_invalid_parameters_without_external_calls | HTTP API; поиск не использует БД; формат внешнего запроса отдельно проверяет test_search_sends_expected_request_and_normalizes_response |
| API; длина q после strip | test_search_validates_length_after_trimming | Открытый BR-MOV-001, strict xfail |
| FR.MOV.05–06; карточка, импорт, жанры, нормализация NULL | test_movie_import_commits_movie_genres_and_links; test_movie_import_persists_unknown_date_and_runtime | Ответ и сохранение проверяются вместе на PostgreSQL |
| FR.MOV.06, BRULE.MOV.01–02; повторное чтение и отсутствие дублей | test_cached_movie_is_read_from_database_without_tmdb; test_movie_import_reuses_existing_genres_and_deduplicates_links | Сохранённая карточка доступна без TMDB; жанры и связи проверяются в БД |
| FR.MOV.06; конкурентные открытия | test_concurrent_movie_imports_keep_one_card; test_concurrent_movie_imports_share_one_genre | Отдельные гонки для одной карточки и общего жанра сохранены |
| API; неверный ID, отсутствующий фильм, отказ импорта | test_invalid_movie_ids_do_not_reach_repositories; test_unknown_local_movie_is_not_found_without_import; test_failed_movie_import_leaves_catalog_empty | 404, adult, неверный внешний ID, таймаут; отсутствие записей в БД |
| API; атомарность импорта | test_movie_import_rolls_back_all_catalog_rows_after_database_failure | Откат фильма, жанра и связи после фактических вставок |
| FR.MOV.01–03, частично; локальный каталог | test_catalog_is_public_and_passes_valid_parameters; test_catalog_rejects_invalid_parameters_before_repository_calls; test_catalog_filters_saved_movies_without_tmdb; test_catalog_sorts_dates_with_id_ties_and_nulls_last | Фильтры жанр/год/AND и две сортировки по дате; сортировка по рейтингу отложена |
| API; пагинация и стабильный порядок | test_catalog_pagination_counts_at_page_boundaries; test_catalog_out_of_range_page_preserves_filtered_totals; test_catalog_keeps_stable_order_across_page_boundary | Пустая/полная/неполная страницы, выход за пределы, счётчики после фильтрации, два направления сортировки |
| FR.MOV.01–03, частично; витрина TMDB | test_discover_is_public_and_translates_request_parameters; test_discover_rejects_invalid_parameters_without_http_or_database; test_discover_returns_empty_page_without_database | Публичность, фильтры, три поддерживаемых порядка, отсутствие БД |
| API; предел витрины и нормализация ответа | test_discover_caps_total_pages_and_preserves_results; test_discover_ignores_unknown_upstream_fields | 499/500/501; дополнительные поля страницы и фильма проверяются вместе |
| API; классы ошибок TMDB, HTTPS и защита ключа | test_upstream_http_errors_are_safe_bad_gateway_responses; test_network_failures_become_safe_bad_gateway_responses; test_invalid_json_becomes_bad_gateway; test_unsafe_base_url_is_rejected | 302/401/429/500 для общего обработчика страниц и отдельного обработчика карточки; таймаут/сеть; без повторения discover |
| API; особенности ошибок карточки и витрины | test_get_movie_preserves_not_found_status; test_get_movie_handles_adult_content; test_discover_upstream_not_found_returns_safe_502; test_failed_movie_import_does_not_save_data | 404 карточки отличается от 502 витрины |
| API; некорректные данные и отсутствие настройки TMDB | test_invalid_movie_details_become_bad_gateway; test_invalid_search_response_becomes_bad_gateway; test_discover_invalid_upstream_data_returns_safe_502; test_unconfigured_tmdb_returns_503_without_saving; test_missing_token_is_configuration_error_without_http | В адаптере проверяется формат данных; API подтверждает безопасный ответ |
| NFR.REL.01; восстановление TMDB и работа локальных функций | test_movie_import_recovers_after_timeout; test_discover_recovers_after_network_failure_without_database; test_cached_movie_is_read_from_database_without_tmdb | Повторный запрос через то же приложение; локальная карточка не требует TMDB |

## Данные и надёжность

| Требование / условие | Основная автоматизация | Границы |
|---|---|---|
| NFR.REL.02; безопасное преобразование ошибок БД | test_database_dependency_returns_safe_503_and_rolls_back | Четыре класса исключений один раз на get_db; rollback и безопасный detail |
| NFR.REL.02; HTTP 503 маршрутов чтения | test_database_read_errors_return_safe_503 | По одному случаю для локального ID, tmdb_id и каталога |
| NFR.REL.02–03; остановка и восстановление PostgreSQL | test_auth_returns_503_during_database_outage_and_recovers; test_movie_reads_recover_after_database_outage; test_discover_stays_available_during_database_outage | Собственный контейнер; те же приложение, клиент и engine; поиск/витрина доступны без БД |
| BRULE.CNT.01,03,05–07; ограничения контента | test_invalid_ratings_are_rejected; test_unique_content_and_multiple_lists | Только ограничения БД; операции API этим не подтверждаются |
| BRULE.FRD.02 и БД; допустимая пара дружбы | test_friendship_cannot_be_self_or_have_unrelated_requester | Проверены self, нормализация пары и принадлежность отправителя; полный сценарий дружбы не проверен |
| БД; согласованность критика и источника | test_critic_source_consistency_and_unknown_author | Не подтверждает BR.04 целиком |
| БД; внешние ключи, каскадное удаление, схема и RLS | test_missing_foreign_key_and_cascade_delete; test_tables_have_rls_and_root_is_available; test_metadata_is_scoped_to_application_schema | Технические ограничения схемы |
| NFR.MAINT.01,03 | Alembic upgrade head; coverage --source=app | Миграции и порог 70% проверяются при полном прогоне |

Дополнительные technical-проверки test_local_movie_read_recovers_after_connection_termination и test_local_movie_read_replaces_dead_idle_connection подтверждают детали пула. Smoke test_database_auth_with_rollback диагностирует выбранное окружение. Они не дублируются в обязательной матрице пользовательских сценариев.

## Оставшиеся пробелы MVP

- BR.02: API оценок и агрегаты, операции списков и рецензий, права владельца требуют целевого QA. Тесты ограничений БД их не заменяют.
- BR.03: полный профиль, приватность и дружба требуют отдельных сценариев. /auth/me покрывает только текущую учётную запись.
- BR.04: просмотр и администрирование профессиональных рецензий не подтверждены интеграционным сценарием.
- FR.MOV.03: сортировка по рейтингу остаётся отложенной в текущем API.
- Нагрузочные требования, перезапуск процесса backend, сохранность Docker volume и отсутствие секретов во всех компонентах этим набором полностью не подтверждаются.
- Frontend имеет отдельные ручные чек-листы; сборка не подтверждает прохождение пользовательских сценариев.
