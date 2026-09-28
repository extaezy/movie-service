---
name: backend-testing
description: Add or update pytest tests for backend behavior, API endpoints, database logic, or permissions.
---

When testing backend functionality:

1. Identify the behavior that needs protection.

2. Prefer tests for meaningful behavior over tests of implementation details.

3. Consider:

   - successful request;
   - invalid input;
   - missing resource;
   - unauthenticated access;
   - unauthorized access;
   - duplicate operation;
   - important edge cases.

4. For database-dependent functionality:

   - isolate test data;
   - do not rely on test execution order.

5. For API endpoints:
   verify:

   - status code;
   - response structure;
   - relevant database state.

6. Run the smallest relevant test set first.

7. If relevant, run the complete backend test suite afterwards.

Do not add meaningless tests solely to increase coverage.

At completion report:

- tests added;
- scenarios covered;
- tests executed;
- failures, if any.
