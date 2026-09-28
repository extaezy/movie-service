---
name: external-data-import
description: Import or synchronize movie and review data from an external API into PostgreSQL.
---

When implementing an external API import:

1. Inspect the external API data structure.
2. Separate external identifiers from internal database identifiers.
3. Validate incoming data.
4. Normalize it into the application's models.

Handle:

- missing values;
- unexpected values;
- duplicate records;
- existing movies;
- network timeouts;
- HTTP errors;
- API rate limits where applicable.

Use HTTPX for HTTP requests unless the project already uses another client.

Do not duplicate a movie on repeated imports.

Prefer an idempotent import where practical:
running the same import twice should not create duplicate records.

Keep the solution simple.

Do not introduce queues, Redis or distributed processing unless specifically required.

At completion report:

- source API;
- imported fields;
- deduplication strategy;
- error handling;
- database changes.
