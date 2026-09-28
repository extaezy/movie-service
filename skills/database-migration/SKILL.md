---
name: database-migration
description: Handle a PostgreSQL schema change using SQLAlchemy and Alembic.
---

For every database schema change:

1. Inspect the current SQLAlchemy models.
2. Inspect existing Alembic migrations.
3. Modify the SQLAlchemy model.
4. Create an Alembic migration.
5. Review the generated migration manually.
6. Check:
   - column types;
   - nullability;
   - defaults;
   - foreign keys;
   - unique constraints;
   - indexes.
7. Ensure upgrade() performs the intended change.
8. Ensure downgrade() reasonably reverses it.
9. Run the migration if the environment allows.
10. Run relevant tests.

Never modify the PostgreSQL schema manually without representing the change in Alembic.

Do not recreate tables unnecessarily.
Do not delete existing data unless the task explicitly requires it.

At completion describe:

- schema before;
- schema after;
- migration created;
- possible compatibility issues.
