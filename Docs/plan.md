# Lifecycle plan

This plan is written before any feature is implemented. It is extended section by section; each section is committed before the work it describes begins.

## 1. Scope

### Purpose

A small system where players book football pitches in Brașov and view their own bookings. The admin is the pitch owner: they publish their pitches and see every booking made on them. The system is split into three services so that authorization can be studied across service boundaries.

### Roles

| Role | Type | What it can do |
|---|---|---|
| player | ordinary | List pitches, create a booking, see and cancel only their own bookings, request and download their own weekly schedule |
| admin | privileged | The pitch owner. Publishes and removes pitches, sees all bookings, cancels any booking. Does not create bookings. |

Seeded accounts (synthetic data, no registration):

- `andrei` (player)
- `maria` (player)
- `admin` (admin, the pitch owner)

One admin is seeded, so "all bookings" and "bookings on the admin's pitches" are the same set. Two players are needed so that tests can show one player cannot reach the other player's bookings or schedules.

### Entities

| Entity | Fields | Owner |
|---|---|---|
| Pitch | id, name, address, price_per_hour | the admin who published it |
| Booking | id, pitch_id, user_id, date, start_hour, status | the player who created it |

Generated result (not a main entity): **Schedule**: id, owner_id, week, content, created_at. It is owned by the player who requested it.

### Components

Each component runs as a separate process in its own container. They communicate over HTTP with JSON.

| Component | Responsibility | Security responsibility |
|---|---|---|
| Application API (`api`) | The only entry point for users. Handles login and forwards requests to the other services. | Establishes who the user is and what role they have. Rejects unauthenticated requests. |
| Booking service (`booking-service`) | Stores pitches, bookings and schedules. | Checks permission on every resource and action, including requests coming from the other services. |
| Schedule service (`schedule-service`) | Builds a weekly schedule from a player's bookings using the helper package. | Works only on the data needed for the one job it was given. |

Data store: one SQLite database, opened only by the Booking service. The other two components never touch it directly.

```mermaid
flowchart LR
    U[User CLI] -->|HTTP| A[Application API]
    A -->|HTTP| B[Booking service]
    A -->|start schedule job| S[Schedule service]
    S -->|read bookings and save schedule| B
    P[pitchgrid package] -.->|installed into| S
```

### Helper package (external dependency)

`pitchgrid`: takes a list of bookings and returns a weekly timetable as formatted text. It lives in its own directory, is built as an installable package, and is declared as a dependency of the Schedule service. Its code is not copied into any component.

### Operations

| # | Operation | Who | Path |
|---|---|---|---|
| 1 | Log in and receive a token | player, admin | User → API |
| 2 | List pitches | player, admin | User → API → Booking service |
| 3 | Create a booking (rejected if the slot is taken) | player | User → API → Booking service |
| 4 | List or cancel own bookings | player | User → API → Booking service |
| 5 | Request weekly schedule, then download it | player | User → API → Schedule service → Booking service → `pitchgrid` → Booking service → API → User |
| 6 | Publish or remove a pitch | admin | User → API → Booking service |
| 7 | List all bookings, cancel any booking | admin | User → API → Booking service |

Operation 5 involves all three components and the helper package.

### User interface

A command-line client or an API test collection. No graphical interface.

### Out of scope

Account registration, web or mobile interface, real payments, email, public hosting, high availability, performance at scale.

## 2. Asset register

An asset is anything in the system that is worth protecting. Each asset is rated on three needs:

- **C (confidentiality):** only the right people can read it
- **I (integrity):** only the right people can change it
- **A (availability):** it is there when needed

Ratings: H = high, M = medium, L = low.

| ID | Asset | Where it lives | Owner | C | I | A | Why it matters |
|---|---|---|---|---|---|---|---|
| A1 | User credentials (password hashes) | API, seeded user store | each user | H | H | M | Whoever has them can log in as that user |
| A2 | User access tokens | Issued by API, sent with every request | each user | H | H | L | A stolen or forged token gives the user's authority until it expires |
| A3 | Signing keys and service secrets | Configuration of each service | system | H | H | M | Whoever has them can create valid tokens for any user or service |
| A4 | Bookings | Booking service database | the player who created it | M | H | M | Show who plays where and when; must not be changed or cancelled by others |
| A5 | Pitches | Booking service database | admin | L | H | M | Visible to all users, but only the admin may change them |
| A6 | Schedules (generated results) | Booking service database | the player who requested it | M | H | L | Contain a player's bookings; must reach only that player |
| A7 | Job authority (what the Schedule service is allowed to read for one job) | Passed from API to Schedule service to Booking service | the player who started the job | H | H | L | If it is too broad, the Schedule service can read other players' data |
| A8 | Helper package `pitchgrid` and its approval manifest | Package directory; manifest in the Schedule service build | system | L | H | M | A modified package runs with the Schedule service's permissions |
| A9 | Source code, Jenkinsfile, container images | Git repository, build environment | system | L | H | M | Changes here change what every service does |
| A10 | Logs, test and analysis results | Service output, Jenkins artifacts | system | M | H | L | Evidence for gate decisions; must not contain secrets or tokens |

## Sections to be added

3. Trust boundaries and data flow
4. Access control matrix
5. STRIDE analysis
6. Phase plan: requirements, implementation and build, testing, release (asset → threat → control → activity → evidence → gate)