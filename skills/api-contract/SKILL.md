---
name: api-contract
description: Define or change a REST API contract shared between the backend and frontend.
---

When adding or changing an API endpoint:

1. Inspect existing route naming conventions.

2. Preserve existing API contracts unless a change is required.

3. Define:

   - HTTP method;
   - URL;
   - authentication requirement;
   - path parameters;
   - query parameters;
   - request body;
   - response body;
   - HTTP status codes;
   - expected errors.

4. Use Pydantic schemas for request and response models where appropriate.

5. Do not expose internal database objects unnecessarily.

6. If an existing API response changes incompatibly, explicitly report:

BREAKING API CHANGE

7. After implementation provide a frontend-oriented contract such as:

POST /api/v1/example

Request:
{
...
}

Response:
{
...
}

Errors:
400 - ...
401 - ...
404 - ...
