# Secure Pitch Booking

A small multi-service web application where players book football pitches in
Brașov. It was built to study authorization across service boundaries, a secure development lifecycle and how composing services can create vulnerabilities that no single service has on its own.

> **Warning: this repository contains intentional vulnerabilities.**
> Four vulnerabilities are planted for educational purposes. They are
> **off by default** and only switch on when `VULNERABLE_MODE=1`. Do not deploy
> this application, and never run it with `docker-compose.vulnerable.yml`
> outside a local demo. See [docs/known-vulnerabilities.md](docs/known-vulnerabilities.md).

---

## Contents

1. [What the application does](#what-the-application-does)
2. [Architecture](#architecture)
3. [Repository layout](#repository-layout)
4. [Requirements](#requirements)
5. [Build and run](#build-and-run)
6. [Try it by hand](#try-it-by-hand)
7. [Run the tests](#run-the-tests)
8. [Vulnerable mode](#vulnerable-mode)
9. [CI/CD pipeline (Jenkins)](#cicd-pipeline-jenkins)
10. [Security design in short](#security-design-in-short)
11. [Documentation](#documentation)

---

## What the application does

| Role | Can do |
|---|---|
| **player** | List pitches, book a free hour, see and cancel only their own bookings, request and download their own weekly schedule |
| **admin** | Platform administrator: add and remove pitches, see all bookings, cancel any booking. Cannot create bookings or read players' schedules |

Seeded accounts (synthetic data, local use only):

| Username | Role | Password |
|---|---|---|
| `darius` | player | `darius-test-password` |
| `andreea` | player | `andreea-test-password` |
| `admin` | admin | `admin-test-password` |

Operations exposed by the public API:

| Method and path | Who | What |
|---|---|---|
| `POST /login` | anyone | Returns a signed access token |
| `GET /pitches`, `GET /pitches/{id}` | player, admin | List or view pitches |
| `POST /pitches`, `DELETE /pitches/{id}` | admin | Add or remove a pitch |
| `POST /bookings` | player | Book a pitch for one hour (10:00 to 22:00) |
| `GET /bookings[?status=active\|cancelled]` | player, admin | Players see their own bookings, the admin sees all |
| `POST /bookings/{id}/cancel` | owner, admin | Cancel a booking |
| `POST /schedules` | player | Generate a weekly schedule (goes through all three services) |
| `GET /schedules/{id}` | owner | Download a generated schedule |

---

## Architecture

```
                 ┌──────────────────────── internal network (no internet) ───────────────────────┐
                 │                                                                                │
 client ──HTTP──▶│  api :8000  ──access token──▶  booking-service :8001  ◀── SQLite (bookings)   │
 127.0.0.1:8000  │   │  users DB, signs tokens         ▲                                          │
                 │   │                                 │ job token                                │
                 │   └──job token──▶  schedule-service :8002  ── uses pitchgrid (packages/*.whl) │
                 └────────────────────────────────────────────────────────────────────────────────┘
```

| Component | Responsibility |
|---|---|
| `api` | The only public entry point. Checks passwords (Argon2), issues EdDSA-signed access tokens, verifies tokens and forwards requests. Mints short-lived **job tokens** for schedule generation. Holds the only signing key. |
| `booking-service` | Owns pitches, bookings and schedules. Verifies every token itself and makes every authorization decision (role, ownership, job scope). |
| `schedule-service` | Builds a weekly schedule with the third-party `pitchgrid` package. Has no database and no signing key; it only holds the verification key and the job token it was given. |
| `pitchgrid` | Small "supplier" library, installed from a wheel whose SHA-256 digest is pinned by the consumer. |

Only `api` is published, and only on `127.0.0.1`. The other services live on an
internal Docker network without internet access. All containers run as non-root
users with a read-only root filesystem, `cap_drop: ALL` and `no-new-privileges`.

---

## Repository layout

```
api/                      Public gateway: login, tokens, forwarding
booking-service/          Data owner and authorization decisions
schedule-service/         Weekly schedule job (uses pitchgrid)
supplier/pitchgrid/       Source of the third-party package
packages/                 Built pitchgrid wheel used by schedule-service
tests/                    Black-box and internal security tests
tests/vulnerabilities/    Demonstration tests for the planted vulnerabilities
scripts/                  Key generation and the dependency gate
ci/                       Image with the analysis tools used by the pipeline
security/                 Accepted dependency findings (currently none)
jenkins/                  Local Jenkins with the Docker CLI
docs/plan.md              Lifecycle plan: scope, assets, trust boundaries, STRIDE, phase plan
docs/known-vulnerabilities.md   Inventory of the planted vulnerabilities
docs/evidence/            Screenshots from Jenkins builds
docker-compose.yml        The application and the test runner
docker-compose.ci.yml     Overrides used only by Jenkins
docker-compose.vulnerable.yml   Switches the planted vulnerabilities ON (demo only)
Jenkinsfile               The CI/CD pipeline
```

---

## Requirements

- Docker Desktop with Docker Compose v2 (tested on a MacBook Pro M1, macOS)
- Git
- No local Python is needed: every tool runs in a container

All commands below are run from the repository root unless stated otherwise.

---

## Build and run

**1. Clone the repository**

```bash
git clone https://github.com/dariusmuresan01/secure-pitch-booking.git
cd secure-pitch-booking
```

**2. Generate the signing keys** (once). Keys are never committed; `keys/` is in `.gitignore`.

```bash
docker build -f ci/Dockerfile -t spb-ci-tools .
sh ci/run-tool.sh python scripts/generate_keys.py
chmod 644 keys/*.pem
```

The services run as non-root users, so they need read access to the mounted key files.

**3. Build and start the application**

```bash
docker compose up -d --build
```

Docker waits until `booking-service` and `schedule-service` are healthy before
starting `api`. Check that everything runs:

```bash
docker compose ps
curl http://127.0.0.1:8000/health
```

**4. Stop it**

```bash
docker compose down
```

Databases live in `tmpfs`, so every start begins from the seeded data.

---

## Try it by hand

The interactive API documentation is at <http://127.0.0.1:8000/docs>.

From the terminal:

```bash
# Log in as darius and keep the token in a variable
TOKEN=$(curl -s -X POST http://127.0.0.1:8000/login \
  -H "Content-Type: application/json" \
  -d '{"username": "darius", "password": "darius-test-password"}' \
  | python3 -c "import sys, json; print(json.load(sys.stdin)['access_token'])")

# List pitches
curl -s http://127.0.0.1:8000/pitches -H "Authorization: Bearer $TOKEN"

# Book pitch 2 on a future date at 18:00
curl -s -X POST http://127.0.0.1:8000/bookings -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"pitch_id": 2, "date": "2030-06-03", "start_hour": 18}'

# Request and download the schedule for that week (week_start must be a Monday)
curl -s -X POST http://127.0.0.1:8000/schedules -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" -d '{"week_start": "2030-06-03"}'
curl -s http://127.0.0.1:8000/schedules/1 -H "Authorization: Bearer $TOKEN"
```

Use the `schedule_id` returned by `POST /schedules` in the last command.

---

## Run the tests

The tests run in their own container on the internal network, so they can also
reach `booking-service` and `schedule-service` directly and play the role of an
attacker inside the network.

```bash
docker compose up -d --build
docker compose --profile test run --rm --build tests
docker compose down
```

Expected result in the default (secure) mode: **60 passed**.

| File | What it checks |
|---|---|
| `tests/test_auth.py` | Login, generic error messages, missing and tampered tokens |
| `tests/test_authorization.py` | The access control matrix: roles, ownership, input validation |
| `tests/test_schedules.py` | Schedule generation end to end, and who may request or download a schedule |
| `tests/internal/test_job_tokens.py` | Job token scope, forged and expired tokens, token confusion, no trust in the internal network |
| `tests/vulnerabilities/` | One demonstration test per planted vulnerability (see below) |

---

## Vulnerable mode

The four planted vulnerabilities are controlled by a single environment
variable. Only the exact value `1` turns them on; anything else, including a
missing variable, keeps the secure behaviour (fail-safe default).

| Id | Weakness | Where |
|---|---|---|
| V1 | CWE-862 Missing Authorization | `GET /schedules/{id}` |
| V2 | CWE-89 SQL Injection | `GET /bookings?status=` |
| V3 | CWE-20 Improper Input Validation | `POST /bookings` (date) |
| V4 | Composition vulnerability | `api` → `schedule-service` → `booking-service` (operation 5) |

Run the application and the tests in vulnerable mode:

```bash
docker compose -f docker-compose.yml -f docker-compose.vulnerable.yml up -d --build
docker compose -f docker-compose.yml -f docker-compose.vulnerable.yml --profile test run --rm --build tests
docker compose down
```

Expected result: **4 failed, 56 passed**. The four failures are security tests
written from the plan before the vulnerabilities existed, catching them:

- `test_other_player_cannot_download_schedule` (V1)
- `test_admin_cannot_download_player_schedule` (V1)
- `test_schedule_contains_only_own_active_bookings_of_that_week` (V4)
- `test_job_token_reads_only_its_player_and_week` (V4)

All five tests in `tests/vulnerabilities/` pass in both modes, because each one
checks the behaviour that mode should have: the attack fails in secure mode and
succeeds in vulnerable mode. To run only those:

```bash
docker compose -f docker-compose.yml -f docker-compose.vulnerable.yml up -d --build
docker compose -f docker-compose.yml -f docker-compose.vulnerable.yml --profile test run --rm --build tests \
  pytest -v -p no:cacheprovider vulnerabilities
docker compose down
```

Details, locations and what detected each one:
[docs/known-vulnerabilities.md](docs/known-vulnerabilities.md).

---

## CI/CD pipeline (Jenkins)

### Start Jenkins locally

Jenkins runs in its own container and uses the host's Docker through the
socket, so the pipeline can build images and start the application.

```bash
mkdir -p ~/jenkins-home
cd jenkins
docker compose up -d --build
cd ..
```

Open <http://localhost:8080>. The first-time admin password is in:

```bash
cat ~/jenkins-home/secrets/initialAdminPassword
```

Install the suggested plugins and create an admin user.

### Create the pipeline job

1. **New Item** → name `secure-pitch-booking` → **Pipeline**.
2. Under **Pipeline**, choose **Pipeline script from SCM**.
3. SCM: **Git**, repository URL `https://github.com/dariusmuresan01/secure-pitch-booking.git`, branch `*/main`.
4. Script path: `Jenkinsfile`. Save.
5. Click **Build Now**. Afterwards Jenkins polls the repository every 5 minutes.

### Stages

| Stage | What it does | Fails the build when |
|---|---|---|
| Prepare | Builds the tools image and generates fresh keys for this build | |
| 1. Validate dependencies | `scripts/verify_dependencies.py`: every dependency is pinned with a SHA-256 hash, and the `pitchgrid` wheel matches its approved digest | A dependency is unpinned or unhashed, or the wheel was changed |
| 2. Build images | Builds all images with `pip install --require-hashes` | A download does not match its hash |
| 3. Static analysis | Bandit (full JSON report) and Gitleaks | Bandit finds a high-severity issue, or Gitleaks finds a secret |
| 4. Dependency analysis | pip-audit on every requirements file, minus accepted entries in `security/audit-exceptions.txt` | A known vulnerability is not accepted |
| 5. Test environment | Starts the application with the CI override | A service does not become healthy |
| 6. Tests | Full test suite in secure mode, JUnit report | Any test fails |
| 7. Audit log checks | Saves service logs; checks no token appears and denied requests are logged | A token leaks into the logs, or 403s are not logged |
| 8. Vulnerability demonstration | Restarts the application in vulnerable mode and runs `tests/vulnerabilities/` | A planted vulnerability can no longer be demonstrated |

Every build archives `reports/` as artifacts: `dependencies.txt`, `bandit.json`,
`gitleaks.json`, `pip-audit-*.json`, `junit.xml`, `service-logs.txt` and
`junit-vulnerable.xml`. Screenshots of builds #1 and #5 are in
[docs/evidence/](docs/evidence/).

### Stop Jenkins

```bash
cd jenkins
docker compose down
cd ..
```

---

## Security design in short

The three principles applied throughout, with where they are enforced:

| Principle | How |
|---|---|
| **Least privilege** | Only `api` holds the signing key; the other services only verify. `schedule-service` has no database and gets a job token limited to one player, one week, two scopes and two minutes. Containers run as non-root with no capabilities and read-only filesystems. Each service mounts only the key it needs. The admin cannot book or read players' schedules. |
| **Complete mediation** | `booking-service` verifies the token and checks role and ownership on every request, even when it comes from `api` on the internal network. Access tokens and job tokens are separated by `token_use` and audience, so one cannot be used as the other. |
| **Fail-safe defaults** | Missing, expired or invalid tokens are rejected (401), and actions are allowed only for the roles listed in the access control matrix. Inputs are validated by type and range, and unknown values are rejected. The planted vulnerabilities are off unless `VULNERABLE_MODE` is exactly `1`. |

Supply chain: every dependency is pinned with hashes, the `pitchgrid` wheel is
approved by digest in the consumer's requirements, and the build fails on any
mismatch.

---

## Documentation

- [docs/plan.md](docs/plan.md): lifecycle plan written before the code (scope,
  assets, trust boundaries and data flow, access control matrix, STRIDE, phase
  plan with gates)
- [docs/known-vulnerabilities.md](docs/known-vulnerabilities.md): the four planted vulnerabilities
- [docs/evidence/](docs/evidence/): Jenkins build screenshots