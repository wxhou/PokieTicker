## ADDED Requirements

### Requirement: User registration and login

The system SHALL provide user registration with email/password and login with JWT token issuance.

#### Scenario: Successful registration
- **WHEN** user submits email and password (>= 8 chars)
- **THEN** system creates account in `users` table with hashed password (bcrypt)
- **AND** returns JWT token valid for 7 days
- **AND** returns user_id and email

#### Scenario: Duplicate email registration
- **WHEN** user submits email that already exists
- **THEN** system returns 400 error with message "该邮箱已注册"

#### Scenario: Successful login
- **WHEN** user submits correct email and password
- **THEN** system verifies password hash and returns JWT token
- **AND** token contains user_id and email claims

#### Scenario: Failed login
- **WHEN** user submits wrong password
- **THEN** system returns 401 error with message "邮箱或密码错误"

### Requirement: JWT authentication middleware

All protected API routes SHALL validate JWT token and extract user identity.

#### Scenario: Valid token
- **WHEN** request includes `Authorization: Bearer <token>`
- **THEN** middleware extracts user_id and sets it in request context
- **AND** request proceeds to handler

#### Scenario: Missing or invalid token
- **WHEN** request has no token or invalid/expired token
- **THEN** middleware returns 401 error
- **AND** request does NOT proceed

### Requirement: Password security

The system SHALL hash passwords using bcrypt with appropriate cost factor, and never store plaintext passwords.

#### Scenario: Password hashing
- **WHEN** user registers or changes password
- **THEN** system hashes password with bcrypt and stores only the hash
- **AND** plaintext password is never logged or stored
