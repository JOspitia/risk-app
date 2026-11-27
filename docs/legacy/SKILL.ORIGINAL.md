# REST Layered Architecture — Language-Agnostic Skill

## What this is

A specification for building layered REST APIs. The **rules are language-agnostic**: they hold in Java, Python, TypeScript, Go, Rust, Ruby, PHP, C#, Kotlin. A worked reference implementation in Java/Javalin appears in [Reference implementation](#reference-implementation-java--javalin) — treat it as *one* valid instantiation, not as the pattern itself.

The core idea: **each layer has exactly one job, dependencies flow in one direction, and every piece of logic lives in exactly one place.**

---

## Quick start — setting up a new project

Follow in order. The order matters: schema before the code that queries it.

1. **Scaffold the project.** Build tool, dependencies, local database, environment config. See [Project scaffolding](#project-scaffolding).
2. **Decide the folder strategy.** Layer-first is fine to start; know when to [restructure](#scaling-past-20-entities).
3. **Write the migration** with the full security schema ([Data model](#data-model-rules)).
4. **Verify the migration applies clean against an empty database.** Run it. Read the actual error. A migration that has never executed is a migration that does not work.
5. **Implement the 9 layer contracts** ([Layers](#the-9-layers)).
6. **Wire dependency injection.** Resolvable in any order.
7. **For each entity: pass the [decision gate](#decision-gate-which-layers-does-an-entity-need).** Not every entity needs every layer.
8. **Implement the security baseline** ([Security baseline](#security-baseline)).
9. **Write tests** as you go — [Test strategy](#test-strategy), not at the end.
10. **Run the [verification checklist](#verification-checklist) and the [readiness gate](#readiness-gate--is-the-backend-ready-for-a-frontend).**

Do not skip step 4. Every serious defect in [Pitfalls](#pitfalls-learned-the-hard-way) is a migration or a mapping that was never executed.

**Read the tests before writing the feature.** Test strategy tells you what behaviour is required — duplicate handling, soft-delete visibility, immediate revocation. Writing them afterwards means writing what the code happens to do.

---

## Project scaffolding

The scaffolding is what makes the project *runnable*. Without it there is no feedback loop, and an unverified architecture is worth very little.

### Minimum viable stack

| Concern | Purpose | Notes |
|---|---|---|
| Web framework | Routing, JSON, filters | Must support a before/middleware hook for auth |
| Migration tool | Versioned schema | Must support validating against empty DB |
| Connection pool | Reuse DB connections | Size it; exhaustion is a real failure mode |
| Password hashing | bcrypt or argon2id | **Never** hand-rolled |
| JWT library | Sign and verify tokens | Verify signature, expiry, issuer |
| Test runner | Unit + integration | Integration tests must hit a real server |
| Local database | Development | Containerized, disposable |

### Environment configuration

**Secrets come from the environment.** Never from source, never with a real default committed.

| Variable | Required | Default | Notes |
|---|---|---|---|
| `JWT_SECRET` | **yes** | none | HMAC key. **Minimum 32 characters.** Refuse to start if missing or short |
| `JWT_ISSUER` | no | service name | Verify against the `iss` claim |
| `DB_URL` / `DB_HOST` / `DB_NAME` / `DB_USER` / `DB_PASSWORD` | **yes** | none | Connection details |
| `DB_POOL_MAX` | no | 10 | |
| `PORT` | no | 8080 | |

**Fail fast on missing configuration.** A default secret is a vulnerability; a missing secret that crashes at boot is a feature. Validate at startup, before serving traffic.

> **Never commit a real secret, and never ship a usable default.** The only acceptable default for a signing key is "absent", which must abort startup.

### Commands

Know these before writing code — they are the feedback loop.

```
compile       build production sources only   ← misses test bugs
build         compile everything, including tests
test          run the suite
test:watch    re-run on change
run           start the server locally
db:up         start the local database
db:reset      destroy and recreate the database   ← the fastest way to test migrations clean
migrate       apply pending migrations
```

> **Check the compile step you are actually using.** A build command that compiles only production sources will happily report success while your tests do not compile. Prefer the command that builds everything.

### Local database

Run the database in a container so it is disposable and reproducible.

```yaml
# docker-compose.yml — shape, not exact syntax
services:
  db:
    image: postgres:16-alpine
    environment:
      POSTGRES_DB: app_db
      POSTGRES_USER: app_user
      POSTGRES_PASSWORD: local_only_password
      PGTZ: UTC
    ports: ["5432:5432"]
    volumes: [postgres_data:/var/lib/postgresql/data]
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U app_user -d app_db"]
```

**Always pin the timezone.** Without it, timestamp semantics differ between local and production, and every date assertion becomes environment-dependent.

---

## Scaling past 20 entities

Layer-first folders — one folder per layer, all models together — works fine at small scale and then collapses.

### The arithmetic

Each entity produces roughly 8 files (model, request, resource, repository interface, repository implementation, service interface, service implementation, controller). A layer-first layout groups those 8 across 8 different folders.

| Entities | Files | Per folder (layer-first) |
|---|---|---|
| 2 | ~16 | 2 — comfortable |
| 20 | ~160 | 20 — manageable |
| 100 | ~800 | 100 — unmanageable |

To change one field on `User`, you jump across 8 folders. To understand a feature, you open every folder in the project.

### The rule

**Below ~20 entities: layer-first is fine. Do not restructure prematurely.**

Past that, invert the axis — **group by entity, not by layer**:

```
com.example/
├── shared/                    ← cross-cutting; does NOT grow per entity
│   ├── config/                serialization, clocks
│   ├── security/              token service, password hashing, auth filter
│   ├── database/              pool, transaction manager
│   ├── audit/                 audit context and logger
│   ├── response/              API envelope
│   └── exception/             domain error types
│
├── user/                      ← everything about User
│   ├── User.java
│   ├── UserRequest.java
│   ├── UserResource.java
│   ├── IUserRepository.java
│   ├── UserRepository.java
│   ├── IUserService.java
│   ├── UserService.java
│   └── UserController.java
│
├── session/
│   └── ...
└── order/
```

Adding `Order` creates one folder. Changing `User` keeps you in one place.

### What this does not change

**The dependency rule is identical.** Controller → Service → Repository, pointing inward. Feature-first reorganizes where files live; it has no effect on the direction of dependencies. The layer *names* still exist — as file roles inside the entity folder.

### The trade-off, stated honestly

| Approach | Wins | Loses |
|---|---|---|
| **Layer-first** | See all services at once. Familiar. Zero ceremony | Change one entity → jump 8 folders |
| **Feature-first** | One entity, one folder. Scales cleanly | Must know which folder owns a service. Cross-cutting concerns need a home |

Feature-first is the right default for a REST API that grows by entity. Layer-first is better when the team thinks in layers and the codebase stays small.

### Migrating later

Do this **under version control**, as its own commit, after the code is green.

Moving files is only a third of the job:

1. Move the file into the new folder
2. Change its package declaration
3. **Rewrite every import across the codebase** — the expensive step; a single token change reaches dozens of files

Automate step 3 per package rename rather than editing files by hand, then let the compiler find what you missed.

> **Do not restructure a codebase that is not in version control.** A mechanical refactor touching every import with no way to revert is how an afternoon disappears. Commit green first, restructure second.

---

## The one invariant

```
Request → Controller → Service → Repository → Model
                                          ↑
Model → Resource → Response ───────────────┘  (flows back up, not down)
```

**Dependencies point inward only.** A layer may call the layer directly below it and nothing else.

- Controller may call Service. Controller may **not** call Repository.
- Service may call Repository. Service may **not** touch HTTP.
- Repository knows SQL only. It never decides anything.

The single most common violation: a Controller calling the Repository directly to check ownership or existence. That is business logic wearing a controller's clothes. It belongs in a Service.

---

## The 9 layers

```
HTTP Request
    │
    ▼
┌──────────────────────────────────────────────────────────────┐
│  Auth Filter (before)  │ 1. Extrae credencial del header      │
│                       │ 2. Valida firma, expiry, issuer       │
│                       │ 3. Verifica estado en DB (revocación) │
│                       │ 4. Construye AuditContext             │
└───────────────────────────┬───────────────────────────────────┘
                            │
                            ▼
┌─────────────┐
│   Request   │  DTO de entrada. Validación declarativa.
│   (input)   │  Cero lógica de negocio.
└──────┬──────┘
       │
       ▼
┌─────────────┐
│ Controller  │  Orquestación. Decide status HTTP.
│             │  Delega decisiones al Service.
└──────┬──────┘
       │
       ▼
┌─────────────┐
│  Service    │  Lógica de negocio. Transacciones.
│             │  Autorización. Auditoría.
└──────┬──────┘
       │
       ▼
┌─────────────┐
│ Repository  │  Una query por método.
│             │  Mapea filas → Model. No decide.
└──────┬──────┘
       │
       ▼
┌─────────────┐
│   Model     │  Dominio puro. Inmutable.
│  (Entity)   │  Sin conocimiento de HTTP ni DB.
└──────┬──────┘
       │
       ▼
┌─────────────┐
│  Resource   │  DTO de salida. LA FRONTERA DE SEGURIDAD:
│  (output)   │  controla qué campos salen de la API.
└──────┬──────┘
       │
       ▼
┌─────────────┐
│  Response   │  Wrapper HTTP. Sin lógica de negocio.
│  (wrapper)  │
└─────────────┘
```

### Request flow (down)

`Request → Controller → Service → Repository → Model`

### Response flow (up)

`Model → Resource → Response → HTTP`

The Resource sits on the way **back up**. It is the only place where a decision about *what a client may see* belongs.

---

## Layer contracts

### Request (input DTO)

**Does:** receive client data, declarative validation, immutability.
**Does not:** business logic, DB access.
**Rule:** if you need to mutate it after receiving it, it's in the wrong place.

### Controller (orchestration)

**Does:** receive the request, delegate validation, call the Service, map Model → Resource, choose the HTTP status, map domain exceptions to status codes, receive `AuditContext`.
**Does not:** business logic, SQL, ownership checks, data transformation.
**Rule:** if you copy this controller to another project and only the *business* changed, it's in the wrong place.

### Service (business logic)

**Does:** real business rules, normalization, multi-step orchestration, transactions, business validation (duplicate email, ownership, state transitions), audit logging.
**Does not:** HTTP, JSON, raw SQL, Resource construction.
**Rule:** two or more DB calls, or any conditional on a DB result → this belongs in a Service.

> **Never re-wrap a domain exception in a generic error.**
> Domain exceptions should already be unchecked and carry their own HTTP semantics. If you catch and re-wrap them into a generic runtime/error type, your HTTP handler stops recognising them and every business error degrades into a 500. This is a silent, total failure of error mapping.
> **Test:** trigger a domain error, assert the exact status code. If everything returns 500, you re-wrapped it.

### Repository (data access)

**Does:** one SQL statement per method, row → Model mapping, connection handling.
**Does not:** business logic, chaining to other repository methods, branching on query results.
**Rule:** `findAll` / `findById` / `create` / `update` / `delete` — one operation per method.

Two conventions worth adopting:

- **An interface per repository.** Allows mocking in tests without a DB, and enforces dependency inversion.
- **Connection-parameter variants.** Each write method has a variant that receives an open connection so the Service can include it in a transaction. See [Transactions](#transactions).

### Model (domain entity)

**Does:** represent the domain, immutable, no framework annotations if avoidable.
**Does not:** HTTP, JSON, SQL, application logic. **Never serialization concerns.**

### Resource (output DTO) — the security boundary

**Does:** decide which fields leave the API, transform formats (timestamp → ISO-8601 string), decouple API versioning from the domain.
**Does not:** business logic, DB access.
**Rule:** adding a field to the Model must **not** automatically add it to the Resource.

> **Never return a Model directly from a Controller.**
> That deletes the Resource layer's only purpose. Any sensitive field on the Model — password hashes, internal keys, soft-delete flags, audit columns — leaks automatically, silently, and forever after.
> **Test:** inspect an actual HTTP response body. Grep it for every secret your Model carries.

The Resource should expose what the client genuinely needs and hide everything else. Example: a session's public revocation key is exposed; its token hash and internal surrogate key are not.

### Response (HTTP wrapper)

**Does:** wrap every API response, carry the status code for the handler.
**Does not:** business logic, DB access.
**Rule:** the client receives only `success`, `message`, `data`, `errors`, `timestamp`. The HTTP status is also set as a header — carrying it in the body too is redundant and leaks implementation detail.

### Exception layer

**Does:** each domain exception carries HTTP status semantics; a global handler maps them.
**Does not:** rely on generic runtime errors.

Map domain exceptions to status codes explicitly:

| Exception | Status |
|---|---|
| Validation error | 400 |
| Unauthenticated | 401 |
| Forbidden | 403 |
| Not found | 404 |
| Conflict / duplicate | 409 |
| Unexpected | 500 |

---

## Decision gate: which layers does an entity need?

**Not every entity needs all 9 layers.** Assume they do and you will build an empty abstraction — a `Create` request for an entity the client never creates, a Service that contains nothing but a repository passthrough.

Run this gate per entity, from the top:

| Question | If YES | If NO |
|---|---|---|
| 1. Does the **client send fields** to create or modify it? | Build a **Request** DTO | **Skip Request.** Name it `<Entity>Command` if you want clarity |
| 2. Does the **client read** it back? | Build a **Resource** DTO | **Skip Resource** |
| 3. Does it have **business rules** beyond CRUD — state transitions, uniqueness, ownership, limits? | Build a **Service** | A Service with only passthrough methods is dead weight |
| 4. Does it have **security-sensitive fields**? | Build a **Resource** even if the answer to 2 was no | — |
| 5. Is it **server-created only** (sessions, audit entries, jobs)? | Skip Request **and** usually skip Service — the creating layer owns it | — |

### Worked example — why the gate exists

A `Session` model backing JWT revocation:

- Client sends fields to create it? **No** — the server creates it during login. → **No Request.** A `CreateSessionRequest` would have zero fields.
- Client reads it back? **Yes** — to list active devices and revoke one by ID. → **Resource required**, and it **must** hide the token hash.
- Business rules? Ownership check on revoke ("only the owner may revoke"). → **Service required**, because that rule does not belong in the Controller.
- Server-created? **Yes.**

Result: Model + Resource + Service. No Request. Building all 9 "because the checklist said so" leaves you with an empty DTO and an authorization bug in the Controller.

---

## Data model rules

Every user-like entity carries these fields from day one. Retrofitting security onto a live schema is far more expensive than starting with it.

| Field | Purpose |
|---|---|
| `password_hash` | **NOT NULL.** Never plaintext. Every row is a verifiable credential. |
| `is_active` | Account disabled by an administrator. Distinct from deleted. |
| `deleted_at` | Soft delete. Null = alive. The row persists for audit and referential integrity. |
| `locked_until` | Account locked by brute-force protection. Null = not locked. |
| `failed_login_attempts` | Consecutive failed attempts. Reset on successful login. |
| `password_changed_at` | Enables password-expiry policy. |
| `email_verified_at` | Null = unverified. Sensitive actions can require it. |
| `created_at` / `updated_at` / `last_login_at` | Audit metadata. |

### The NOT NULL password invariant

`password_hash NOT NULL` means **every row is a credential**. This is a good invariant — it removes the "account with no password" state entirely.

For high-level creates that have no password (administrator, seed, invitation), generate an **unusable hash** rather than allowing null: hash a cryptographically random value. The account exists, is structurally valid, and is impossible to authenticate against until registration or a password reset sets a real credential.

> Do not add a repository overload that creates the row "without a password". That overload is a footgun: it looks convenient, it produces a NOT NULL violation the moment the schema is correct, and it encourages every caller to invent its own workaround.

---

## Security baseline

### Password hashing

Use **bcrypt** (or argon2id, preferred where available).

| Property | Value |
|---|---|
| Salt | Automatic, per-hash, ~128 bits |
| Cost factor | Tunable. 10 is a reasonable minimum; raise it as hardware improves |
| Rainbow tables | Defeated by per-hash salt |
| Timing attacks | The verify function uses constant-time comparison |

Work factor scales with attacker hardware, not yours. Raise it over time; it is designed to be raised.

> **Never copy a password hash from a fixture, a blog post, or another project.**
> A hash you did not generate verifies against a password you do not know. It fails *silently*: the user is found, the comparison fails, a 401 comes back, and nothing in the logs says "wrong hash".
> **Rule:** generate every seed hash with the real library and verify it with the real verify function before committing. A login smoke test on a seed user is mandatory.

### JWT + revocable sessions

A pure stateless JWT cannot be revoked. If a token leaks, it stays valid until it expires. Combine a signed token with server-side session state.

**Login flow**

```
POST /auth/login { email, password }
  1. Look up user by email
  2. Reject if inactive / deleted / locked      ← state checks, not just password
  3. bcrypt verify(password, hash)             ← constant-time, dummy hash on miss
  4. Generate a unique token ID (JTI), a UUID
  5. Sign the JWT embedding the JTI
  6. Persist the session: jti, user_id, sha256(token), issued_at, expires_at, ip, user_agent
  7. Reset failed_login_attempts, set last_login_at
  8. Return the token
```

**Logout flow**

```
POST /auth/logout
  1. Auth filter populates the JTI
  2. Mark the session revoked (set revoked = true, revoked_at = now)
  3. The token is invalid immediately — no waiting for expiry
```

**Per-request validation**

```
Auth filter, before every handler
  1. Extract the bearer token
  2. Verify signature, expiry, issuer
  3. Look up the session by JTI: active AND not revoked AND not expired
  4. Active   → build an authenticated context with user id and JTI
     Not     → build an anonymous context
  5. Endpoints requiring auth call a guard that raises 401 on an anonymous context
```

The signature proves *authenticity*. The session row proves *still active*. Both together.

**Password-hash storage in sessions:** store `sha256(token)`, never the token itself. If the database leaks, a SHA-256 digest of a short-lived JWT is far less useful than the token.

### Enforce the state checks

The account-state fields do nothing unless login enforces them:

- Inactive, deleted, or locked → reject before verifying the password.
- Failed password → increment `failed_login_attempts`; when it crosses the threshold, set `locked_until`.
- Successful login → reset `failed_login_attempts`, set `last_login_at`.

> **A `can_login()` helper on the model that nothing calls is worse than not having it.** It reads as implemented, passes code review, and leaves the account lockout feature entirely inert. Every state field needs a write path and a read path, or it is decoration.
> **Test:** attempt login on a disabled account and on a locked account. Both must be rejected.

### Timing oracle on unknown users

When the email does not exist, returning immediately skips the password comparison — and the response *time* reveals which emails are registered.

Mitigate by performing a dummy bcrypt verify against a fixed hash when the user is not found, so both paths cost the same.

> Be honest in the code and in the docs about which of these mitigations are actually implemented. Do not document a defence the code does not perform.

---

## Pitfalls learned the hard way

Each of these shipped broken, was invisible, and cost real debugging time. They are in this document because they will recur.

### 1. Never auto-baseline migrations in development

Flyway-style migration tools have a "baseline an existing database" flag. It is for adopting the tool against a live production database. **In development it silently skips your first migration.**

Observed: the tool wrote a baseline marker at version 1 and never ran migration 1. The database kept a 4-column table while the code selected 13. Every security test passed — against a schema that did not match the code at all.

- Development: migrations must apply cleanly to an empty database, every time.
- Never enable auto-baseline outside production adoption.
- **Rule:** if your tests pass but you have never run the migration against an empty database, your tests prove nothing.

### 2. Never edit a migration that has already been applied

Migration tools checksum their files. Editing an applied migration makes validation fail at boot, with an error that points at the migration tool, not at your change.

- Corrections to schema or data go in a **new** migration.
- Exception: a throwaway development database. Wipe it and re-run from scratch — it is faster and cleaner than an incremental correction nobody will ever read.

### 3. Trailing commas before a closing paren are syntax errors

A column definition left with a trailing comma before `)` — leftover from adding fields — fails to parse. It looks correct while reading.

**Rule:** execute every migration against an empty database before you trust it.

### 4. `NOW()` cannot appear in a partial index predicate

Index predicates must be **IMMUTABLE**. Time-dependent functions are `STABLE`, so they are rejected — and even if allowed, an index whose predicate changes with the clock is semantically broken.

```sql
-- REJECTED: functions in index predicate must be marked IMMUTABLE
CREATE INDEX idx_locked ON users (email)
    WHERE locked_until IS NOT NULL AND locked_until > NOW();

-- CORRECT: index the rows; filter on time in the query
CREATE INDEX idx_locked ON users (locked_until)
    WHERE locked_until IS NOT NULL;
```

### 5. SQLState classes are not error types

Integrity constraint violations are a **class**, not a code. `23502` is not-null, `23503` foreign key, `23505` unique, `23514` check. Mapping the whole class to one error message turns every integrity failure into the same lie.

Observed: a NOT NULL violation reported itself as "email already exists" — hiding the actual bug behind a plausible message, and sending debugging in the wrong direction.

**Rule:** dispatch on the **exact** code, and let anything unknown fall through to a generic database error that preserves the original.

### 6. Re-wrapping domain exceptions breaks HTTP mapping

Catching a domain exception and re-throwing it as a generic runtime error destroys its type. Most HTTP frameworks resolve exception handlers by the class of the exception **actually thrown** — so a 409 degrades into a 500.

The Service layer should not wrap exceptions at all: domain exceptions are already unchecked.

### 7. Text block concatenation does not insert whitespace

In several languages, a multi-line string literal used inside a concatenation begins immediately with its first character. A statement ending in `RETURNING` concatenated with a constant starting in `id` produces `RETURNINGid`.

**Rule:** never rely on implicit whitespace when composing SQL from fragments. Be explicit, and verify the composed statement.

### 8. A passing suite may not have compiled

Some build commands compile only production sources. Test sources that fail to compile are simply not built — and the previous run's results are reported as if current.

Observed: a duplicated test method. Every "compile" passed, because none of them compiled the tests.

**Rule:** before trusting a green suite, confirm it actually rebuilt. Clean, then run. If you saw "nothing to compile", you did not run your tests.

### 9. Row mapping must match the schema column-for-column

When a Model gains a field, every projection, every `RETURNING` clause, and every row mapper must change with it. A mismatch surfaces as a runtime failure deep in the mapping layer, far from the edit that caused it.

**Rule:** keep column lists as a single shared constant. Duplicating the projection across queries guarantees they drift.

### 10. Instant serialization needs explicit configuration

Most JSON libraries serialize instants as a decimal epoch number unless told otherwise. `1791569826.341885000` is technically valid and practically wrong for an API.

**Rule:** configure ISO-8601 explicitly and assert it in a test on the actual response body.

---

## Transactions

Without a framework, the Service owns the transaction boundary.

```
execute(block):
    open connection
    disable autocommit
    run block(connection)          ← repository uses this connection, does not open another
    commit
    on error: rollback, rethrow
    finally: close connection
```

Two shapes cover nearly everything:

- `execute(block)` → no return value
- `execute_returning(block)` → returns the block's value (needed for generated IDs)

The repository's connection-parameter variants are what make this work: the Service opens one connection, the block receives it, and the repository participates instead of starting a competing transaction.

**Rule:** never mix an auto-committing write inside a transactional block. One connection, one transaction, one commit.

---

## Dependency injection

Manual `new` stops scaling past a handful of components. A minimal registry is enough:

```
register(key, instance)              # singleton, eager
register_factory(key, supplier)      # lazy: resolved on first access, in any order
resolve(key)                         # builds and caches
```

Lazy factories are what let you register mutually-dependent components in any order without null checks.

Prefer constructor injection throughout. It makes dependencies explicit and keeps the class testable without a framework.

---

## Pagination

**Request:** `(page, size)` with defaults — page 1, size 20, max 100. Clamp rather than reject.

**Response:** the page of data plus the metadata a UI needs to render controls:

```json
{
  "data": [],
  "page": 1,
  "size": 20,
  "total": 47,
  "totalPages": 3,
  "hasNext": true,
  "hasPrevious": false
}
```

Return the metadata. A client that receives only a bare array cannot build pagination controls without a second request.

---

## Audit context

A value object carrying who is making the request, populated by the auth filter before the handler runs and passed down to Services.

**Fields:** user id (null when anonymous), username, session/token ID (the revocation key), action, client IP.

**Rules:**
- Services receive this object and never see the token itself.
- The filter stores it in the request context; handlers read it from there.
- Invalid, expired, or revoked credentials produce an anonymous context — not an immediate 401. Endpoints that require authentication call a guard that raises 401.
- For tests, replace the filter with one that sets the context directly.

Centralized audit logging writes to a **separate channel** from business logs, with independent retention. Audit data and debugging data have different lifecycles and different audiences; routing them together means you cannot keep audit records without keeping debug noise, or drop debug noise without dropping audit records.

---

## Verification checklist

Run this before considering any layer complete. Each item is a thing that has actually broken.

**Schema**
- [ ] Migrations execute cleanly against an **empty** database
- [ ] Migration history shows every version applied, success = true
- [ ] No auto-baselining enabled outside production adoption
- [ ] Applied migrations have never been edited

**Security**
- [ ] Passwords hashed with bcrypt/argon2id, never plaintext
- [ ] Every seed hash **verified** with the library's verify function — login works
- [ ] No HTTP response body contains a password hash or token hash
- [ ] Login rejects inactive, deleted, and locked accounts
- [ ] Failed logins increment the counter; the threshold locks the account
- [ ] Logout invalidates the token immediately
- [ ] A revoked token is rejected on the next request

**Layers**
- [ ] No Controller calls a Repository directly
- [ ] No Service constructs Resources or touches HTTP types
- [ ] Every entity passed the decision gate — no empty DTOs, no passthrough Services
- [ ] Column lists are a single shared constant

**Errors**
- [ ] Each domain exception maps to its intended status code
- [ ] No domain exception is caught and re-wrapped in a generic error
- [ ] Integrity violations dispatch on the exact SQLState code, not the class

**Correctness**
- [ ] Timestamps serialize as ISO-8601 — asserted on the **actual response body**, not just configured
- [ ] A clean build compiles **tests**, not just production sources
- [ ] The suite was re-run from clean and genuinely re-executed

**Test suite** — see [Test strategy](#test-strategy)
- [ ] Every layer has tests, not just the happy path
- [ ] [Readiness gate](#readiness-gate--is-the-backend-ready-for-a-frontend) passed

---

## Test strategy

Tests are not the last step. They are the contract that tells you the backend can be connected to a frontend without surprises.

**Rule: an endpoint is not done until it has a test that fails when the endpoint is wrong.** A test that cannot fail proves nothing.

Organize by attack surface and lifecycle stage, not by class. A frontend integrator asks questions in this order: does it start, does it authenticate, does it do CRUD, does it hold up under load, does it break when someone types badly.

### Layer 1 — Bootstrap

The service must answer before anything else can be tested.

| Check | Assert |
|---|---|
| Health endpoint | 200 |
| Database reachable | Health reports connected |
| Migrations applied | History table lists every version, success |
| Startup with an empty database | No errors — this catches migration defects that never execute |

### Layer 2 — CRUD on the core entity

Full lifecycle against a real running server. Not mocks.

| Case | Assert |
|---|---|
| Create valid | 201, body echoes input, persisted |
| Create duplicate unique field | 409 — not 500 |
| Create missing required field | 400 |
| Create invalid format (bad email) | 400 |
| Read existing | 200, exact data |
| Read non-existent | 404 |
| List | 200, paginated with correct metadata |
| List empty | 200, empty array — not null |
| Update existing | 200, fields changed |
| Update non-existent | 404 |
| Update to a duplicate value | 409 |
| Delete existing | 200, then read returns 404 |
| Delete non-existent | 404 |
| Delete twice | Second returns 404, not an error |
| Full lifecycle in sequence | Create → read → update → delete, state correct at each step |

**Assert the response body, not only the status code.** A 201 with the wrong payload passes a status-only test and breaks the frontend.

### Layer 3 — Authentication

| Case | Assert |
|---|---|
| Login valid credentials | 200, token returned |
| Login unknown email | 401 |
| Login wrong password | 401 |
| Login inactive account | 401 |
| Login locked account | 401 |
| Login unverified email | 401 if verification is required |
| Login without body | 400 |
| Login with empty fields | 400 |
| Response to bad credentials | Identical message for unknown user and wrong password |

### Layer 4 — Session lifecycle

The cases that actually break frontend integrations.

| Case | Assert |
|---|---|
| Authenticated request with valid token | 200 |
| Request without token | 401 on protected routes |
| Request with malformed token | 401 — not 500 |
| Request with tampered signature | 401 |
| **Login twice, both tokens used** | **Both work — multiple devices are normal** |
| Logout, reuse the same token | **401 immediately, without waiting for expiry** |
| Revoke all sessions | All prior tokens 401 |
| List own sessions | Returns only that user's sessions |
| Revoke another user's session | **403/404 — never succeeds** |
| Token after account deletion | 401 |

Two of these deserve emphasis because they are where naive implementations fail:

- **Logout must invalidate immediately.** If the token still works after logout, revocation is not implemented and the whole stateful-session design is theatre.
- **Cross-user session access must be rejected.** Returning another user's sessions is an authorization bug, not a cosmetic one.

### Layer 5 — Injection and injection-adjacent

Run these against a real server with a real database. Mocked repositories cannot catch them — the vulnerability *is* in the query.

| Attack | Input | Assert |
|---|---|---|
| SQLi in a string field | `' OR '1'='1' --` | Treated as literal data; no 500; stored as the literal string |
| SQLi in an email field | `' UNION SELECT ... --` | 400 or stored literally, never executed |
| SQLi for mass deletion | `'; DROP TABLE users; --` | Table still exists afterwards |
| SQLi concurrency burst | Same payload × 20 concurrent | No 500s |
| XSS stored | `<script>alert(1)</script>` in a name | Stored and returned as-is; **the API must not execute it** |
| Unicode / emoji | Emails and names with them | Accepted or cleanly 400 — never 500 |
| Oversized input | 10 MB string | 400/413 — not a memory error |
| Null / wrong type | `"name": null`, `"name": 123` | 400 |
| Unknown fields in body | Extra JSON keys | Behaviour is deliberate and documented |

**Cleanup assertion is mandatory for destructive payloads.** "No 500" is not enough — assert the table survived.

### Layer 6 — Abuse and concurrency

| Case | Assert |
|---|---|
| N users created simultaneously | All succeed; no 500s; no lost writes |
| Concurrent creates, same email | Exactly one 201; the rest 409 |
| 100 sequential creates | No connection exhaustion, no 500s |
| 100 updates to one row | Consistent final state |
| 100 deletes of one row | First succeeds; rest 404 |
| Mixed CRUD, many threads | No 500s anywhere |

These catch transaction bugs and connection-pool exhaustion that single-threaded tests cannot.

### Layer 7 — Serialization contract

Frontend integrators bind to this, so it is tested explicitly.

| Field | Assert |
|---|---|
| Timestamps | ISO-8601 string matching RFC 3339 — **not** a decimal number |
| Timestamps parse in JS | `new Date(value)` yields the correct year |
| Booleans | JSON `true`/`false`, not `0`/`1` or `"true"` |
| Nulls | Explicit `null` where absent — not missing keys, not `"null"` |
| IDs | Numbers stay numbers; large IDs do not lose precision |
| Envelope | Same shape on success and error |
| Error envelope | Contains a machine-readable error identifier, not only prose |

> A decimal epoch for `Instant` is the classic example of a field that passes every status-code test and still breaks the frontend: JavaScript expects milliseconds, the API sends seconds, and the client renders 1970 with no error anywhere. **Assert the format in the response body.**

---

## Readiness gate — is the backend ready for a frontend?

Run this before declaring the API consumable. Every item must be verified against a **running server**, not a mock.

**Endpoints**
- [ ] Health endpoint responds
- [ ] Every route documented with method, path, request shape, response shape
- [ ] Status codes match the table in this skill

**Contract**
- [ ] Timestamps ISO-8601 and verified in a JavaScript `Date`
- [ ] Error responses share one envelope shape
- [ ] Pagination returns metadata, not a bare array
- [ ] Resource DTOs expose no secret fields — inspect a real response body

**Auth**
- [ ] Login returns a token usable immediately
- [ ] Protected routes reject missing, malformed, and tampered tokens
- [ ] Logout invalidates the token immediately
- [ ] Two simultaneous logins both work

**Data**
- [ ] CRUD lifecycle passes end to end
- [ ] Soft-deleted rows are excluded from reads
- [ ] Duplicate unique values return 409

**Resilience**
- [ ] Injection suite passes with no 500s and no destroyed data
- [ ] Concurrency suite passes
- [ ] Locked, inactive, and deleted accounts cannot log in

**Reproducibility**
- [ ] Migrations apply clean to an empty database
- [ ] Seed data logins are verified against the real password verifier

**Gate rule:** if any item fails, the backend is not ready. A frontend built against a half-working API absorbs every gap as its own bug.

---

## Reference implementation (Java / Javalin)

One instantiation of the rules above. Structure and names are conventional; the contracts are what carry over.

### File structure

Shown feature-first, the scalable layout. At small scale the same files sit in layer folders instead — the contracts do not change. See [Scaling past 20 entities](#scaling-past-20-entities).

```
src/main/java/com/example/
├── App.java                            Entry point: routing, DI, exception mapping
│
├── shared/                             Cross-cutting — does not grow per entity
│   ├── config/
│   │   └── JsonConfig.java             Serialization (ISO-8601 dates)
│   ├── security/
│   │   ├── JwtConfig.java              Secret from env, issuer, ttl
│   │   ├── JwtService.java             Sign and verify tokens
│   │   ├── JwtAuthFilter.java          Before-filter: validate + build context
│   │   └── PasswordService.java        Hash, verify, unusable hash
│   ├── database/
│   │   ├── DatabaseConfig.java         Connection pool
│   │   └── TransactionManager.java     Explicit commit / rollback
│   ├── di/
│   │   └── ServiceRegistry.java        Minimal container
│   ├── audit/
│   │   ├── AuditContext.java           Who is calling: id, username, jti, action, ip
│   │   ├── AuditContextFilter.java     Places the context on the request
│   │   └── AuditLogger.java            Centralized audit channel
│   ├── response/
│   │   ├── ApiResponse.java            API envelope (httpStatus @JsonIgnored)
│   │   └── PaginatedResponse.java      Envelope with pagination metadata
│   └── exception/                      Domain errors, one per status class
│
├── user/                               One folder per entity
│   ├── User.java                       Model — domain entity
│   ├── UserRequest.java                Request — input DTO + validation
│   ├── UserResource.java               Resource — output DTO (security boundary)
│   ├── IUserRepository.java            Repository contract
│   ├── UserRepository.java             SQL implementation
│   ├── IUserService.java               Service contract
│   ├── UserService.java                Business logic + transactions
│   └── UserController.java            Orchestration, status codes
│
└── session/
    ├── Session.java
    ├── ISessionRepository.java
    ├── SessionRepository.java
    ├── SessionResource.java            Hides token hash
    └── AuthService.java                Login/logout; session lifecycle
```

The same content in layer-first form, which is perfectly acceptable for a small service:

```
src/main/java/com/example/
├── App.java
├── config/  security/  database/  di/  audit/  response/  exception/
├── model/            User, Session, App
├── request/          UserRequest, LoginRequest, PaginationRequest
├── resource/         UserResource, SessionResource
├── repository/       IUserRepository, UserRepository, ISessionRepository, SessionRepository
├── service/          IUserService, UserService, AuthService
└── controller/       UserController, AuthController
```

### Password service

```java
public class PasswordService {

    private static final int BCRYPT_COST = 10;

    public String hash(String plainPassword) {
        if (plainPassword == null || plainPassword.isBlank()) {
            throw new IllegalArgumentException("Password cannot be null or blank");
        }
        return BCrypt.hashpw(plainPassword, BCrypt.gensalt(BCRYPT_COST));
    }

    public boolean verify(String plain, String hashed) {
        if (plain == null || hashed == null) return false;
        try {
            return BCrypt.checkpw(plain, hashed);
        } catch (Exception e) {
            return false;
        }
    }

    /**
     * Hash inservible: la cuenta existe pero es imposible de autenticar por
     * password. Para altas sin password (admin, seeds, invitaciones).
     * Mantiene password_hash NOT NULL como invariante real.
     */
    public String unusableHash() {
        return BCrypt.hashpw(UUID.randomUUID().toString(), BCrypt.gensalt(BCRYPT_COST));
    }
}
```

### Transaction manager

```java
public <T> T executeReturning(ReturningTransactionBlock<T> block) {
    try (Connection conn = DatabaseConfig.getConnection()) {
        conn.setAutoCommit(false);
        try {
            T result = block.execute(conn);
            conn.commit();
            return result;
        } catch (Exception e) {
            conn.rollback();
            throw e instanceof RuntimeException re ? re : new RuntimeException(e);
        }
    } catch (SQLException e) {
        throw new RuntimeException(e);
    }
}
```

Note the rethrow: a runtime exception is propagated **unchanged**, preserving its type for the HTTP handler. This is the anti-pattern from Pitfall 6.

### Service — no exception re-wrapping

```java
public User create(UserRequest request, AuditContext ctx) {
    String email = request.email().toLowerCase().trim();
    UserRequest normalized = new UserRequest(request.name().trim(), email);

    if (repository.existsByEmail(email)) {
        throw new ConflictException("Email already registered");
    }

    // Sin catch/wrap: las excepciones de dominio son unchecked y el handler
    // global las mapea por su tipo. Envolverlas las degrada a 500.
    Long id = transactionManager.executeReturning(conn ->
            repository.create(conn, normalized, passwordService.unusableHash())
    );

    User created = repository.findById(id)
            .orElseThrow(() -> new NotFoundException("User created but not found"));

    AuditLogger.logCreate(ctx, "User", created.id());
    return created;
}
```

### Repository — precise SQLState dispatch

```java
private RuntimeException handleSqlException(SQLException e) {
    String state = e.getSQLState();
    if (state != null) {
        switch (state) {
            case "23505": return new ConflictException("Email already exists");
            case "23502": return new ValidationException("Required field is missing: " + e.getMessage());
            case "23503": return new ConflictException("Referenced record does not exist");
            case "23514": return new ValidationException("Value violates a constraint: " + e.getMessage());
            default: break;
        }
    }
    return new RuntimeException("Database error (SQLState " + state + ")", e);
}
```

Shared column constant — one source of truth:

```java
private static final String USER_COLUMNS = """
        id, name, email, password_hash, is_active, deleted_at, locked_until,
        failed_login_attempts, password_changed_at, email_verified_at,
        created_at, updated_at, last_login_at
        """;

// Compose SQL with EXPLICIT spacing. Implicit whitespace is not guaranteed.
String sql = """
        UPDATE users
        SET name = ?, email = ?, updated_at = NOW()
        WHERE id = ? AND deleted_at IS NULL
        RETURNING """ + " " + USER_COLUMNS;
```

### Resource — the security boundary

```java
public record SessionResource(
    String jti,          // exposed: the client needs it to revoke
    Long userId,
    Instant issuedAt,
    Instant expiresAt,
    String ipAddress,
    String userAgent,
    boolean revoked,
    Instant revokedAt
) {
    public static SessionResource fromModel(Session session) {
        // tokenHash e id NO se exponen
        return new SessionResource(
            session.jti(), session.userId(), session.issuedAt(), session.expiresAt(),
            session.ipAddress(), session.userAgent(), session.revoked(), session.revokedAt()
        );
    }
}
```

### Controller — orchestrating only

```java
public ApiResponse me(AuditContext ctx) {
    JwtAuthFilter.requireAuth(ctx);
    // Resource, nunca el Model crudo.
    return userRepository.findById(ctx.userId())
            .map(user -> ApiResponse.success("User found", UserResource.fromModel(user)))
            .orElse(ApiResponse.error("User not found", 404));
}
```

### DI wiring

```java
ServiceRegistry registry = new ServiceRegistry();
registry.register(JwtConfig.class, new JwtConfig());
registry.register(JwtService.class, new JwtService(registry.resolve(JwtConfig.class)));
registry.register(PasswordService.class, new PasswordService());
registry.register(TransactionManager.class, new TransactionManager());

registry.registerFactory(IUserRepository.class, UserRepository::new);
registry.registerFactory(ISessionRepository.class, SessionRepository::new);

registry.registerFactory(IUserService.class, () -> new UserService(
        registry.resolve(IUserRepository.class),
        registry.resolve(TransactionManager.class),
        registry.resolve(PasswordService.class)));

registry.registerFactory(UserController.class, () -> new UserController(
        registry.resolve(IUserService.class)));

// Register the before-filter EXACTLY ONCE.
registry.registerFactory(JwtAuthFilter.class, () -> new JwtAuthFilter(
        registry.resolve(JwtService.class),
        registry.resolve(AuthService.class)));

app.before(registry.resolve(JwtAuthFilter.class));   // once, not twice
```

### Migration

```sql
CREATE TABLE users (
    id                    BIGSERIAL PRIMARY KEY,
    name                  VARCHAR(100) NOT NULL,
    email                 VARCHAR(255) NOT NULL UNIQUE,
    password_hash         VARCHAR(255) NOT NULL,
    is_active             BOOLEAN NOT NULL DEFAULT TRUE,
    deleted_at            TIMESTAMP WITH TIME ZONE,
    locked_until          TIMESTAMP WITH TIME ZONE,
    failed_login_attempts SMALLINT NOT NULL DEFAULT 0,
    password_changed_at   TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    email_verified_at     TIMESTAMP WITH TIME ZONE,
    created_at            TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at            TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    last_login_at         TIMESTAMP WITH TIME ZONE
);

CREATE UNIQUE INDEX idx_users_email ON users(email);
CREATE INDEX idx_users_active ON users(email)
    WHERE deleted_at IS NULL AND is_active = TRUE;

-- NO trailing comma on the last column before ')'
-- NO NOW() in a partial index predicate
```

Sessions:

```sql
CREATE TABLE sessions (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    jti         VARCHAR(64) NOT NULL UNIQUE,
    user_id     BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    token_hash  VARCHAR(128) NOT NULL,
    issued_at   TIMESTAMP WITH TIME ZONE NOT NULL,
    expires_at  TIMESTAMP WITH TIME ZONE NOT NULL,
    ip_address  VARCHAR(45),
    user_agent  VARCHAR(512),
    revoked     BOOLEAN NOT NULL DEFAULT FALSE,
    revoked_at  TIMESTAMP WITH TIME ZONE,
    created_at  TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);
```

---

## Language mapping

The contracts are identical; only the vocabulary changes.

Java equivalents for the scaffolding table: Maven/Gradle, Javalin/Spring Boot, Flyway/Liquibase, HikariCP, jBCrypt/bcrypt, JJWT, TestNG/JUnit, Docker Compose.

| Layer | Python | TypeScript | Go | Rust | Ruby | PHP | C# / .NET |
|---|---|---|---|---|---|---|---|
| Request | Pydantic model | class + class-validator | struct + validator | serde struct | `ActiveModel` | Form Request | record + DataAnnotations |
| Controller | FastAPI route | Express handler | `http.Handler` | axum extractor | Rails controller | Laravel controller | ASP.NET controller |
| Service | class | class service | struct | struct + trait | `PORO` service | Service class | service class |
| Repository | DAO / raw SQL | class repository | repository struct | `sqlx` repository | ActiveRecord model | Eloquent model | DbContext / repository |
| Model | dataclass / Pydantic | interface + type | struct | struct | PORO | Eloquent model | entity class |
| Resource | Pydantic (diff of model) | DTO / interface | response struct | response struct | serializer | API Resource | DTO record |
| Response | response model | generic response | response struct | `ApiResponse<T>` | `render json` | `ApiResponse` | `ApiResponse<T>` |
| Exceptions | custom exceptions | custom Error classes | error types | `thiserror` | custom errors | exceptions | custom exceptions |
| Transactions | context manager | unit of work | `db.Begin` / Tx | transaction closure | `transaction` block | `DB::transaction` | `BeginTransaction` |
| DI container | manual / punq | InversifyJS | fx / wire | `async fn` wiring / `once_cell` | manual | Laravel container | built-in DI |
| Migrations | Alembic | Prisma / Drizzle | goose / Atlas | sqlx / refinery | ActiveRecord migrations | Laravel migrations | EF Core migrations |
| Migrations: adopt existing DB | `alembic stamp` | `prisma migrate resolve` | `goose -b` | sqlx `--baseline` | `db:migrate` | `migrate --step` | `migrations add` |
| JWT | PyJWT | jsonwebtoken | golang-jwt | jsonwebtoken | jwt | firebase/php-jwt | `Microsoft.AspNetCore.Authentication.JwtBearer` |
| Password hash | bcrypt | bcrypt | bcrypt (x/crypto) | argon2 / bcrypt | bcrypt | password_hash | `Microsoft.AspNetCore.Identity` |
| Audit context | middleware | Express middleware | `context.Context` | extractor + extensions | `CurrentUser` concern | middleware | scoped service / `HttpContext` |
| Pagination | Paginator | pagination DTO | pagination params | pagination struct | Kaminari | `LengthAwarePaginator` | `PagedResult<T>` |

**Mapping the pitfall about adopting an existing database:** every migration tool has a "stamp"/"baseline" command. Same rule applies — never use it in development; migrations must run clean against an empty database.

---

## Adding a new entity

1. Write the migration. Add security fields from day one.
2. **Run it against an empty database.** Confirm.
3. Model — immutable, no serialization concerns.
4. Pagination request — reuse the shared one, do not create a new one.
5. **Decision gate.** Create only what the answers require.
6. Repository interface, then implementation. Connection variants for writes.
7. Service interface, then implementation. Transaction boundary here.
8. Controller. Orchestration only.
9. Resource, if the client reads it back.
10. Wire into the DI container.
11. Register routes.
12. Write the [test strategy](#test-strategy) coverage for this entity: CRUD lifecycle at minimum.
13. **Run the verification checklist and the [readiness gate](#readiness-gate--is-the-backend-ready-for-a-frontend).**