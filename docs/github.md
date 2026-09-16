# GitHub-процесс

## Создание репозитория

Создайте на GitHub пустой репозиторий `movie-service` без README и `.gitignore`, затем выполните:

```powershell
cd "C:\Users\User\PycharmProjects\IT managment"
git init
git add .
git commit -m "docs: define MVP and week one artifacts"
git branch -M main
git remote add origin https://github.com/USERNAME/movie-service.git
git push -u origin main
```

Если репозиторий уже существует локально, `git init` повторно не выполняйте.

## Командная работа

- `main` всегда должна запускаться;
- одна задача — одна ветка;
- примеры: `feature/backend-auth`, `feature/frontend-catalog`, `docs/week-one`;
- изменения объединяются через Pull Request;
- перед merge второй участник проверяет код;
- секреты хранятся только в `.env`, в GitHub попадает `.env.example`.

## Первые Issues

1. `W1: зафиксировать MVP и ограничения`.
2. `W1: утвердить ER-схему`.
3. `W1: согласовать API-контракт`.
4. `W1: подготовить frontend wireframes`.
5. `W2: создать FastAPI-каркас`.
6. `W2: создать React/Vite-каркас`.
7. `W2: проверить PostgreSQL и TMDB`.

У каждой Issue должны быть цель, исполнитель, критерии готовности, связанные endpoint/страницы и номер недели.

## Commit convention

```text
feat: новая функция
fix: исправление
test: тесты
docs: документация
chore: инфраструктура
refactor: реорганизация без изменения поведения
```

## Авторизация GitHub

Для HTTPS используйте Git Credential Manager или GitHub Desktop. Пароль GitHub через Git не вводите; при запросе используйте Personal Access Token. Альтернатива — SSH-ключ и remote вида `git@github.com:USERNAME/movie-service.git`.

## Защита main

После первого push включите запрет прямого push в `main`, обязательный Pull Request, проверку второго участника и удаление ветки после merge.

