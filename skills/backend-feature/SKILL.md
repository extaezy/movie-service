---
name: backend-feature
description: Implement a backend feature that may affect FastAPI endpoints, business logic, models, schemas, or tests.
---

When implementing a backend feature:

1. Inspect the existing related code first:

   - routers;
   - schemas;
   - models;
   - services;
   - database queries;
   - tests.

2. Determine the smallest change required.

3. Determine whether the database schema must change.

4. If the schema changes:

   - update the SQLAlchemy model;
   - create an Alembic migration.

5. Add or update Pydantic schemas when necessary.

6. Implement the business logic.

7. Add or update the FastAPI endpoint.

8. Check authentication and authorization requirements.

9. Handle expected errors explicitly.

10. Add relevant pytest tests.

11. Run the relevant tests.

At completion report:

- files changed;
- API changes;
- database changes;
- tests performed;
- suggested Git commit message.

Do not introduce unnecessary architectural layers.
