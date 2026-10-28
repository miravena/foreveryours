#!/usr/bin/env python3
"""Two-tier eval of the crisis fixture (#199, ADR-013).

    python3 scripts/crisis_eval.py --regex-only                       # offline table, no client
    python3 scripts/crisis_eval.py --auditor stub-perfect             # offline stub backstop
    scripts/with_key.sh python3 scripts/crisis_eval.py --model <id>   # live backstop (spends tokens)
    python3 scripts/crisis_eval.py --replay out/crisis_eval/<slug>.jsonl

Every row of tests/fixtures/crisis_eval_set.jsonl goes through the fast-path
(``safety.fastpath.check``, offline). Rows the fast-path does not fire on go
through the AUDIT backstop (``pipeline.audit.audit_reply``), reusing
scripts/audit_eval.py's loader, cache, budget and call helpers. A crisis row is
covered when the fast-path fired crisis OR the backstop said CRISIS; a benign
row is a false flag when either tier fires. The 988 line is US-only (#89).

The last stdout line is the score line:

    tiers=<regex|regex+backstop> crisis=<n> regex=<a> backstop=<b> missed=<c> false_flags=<f>/<m> unknown=<u> calls=<k>

Exit 0 when every crisis row is covered and no benign row is flagged; 1
otherwise; 2 usage or input error; 3 call cap reached.
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import audit_eval  # noqa: E402
from safety import fastpath  # noqa: E402

DEFAULT_FIXTURE = ROOT / "tests" / "fixtures" / "crisis_eval_set.jsonl"
DEFAULT_OUT_DIR = ROOT / "out" / "crisis_eval"


def regex_results(rows) -> dict[str, bool]:
    return {r["id"]: fastpath.check(r["transcript"]).severity == "crisis" for r in rows}


def print_table(rows, fired) -> None:
    print(f"{'id':<10} {'tier':<9} {'regex':<6} transcript")
    for r in rows:
        print(f"{r['id']:<10} {r.get('tier', '-'):<9} {'FIRE' if fired[r['id']] else '-':<6} {r['transcript'][:70]}")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    src = ap.add_mutually_exclusive_group(required=True)
    src.add_argument("--regex-only", action="store_true", help="fast-path table only, no backstop")
    src.add_argument("--model", help="AUDIT model id to evaluate live")
    src.add_argument("--auditor", choices=("stub-none", "stub-perfect"), help="offline stub backstop")
    src.add_argument("--replay", type=Path, help="score a recorded out file; no client, no network")
    ap.add_argument("--fixture", type=Path, default=DEFAULT_FIXTURE)
    ap.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    ap.add_argument("--max-calls", type=int, default=100)
    args = ap.parse_args(argv)

    try:
        rows = audit_eval.load_fixture(args.fixture)
    except (OSError, ValueError) as exc:
        print(f"crisis_eval: bad fixture: {exc}", file=sys.stderr)
        return 2

    fired = regex_results(rows)
    print_table(rows, fired)
    crisis = [r for r in rows if r["expect_flag"]]
    benign = [r for r in rows if not r["expect_flag"]]
    calls = 0
    records: dict[str, dict] = {}
    tiers = "regex"

    if not args.regex_only:
        tiers = "regex+backstop"
        pending = [r for r in rows if not fired[r["id"]]]
        if args.replay:
            records = audit_eval.load_records(args.replay)
            missing = [r["id"] for r in pending if r["id"] not in records]
            if missing:
                print(f"crisis_eval: replay lacks {len(missing)} ids: {','.join(missing[:5])}", file=sys.stderr)
                return 2
        else:
            if args.model:
                os.environ["AUDIT_MODEL"] = args.model
                auditor = audit_eval.make_auditor("live")
                name = args.model
            else:
                auditor = audit_eval.make_auditor(args.auditor)
                name = args.auditor
            out_path = args.out_dir / f"{audit_eval.slug(name)}.jsonl"
            records = audit_eval.load_records(out_path)
            try:
                calls = audit_eval.run_rows(pending, records, auditor, out_path, args.max_calls)
            except audit_eval.CapReached as exc:
                print(f"cap reached: {exc.args[0]}; re-run to resume. No score printed.", file=sys.stderr)
                return 3

    def backstop_says(r, status):
        rec = records.get(r["id"])
        return bool(rec) and not fired[r["id"]] and rec["status"] == status

    regex_hits = sum(1 for r in crisis if fired[r["id"]])
    backstop_hits = sum(1 for r in crisis if backstop_says(r, "CRISIS"))
    missed = [r["id"] for r in crisis if not fired[r["id"]] and not backstop_says(r, "CRISIS")]
    false_flags = [
        r["id"] for r in benign
        if fired[r["id"]] or (records.get(r["id"]) and records[r["id"]]["status"] not in audit_eval.NOT_FLAGS)
    ]
    unknown = sum(1 for rec in records.values() if rec.get("status") == "UNKNOWN")
    if args.regex_only:
        missed = [r["id"] for r in crisis if not fired[r["id"]] and r.get("tier") != "backstop"]
    print(f"# missed={','.join(missed) or '-'} false_flagged={','.join(false_flags) or '-'}")
    print(f"tiers={tiers} crisis={len(crisis)} regex={regex_hits} backstop={backstop_hits} "
          f"missed={len(missed)} false_flags={len(false_flags)}/{len(benign)} unknown={unknown} calls={calls}")
    return 0 if not missed and not false_flags else 1


if __name__ == "__main__":
    sys.exit(main())
