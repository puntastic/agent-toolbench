"""Inspect report consistency and print counts without ranking interfaces."""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from reporting import load, summarize, validate


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("reports", type=Path, nargs="*")
    parser.add_argument("--json", action="store_true", help="Machine-readable summary instead of the short human view")
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    paths = args.reports or [root / "results/baseline.json", root / "results/candidate.json",
                             root / "results/harness-v2-validation.json"]
    failed = False
    for path in paths:
        try:
            report = load(path)
            errors = validate(report)
            if errors:
                raise ValueError("; ".join(errors))
            binding = ("start/end hashes match" if report.get("source_hashes_match") is True else
                       "source changed; comparison unqualified" if report.get("source_hashes_match") is False else
                       "v1: end-of-run hash only")
            rows = summarize(report)
            if args.json:
                print(json.dumps({"report": path.name, "structurally_consistent": True,
                                  "source_binding": binding, "arms": rows}, indent=2))
            else:
                print(f"{path.name}: structurally consistent; {binding}")
                for row in rows:
                    details = ", ".join(row["failed_cases"]) or "none"
                    boundary = (f"; execution errors: {row['execution_errors']}; incomplete captures: {row['incomplete_captures']}"
                                if row["execution_errors"] or row["incomplete_captures"] else "")
                    print(f"  {row['arm']:<17} {row['passed']}/{row['cases']}  mismatches: {details}{boundary}")
                print("  Counts describe these fixtures, not general superiority.\n")
        except (OSError, ValueError) as error:
            failed = True
            print(f"{path.name}: {error}", file=sys.stderr)
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
