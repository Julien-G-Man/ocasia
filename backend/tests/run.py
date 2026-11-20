"""Run Django tests for selected apps.

Examples:
    python tests/run.py --list
    python tests/run.py tutor chatbot
    python tests/run.py --all
"""

import argparse
import sys
from pathlib import Path


BACKEND_DIR = Path(__file__).resolve().parents[1]
APPS_DIR = BACKEND_DIR / "apps"


def discover_test_apps() -> list[str]:
    apps = []
    for app_dir in sorted(APPS_DIR.iterdir()):
        if not app_dir.is_dir() or app_dir.name.startswith("_"):
            continue
        has_tests_file = (app_dir / "tests.py").is_file()
        test_dir = app_dir / "tests"
        has_test_modules = test_dir.is_dir() and any(
            file.is_file() and file.name.startswith("test") and file.suffix == ".py"
            for file in test_dir.rglob("*.py")
        )
        if has_tests_file or has_test_modules:
            apps.append(app_dir.name)
    return apps


def main() -> int:
    parser = argparse.ArgumentParser(description="Run tests for selected Django apps.")
    parser.add_argument("apps", nargs="*", help="App names, e.g. tutor chatbot")
    parser.add_argument("--all", action="store_true", help="Run every app that contains tests")
    parser.add_argument("--list", action="store_true", help="List apps that contain tests")
    parser.add_argument("--keepdb", action="store_true", help="Reuse Django's test database")
    parser.add_argument("--verbosity", type=int, choices=range(0, 4), default=1)
    args = parser.parse_args()

    available = discover_test_apps()
    if args.list:
        print("\n".join(available))
        return 0
    if args.all and args.apps:
        parser.error("Choose app names or --all, not both.")
    selected = available if args.all else args.apps
    if not selected:
        parser.error("Pass one or more app names, or use --all. Use --list to see available apps.")

    normalized = [name.removeprefix("apps.") for name in selected]
    unknown = sorted(set(normalized) - set(available))
    if unknown:
        parser.error(f"No tests found for: {', '.join(unknown)}. Available: {', '.join(available)}")

    sys.path.insert(0, str(BACKEND_DIR))
    import os

    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
    from django.core.management import execute_from_command_line

    command = ["manage.py", "test", *(f"apps.{name}" for name in normalized), "--verbosity", str(args.verbosity)]
    if args.keepdb:
        command.append("--keepdb")
    return execute_from_command_line(command) or 0


if __name__ == "__main__":
    raise SystemExit(main())
