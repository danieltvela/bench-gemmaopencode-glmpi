#!/usr/bin/env python3
"""Run one grading phase of the shelf hidden test suite.

Phase A runs everything except the post-restart persistence checks; phase B
runs only the post-restart checks, against a server started with a custom
PORT and JWT_SECRET on the same SQLite file.
"""

import argparse
import json
import os
import sys
import time
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent


def iter_tests(suite):
    for item in suite:
        if isinstance(item, unittest.TestSuite):
            yield from iter_tests(item)
        else:
            yield item


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--phase", choices=["A", "B"], required=True)
    parser.add_argument(
        "--base-url",
        default=os.environ.get("SHELF_BASE_URL", "http://127.0.0.1:8080"),
    )
    parser.add_argument("--state", default=os.environ.get("SHELF_STATE", ""))
    parser.add_argument("--report", default=os.environ.get("SHELF_REPORT", ""))
    parser.add_argument("--module-dir", default=str(HERE))
    args = parser.parse_args()

    os.environ["SHELF_BASE_URL"] = args.base_url
    if args.state:
        os.environ["SHELF_STATE"] = args.state
    sys.path.insert(0, args.module_dir)

    loader = unittest.TestLoader()
    discovered = loader.discover(args.module_dir, pattern="test_*.py", top_level_dir=args.module_dir)
    selected = unittest.TestSuite()
    for test in iter_tests(discovered):
        if getattr(test.__class__, "PHASE", "A") == args.phase:
            selected.addTest(test)

    result = unittest.TestResult()
    started = time.time()
    selected.run(result)
    duration = time.time() - started

    cases = []
    for test, traceback in result.failures:
        cases.append({"id": test.id(), "outcome": "failed", "message": str(traceback)[:2000]})
    for test, traceback in result.errors:
        cases.append({"id": test.id(), "outcome": "error", "message": str(traceback)[:2000]})
    for test, reason in result.skipped:
        cases.append({"id": test.id(), "outcome": "skipped", "message": str(reason)[:500]})

    passed = result.testsRun - len(result.failures) - len(result.errors) - len(result.skipped)
    report = {
        "phase": args.phase,
        "base_url": args.base_url,
        "total": result.testsRun,
        "passed": passed,
        "failed": len(result.failures),
        "errors": len(result.errors),
        "skipped": len(result.skipped),
        "duration_s": round(duration, 3),
        "cases": cases,
    }
    text = json.dumps(report, indent=2)
    if args.report:
        report_path = Path(args.report)
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(text, encoding="utf-8")
    print(text)
    clean = report["failed"] == 0 and report["errors"] == 0 and report["total"] > 0
    return 0 if clean else 1


if __name__ == "__main__":
    sys.exit(main())
