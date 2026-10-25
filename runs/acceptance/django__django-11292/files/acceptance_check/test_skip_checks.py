"""Acceptance check for django__django-11292, from the issue text alone.

The issue: management commands have a skip_checks stealth option, and it should be
exposed on the command line as --skip-checks, so a command run from the command line
can skip the system checks. Exit 0 is pass.
"""

import io
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import django
from django.conf import settings

settings.configure(INSTALLED_APPS=[], DATABASES={})
django.setup()

from django.core.management.base import BaseCommand


class Command(BaseCommand):
    requires_system_checks = True

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.checks_run = 0
        self.handled = False

    def check(self, *args, **kwargs):
        self.checks_run += 1

    def handle(self, *args, **options):
        self.handled = True


def run(argv):
    cmd = Command(stdout=io.StringIO(), stderr=io.StringIO())
    try:
        cmd.run_from_argv(["manage.py", "acceptance"] + argv)
    except SystemExit as e:
        return cmd, f"exited with {e.code}"
    return cmd, None


failures = []

cmd, err = run([])
if err or not cmd.handled or cmd.checks_run != 1:
    failures.append(f"without --skip-checks: handled={cmd.handled} checks_run={cmd.checks_run} {err or ''}")

cmd, err = run(["--skip-checks"])
if err:
    failures.append(f"--skip-checks is not accepted on the command line: {err}")
elif not cmd.handled or cmd.checks_run != 0:
    failures.append(f"with --skip-checks: handled={cmd.handled} checks_run={cmd.checks_run}")

help_text = Command().create_parser("manage.py", "acceptance").format_help()
if "--skip-checks" not in help_text:
    failures.append("--skip-checks is not in the command's --help")

for f in failures:
    print("FAIL:", f)
print("PASS" if not failures else f"{len(failures)} failure(s)")
sys.exit(1 if failures else 0)
