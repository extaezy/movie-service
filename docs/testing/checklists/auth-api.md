# Auth API без PostgreSQL — дополнение 14.11.2026

Проверена рабочая копия поверх `6417a7c`, ветка `feature/auth-qa-tests`. Новые проверки находятся в `backend/tests/test_auth_api.py`, общие фикстуры — в `backend/tests/conftest.py`.

## Область

Настоящие auth-router, Pydantic-схемы, сервис входа, Argon2-проверка пароля, создание и проверка JWT, зависимость текущего пользователя. Подменены получение сессии и три чтения репозитория. Пользователи — экземпляры модели User без записи в БД.

Тесты не требуют Docker, настроенного backend или внешних ключей. Временный JWT-секрет задаётся фикстурой и восстанавливается monkeypatch после теста. Реальное создание/поиск пользователей в PostgreSQL проверяется существующим интеграционным набором; подмены этого дополнения не доказывают правильность SQL.

## Покрытые условия

| Обозначение | Функция | Варианты и проверки |
|---|---|---|
| T-AUTH-17 | `test_login_issues_usable_token_without_sensitive_fields` | Username, email и email с верхним регистром домена — 3 варианта. 200, точные ключи ответа, непустой bearer-токен, отсутствие пароля/хеша; точные аргументы репозитория; токен принимается `/auth/me` |
| T-AUTH-18 | `test_login_requires_fields_without_repository_calls` | Отсутствуют identifier/password — 2 варианта. 422 с ошибкой нужного поля, чтения репозитория не вызываются |
| T-AUTH-19 | `test_login_rejects_invalid_field_types_without_repository_calls` | Null/объект для identifier/password — 4 варианта. 422 с ошибкой нужного поля, чтения репозитория не вызываются |
| T-AUTH-20 | `test_unknown_user_and_wrong_password_have_same_unauthorized_response` | Неизвестный username, email и невалидный email — 3 варианта. Ответы совпадают с отказом при неверном пароле, 401 и WWW-Authenticate: Bearer, токен/пароль/хеш отсутствуют |
| T-AUTH-21 | `test_inactive_user_cannot_login` | Неактивный пользователь не получает токен при правильном пароле |
| T-AUTH-22 | `test_login_preserves_username_case` | STUDENT_1 передаётся в поиск без изменения регистра; при наличии только student_1 получается 401 |
| T-AUTH-23 | `test_login_does_not_trim_password` | Пробел до/после правильного пароля — 2 варианта. 401, токен не выдан |
| T-AUTH-24 | `test_me_rejects_missing_or_malformed_credentials_without_lookup` | Нет заголовка, пустой Bearer, Basic и строка invalid вместо токена — 4 варианта. 401, WWW-Authenticate: Bearer, пользователь не запрашивается |
| T-AUTH-25 | `test_me_rejects_unknown_and_inactive_token_owners` | Владелец действующего токена отсутствует или неактивен — 2 варианта. 401, правильный UUID передан репозиторию |
| T-AUTH-26 | `test_me_returns_only_the_requested_token_owner` | Два пользователя с разными токенами: точные JSON текущей учётной записи, соответствующие UUID/username/email, хеш отсутствует |
| T-AUTH-30 | `test_me_rejects_invalid_jwt_before_user_lookup` | Истечение, будущий iat, неверный ключ, HS384, отсутствие sub/iat/exp, sub не UUID и пустой sub — 9 вариантов. 401, WWW-Authenticate: Bearer, безопасный detail без токена/ключа, чтение пользователя не вызывается |

AUTH-LOGIN-004 полностью покрыта T-AUTH-18–19: два обязательных поля и четыре комбинации неверного типа. Проверки регистра, нормализации email и неактивности в этом дополнении выполняются на подменённом репозитории; сценарии регистрации и изменения записей реальной БД от них учитываются отдельно.

## Результаты

Окружение — Windows, Python 3.13.17, интерпретатор `backend/.venv/Scripts/python.exe`.

Отдельный запуск `pytest tests/test_auth_api.py -q` — **23 passed in 1.22s**. Ruff (`ruff check app tests --no-cache`) — **All checks passed!**

Общий запуск после трёх учебных tests movies и нового auth-блока — **147 passed, 1 skipped, 1 xfailed in 5.77s**. Использована отдельная локальная PostgreSQL `movie_service_automation_test`. Пропущен отдельно включаемый `test_database_auth_with_rollback`, поскольку `MOVIE_SERVICE_RUN_DATABASE_SMOKE=0`; xfail относится к BR-MOV-001. Все 45 вариантов PostgreSQL integration прошли.

## Новые темы для практики

Фикстура `token_context` предоставляет тестовый ключ, UUID, действующий токен, шаблон claims и границы времени создания. Первое учебное задание выполнено в `test_access_token_has_expected_claims`: проверены подпись правильным ключом через PyJWT, HS256, обязательные поля, sub, целочисленные времена, срок 1800 секунд и границы iat. Отдельный запуск дал **1 passed in 0.02s**, Ruff прошёл.

Второе задание выполнено в `test_decode_rejects_invalid_token_times`: истёкший токен и токен с будущим iat, подписанные правильным ключом, отклоняются декодером приложения. На этом этапе файл JWT-тестов дал **3 passed in 0.05s**, включая первое задание; Ruff прошёл. Проверка HTTP-ответов для этих токенов добавлена позднее в T-AUTH-30.

Третье задание выполнено в `test_decode_rejects_invalid_token_credentials`: другой ключ, HS384 и отсутствие каждого из sub/iat/exp отклоняются декодером. Файл `test_tokens.py` дал **8 passed in 0.04s**.

После практики T-AUTH-17 дополнен проверкой токена реального HTTP-входа: подпись, HS256, обязательные claims, UUID, точные целочисленные типы времени, срок 1800 секунд, границы момента выдачи и успешное `/auth/me` проверяются в одном сценарии. AUTH-TOKEN-001 пройдена на API с подменённым репозиторием.

T-AUTH-30 связывает неверные JWT с HTTP-контрактом: все девять вариантов дают безопасный 401 с WWW-Authenticate: Bearer до поиска пользователя. AUTH-ME-004–009 пройдены. JWT и auth API вместе дали **40 passed in 1.21s**, полный набор с PostgreSQL — **164 passed, 1 skipped, 1 xfailed in 4.54s**. Ruff прошёл. Пропущен только отдельно включаемый smoke, xfail — BR-MOV-001.

BR-AUTH-001 остаётся открытым: отсутствие паролей в ошибках валидации этим дополнением не проверяется.
