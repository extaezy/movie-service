# Практика JWT

Знакомая подготовка реализована в фикстуре `token_context` из `backend/tests/conftest.py`. Задания ниже выполняются самостоятельно в новом `backend/tests/test_tokens.py`. Незавершённые каркасы пока находятся только в этом документе и не собираются pytest как тесты.

## Что проверяем

JWT содержит заголовок, payload и подпись. Подпись позволяет проверить целостность и ключ отправителя; содержимое payload не следует считать зашифрованным. В нашем контракте разрешён HS256, обязательны sub, iat и exp, срок действия — 1800 секунд.

- sub — UUID владельца строкой.
- iat — время выдачи в целых секундах Unix UTC.
- exp — момент истечения в тех же единицах.

`jwt.decode` проверяет токен средствами PyJWT и возвращает словарь claims. `token_context.tokens.decode_access_token` — функция нашего приложения: дополнительно проверяет типы и время жизни, возвращает только sub. Формат UUID проверяется позже, в зависимости `/auth/me`.

## Фикстура

| Поле token_context | Значение |
|---|---|
| tokens | Модуль `app.core.tokens` |
| secret | Вымышленный ключ этого теста |
| user_id | UUID пользователя |
| valid_token | Токен, созданный настоящим `create_access_token` |
| claims | Свежий словарь корректных sub/iat/exp для создания тестовых токенов |
| creation_started_at / creation_finished_at | Время до и после создания valid_token |

Используй `claims = token_context.claims.copy()`, когда требуется изменить отдельное поле.

## Три примера операций

Прочитать claims с проверкой ключа и фиксированным разрешённым алгоритмом:

```python
payload = jwt.decode(
    token_context.valid_token,
    token_context.secret,
    algorithms=["HS256"],
    options={"require": ["sub", "iat", "exp"]},
)
```

Создать токен с подготовленными claims:

```python
token = jwt.encode(claims, token_context.secret, algorithm="HS256")
```

Подготовить заведомо истёкший токен с правильной подписью, не используя sleep:

```python
claims = token_context.claims.copy()
claims["iat"] -= 3600
claims["exp"] = claims["iat"] + 1800
expired_token = jwt.encode(claims, token_context.secret, algorithm="HS256")
```

В последнем примере exp остаётся больше iat, но оба времени находятся в прошлом. Меняем только нужное условие; случайно сломанная подпись не должна подменять проверку срока.

## Задание 1 — содержимое выпущенного токена

Добавь `import jwt`. Каркас:

```python
def test_access_token_has_expected_claims(token_context):
    token = token_context.valid_token
    secret = token_context.secret
    expected_subject = str(token_context.user_id)
    expected_algorithm = "HS256"
    expected_lifetime = 1800
    required_claims = {"sub", "iat", "exp"}

    ...
```

Получи payload через `jwt.decode` с проверкой подписи и алгоритма. Проверь наличие обязательных claims, sub, точные типы int у iat/exp, разность exp - iat и попадание iat в границы creation_started_at/creation_finished_at. Через `jwt.get_unverified_header(token)` прочитай alg и сравни с expected_algorithm. Чтение заголовка само по себе не проверяет подпись; оно дополняет проверенный decode.

Наличие claims проверяй как подмножество: контракт требует эти поля, но не запрещает добавлять другие. Для точного целочисленного типа можно использовать `type(value) is int`, поскольку bool в Python является подклассом int.

Задание 1 выполнено в `backend/tests/test_tokens.py`: **1 passed in 0.02s**, Ruff — **All checks passed!** Проверена выдача токена напрямую. Результаты следующих заданий приведены под их описаниями.

## Задание 2 — срок и время выдачи

Добавь `import pytest` и `from jwt.exceptions import InvalidTokenError`.

```python
@pytest.mark.parametrize("time_case", ["expired", "future-issued"])
def test_decode_rejects_invalid_token_times(token_context, time_case):
    claims = token_context.claims.copy()
    secret = token_context.secret
    algorithm = "HS256"

    ...
```

Для expired используй приведённую подготовку прошлого iat/exp. Для future-issued установи iat на 300 секунд позже исходного, exp — ещё на 1800 секунд позже нового iat. Подпиши правильным ключом. Проверь, что именно `token_context.tokens.decode_access_token(token)` выбрасывает `InvalidTokenError` или его наследника через `pytest.raises`.

Задание 2 выполнено для expired и future-issued. На этом этапе `test_tokens.py` дал **3 passed in 0.05s**, Ruff — **All checks passed!** Само задание проверяет декодер приложения; последующие API-проверки описаны после задания 3.

## Задание 3 — ключ, алгоритм и обязательные поля

```python
@pytest.mark.parametrize(
    "invalid_case",
    ["wrong-key", "wrong-algorithm", "missing-sub", "missing-iat", "missing-exp"],
)
def test_decode_rejects_invalid_token_credentials(token_context, invalid_case):
    claims = token_context.claims.copy()
    signing_key = token_context.secret
    algorithm = "HS256"

    ...
```

Для wrong-key поменяй только signing_key. Для wrong-algorithm используй HS384 с тем же ключом. Для missing-* удали только выбранное поле из claims. Остальные параметры должны оставаться корректными. Создай токен через `jwt.encode` и проверь отказ функции нашего приложения через `pytest.raises(InvalidTokenError)`.

Эти задания не требуют PostgreSQL. Обычные синхронные функции tokens не требуют `async def` или маркера asyncio.

Задание 3 выполнено для всех пяти вариантов. `test_tokens.py` дал **8 passed in 0.04s**, Ruff прошёл. Все три учебных задания завершены. Затем известные API-приёмы применены к этим токенам в `test_me_rejects_invalid_jwt_before_user_lookup`; JWT и auth API вместе дали **40 passed in 1.21s**. В T-AUTH-17 также проверены claims и использование токена реального HTTP-входа.

Основание: [API-контракт](../../api.md#текущий-этап-postgresql-и-access-jwt). Справка: [PyJWT Usage Examples](https://pyjwt.readthedocs.io/en/stable/usage.html).
