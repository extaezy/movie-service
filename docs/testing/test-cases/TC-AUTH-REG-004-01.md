# TC-AUTH-REG-004-01 — Регистрация без username

| Поле | Значение |
|---|---|
| Статус | Автоматизирован |
| Тип проверки | API, негативная, функциональная |
| Компонент | `POST /auth/register` |
| Требование | FR.AUTH.01, обязательность username и отказ `422` при ошибке валидации |

Цель — проверить, что регистрация без username отклоняется, не раскрывает чувствительные данные и не создаёт пользователя и профиль.

Источники: [требования](../../requirements.md), [API-контракт](../../api.md#текущий-этап-postgresql-и-access-jwt), [схема БД](../../database.md), [матрица покрытия](../coverage.md#авторизация).

## Предусловия

- Backend подключён к отдельной тестовой PostgreSQL с применёнными миграциями.
- В БД нет пользователя с email `qa.required@example.com`.
- Другие запросы и тесты не изменяют данные этой БД во время проверки.
- Для ручной проверки доступны Swagger UI и отдельное подключение к этой же БД.

## Тестовые данные

Поле username отсутствует. Остальные поля корректны; пароль — вымышленное тестовое значение.

```json
{
  "email": "qa.required@example.com",
  "password": "testing-password-123",
  "password_confirm": "testing-password-123"
}
```

## Шаги и ожидаемые результаты

| № | Действие | Ожидаемый результат |
|---|---|---|
| 1 | Зафиксировать количество пользователей и профилей, проверить отсутствие тестового email | Известно исходное состояние БД |
| 2 | Отправить `POST /auth/register` с тестовыми данными | `422`, непустой массив `detail` |
| 3 | Проверить ошибки | Ошибка username содержит `loc=["body", "username"]` и `type=missing`; каждая ошибка содержит только `loc`, `msg`, `type`; значения запроса отсутствуют |
| 4 | Прочитать состояние БД через отдельное подключение | Тестовый пользователь отсутствует; количество пользователей и профилей не изменилось |

SQL для ручной проверки до и после запроса:

```sql
SELECT count(*) AS users_total FROM movie_service.users;
SELECT count(*) AS profiles_total FROM movie_service.profiles;
SELECT id, username FROM movie_service.users WHERE email = 'qa.required@example.com';
```

## Постусловия

Состояние пользователей и профилей не изменяется. Очистка данных после успешной проверки не требуется.

## Автоматизация

Вариант включён в `test_registration_validation_errors_do_not_expose_input` в [тестах PostgreSQL](../../../backend/tests/test_postgres_integration.py). Функция также проверяет другие ошибки регистрации и безопасный состав ответа, описанный в [BR-AUTH-001](../bug-reports/BR-AUTH-001.md).

Команда PowerShell из backend:

```powershell
.\.venv\Scripts\python.exe -m pytest "tests/test_postgres_integration.py::test_registration_validation_errors_do_not_expose_input[missing-username]" -v
```

Требуется MOVIE_SERVICE_TEST_DATABASE_URL для отдельной локальной тестовой PostgreSQL. Без этой переменной тест пропускается. Условия полного набора приведены в [инструкции](../README.md).
