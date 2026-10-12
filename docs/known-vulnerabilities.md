# Known vulnerabilities

This application contains four vulnerabilities planted on purpose for
educational purposes. They are **off by default**: every

Do not deploy this application with `VULNERABLE_MODE=1`.

## How to switch them on

    docker compose -f docker-compose.yml -f docker-compose.vulnerable.yml up -d --build
    docker compose -f docker-compose.yml -f docker-compose.vulnerable.yml --profile test run --rm --build tests

Each test in `tests/vulnerabilities/` checks both modes: the attack fails in
secure mode and succeeds in vulnerable mode. Jenkins stage 6 runs the full
suite in secure mode, and stage 8 runs the demonstration tests in vulnerable mode.

## Inventory

| Id | Weakness | Where | Threat | What an attacker gets | Demonstration test |
|----|----------|-------|--------|-----------------------|--------------------|
| V1 | CWE-862 Missing Authorization | `booking-service/main.py`, `get_schedule` | T10 | Any logged-in user reads any player's schedule by its id | `test_v1_missing_authorization.py` |
| V2 | CWE-89 SQL Injection | `booking-service/main.py`, `get_bookings` (status filter) | T6 | A player reads every player's bookings | `test_v2_sql_injection.py` |
| V3 | CWE-20 Improper Input Validation | `booking-service/main.py`, `create_booking` (date) | T5, T7 | A player stores fabricated bookings in the past | `test_v3_input_validation.py` |
| V4 | Composition vulnerability | `booking-service` `/jobs/bookings` + `schedule-service` `/jobs` | T11 | A player's own schedule contains other players' bookings | `test_v4_composition.py` |

## What detected them

| Id | Bandit (stage 3) | Security tests from the plan (stage 6) |
|----|------------------|-----------------------------------------|
| V1 | Not detected | `test_other_player_cannot_download_schedule`, `test_admin_cannot_download_player_schedule` |
| V2 | Not detected (query built in pieces, so rule B608 does not match) | `test_v2_*` only; no earlier test used the status filter |
| V3 | Not detected | `test_v3_*` only; the rule did not exist before |
| V4 | Not detected (the code of each service is correct on its own) | `test_schedule_contains_only_own_active_bookings_of_that_week`, `test_job_token_reads_only_its_player_and_week` |