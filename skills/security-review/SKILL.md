---
name: security-review
description: Review backend authentication, authorization, user-owned data, secrets, and privacy controls.
---

Review only security relevant to this application.

Check:

1. Authentication

   - protected endpoints require authentication;
   - passwords are never stored in plaintext;
   - authentication tokens are handled correctly.

2. Authorization

   - users cannot modify another user's resources;
   - users cannot delete another user's content;
   - user_id supplied by the client is not blindly trusted.

3. Private profiles

   - private data cannot be accessed by directly calling the API;
   - friendship/privacy checks happen on the backend.

4. Input handling

   - Pydantic validation is used;
   - invalid identifiers are handled safely.

5. Secrets

   - no API keys in source code;
   - no passwords in source code;
   - secrets come from environment variables.

6. Database

   - use SQLAlchemy safely;
   - avoid manually constructed SQL from untrusted input.

Report concrete findings.

Do not propose enterprise security infrastructure unless it is necessary for this project.
