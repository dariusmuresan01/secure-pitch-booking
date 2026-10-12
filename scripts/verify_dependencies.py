"""Gate check: every dependency is pinned with a hash, and every package in
packages/ is approved by digest in the consumer's requirements file.

Exit code 0 means the check passed, 1 means the build must stop.
"""

import hashlib
import sys
from pathlib import Path

REQUIREMENT_FILES = [
    "api/requirements.txt",
    "booking-service/requirements.txt",
    "schedule-service/requirements.txt",
    "tests/requirements.txt",
]
PACKAGE_DIR = Path("packages")
CONSUMER_FILE = Path("schedule-service/requirements.txt")


def logical_lines(path: Path) -> list[str]:
    """Join lines ending in a backslash and drop comments."""
    lines, current = [], ""
    for raw in path.read_text().splitlines():
        line = raw.split("#", 1)[0].rstrip()
        if line.endswith("\\"):
            current += line[:-1] + " "
            continue
        current += line
        if current.strip():
            lines.append(current.strip())
        current = ""
    return lines


def check_pins(path: Path) -> list[str]:
    problems = []
    for line in logical_lines(path):
        if line.startswith("--"):
            continue
        name = line.split()[0]
        if "==" not in name:
            problems.append(f"{path}: '{name}' is not pinned to an exact version")
        if "--hash=sha256:" not in line:
            problems.append(f"{path}: '{name}' has no sha256 hash")
    return problems


def check_packages() -> list[str]:
    problems = []
    approved = CONSUMER_FILE.read_text()
    for wheel in sorted(PACKAGE_DIR.glob("*.whl")):
        digest = hashlib.sha256(wheel.read_bytes()).hexdigest()
        if f"--hash=sha256:{digest}" not in approved:
            problems.append(f"{wheel}: digest {digest} is not approved in {CONSUMER_FILE}")
        else:
            print(f"ok  {wheel.name}  sha256:{digest}")
    return problems


def main() -> int:
    problems = []
    for name in REQUIREMENT_FILES:
        path = Path(name)
        if not path.exists():
            problems.append(f"{path}: missing")
            continue
        found = check_pins(path)
        problems += found
        if not found:
            print(f"ok  {path}: every dependency pinned with a hash")
    problems += check_packages()
    for problem in problems:
        print(f"FAIL  {problem}")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())