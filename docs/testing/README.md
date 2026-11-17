# Проверка Movie Service

Основной регресс проверяет согласованные сценарии MVP, правила данных и ошибки API. Для каждого условия выбирается основное место проверки: HTTP API для валидации и токенов, PostgreSQL для сохранения, уникальности и транзакций, адаптер TMDB для формата внешнего запроса и классов ошибок.

[Матрица требований](coverage.md) · [Ручная проверка авторизации](checklists/auth.md) · [Ручная проверка фильмов](checklists/movies.md)

## Быстрый прогон

Команды PowerShell из backend после установки requirements.txt в проектное окружение:

```powershell
.\.venv\Scripts\python.exe -m pytest -q -rs
.\.venv\Scripts\python.exe -m ruff check app tests
```

Без тестовой PostgreSQL интеграционные сценарии пропускаются. Такой прогон подтверждает только проверки с подменённым хранилищем.

## Полный регресс и покрытие

Нужна отдельная одноразовая локальная PostgreSQL. MOVIE_SERVICE_TEST_DATABASE_URL должен указывать только на неё: интеграционные тесты очищают предметные таблицы. Общая Supabase и база разработки для этого набора не используются.

Инструмент coverage устанавливается отдельно в локальное тестовое окружение для измерения покрытия. Общий список зависимостей приложения для этого не изменяется.

```powershell
.\.venv\Scripts\python.exe -m pip install "coverage>=7,<8"
$env:MOVIE_SERVICE_TEST_DATABASE_URL = '<URL отдельной локальной тестовой PostgreSQL>'
$env:DATABASE_URL = $env:MOVIE_SERVICE_TEST_DATABASE_URL
$env:DATABASE_SSL = 'disable'
.\.venv\Scripts\python.exe -m alembic upgrade head
$env:MOVIE_SERVICE_RUN_DATABASE_OUTAGE = '1'
.\.venv\Scripts\python.exe -m coverage run --data-file=../coverage/backend --source=app -m pytest -q -rs
.\.venv\Scripts\python.exe -m coverage report --data-file=../coverage/backend --fail-under=70
Remove-Item Env:MOVIE_SERVICE_RUN_DATABASE_OUTAGE
```

Outage-сценарии требуют Docker Desktop и доступный локальный образ postgres:17. Они создают и останавливают собственный контейнер, проверяют отказ и восстановление в том же приложении и удаляют контейнер с его volume. Тестовая PostgreSQL основного набора при этом продолжает работать.

Покрытие измеряется для всего app, включая команды диагностики. Файлы приложения не исключаются ради достижения NFR.MAINT.03. Прохождение порога 70% не означает полного покрытия бизнес-требований.

## Дополнительная диагностика

Проверки PID, разрыва соединения и замены мёртвого соединения помечены technical и исключены из обычного прогона через pytest.ini. Они используют ту же отдельную тестовую PostgreSQL:

```powershell
.\.venv\Scripts\python.exe -m pytest -m technical tests/test_postgres_integration.py -q
```

Для проверки авторизации на базе из текущих настроек отдельно включается существующий smoke:

```powershell
$env:MOVIE_SERVICE_RUN_DATABASE_SMOKE = '1'
.\.venv\Scripts\python.exe -m pytest tests/test_database_auth_smoke.py -q
Remove-Item Env:MOVIE_SERVICE_RUN_DATABASE_SMOKE
```

Smoke использует внешнюю транзакцию и savepoint, откатывает свои записи и проверяет очистку. Он служит диагностикой окружения и не заменяет проверки реального commit.

## Ведение документации

Матрица хранит связи требований с актуальными тестами и пробелы. Чек-листы содержат ручные проверки интерфейса и взаимодействия компонентов. Документация описывает реализованные проверки, открытые дефекты и запланированные задачи QA.

Ручной API-прогон автоматизированных условий нужен при расследовании дефекта или изменении контракта. В обычной проверке интерфейса оцениваются отображение данных, состояния loading/success/empty/error, блокировка кнопок и показ ошибок.
