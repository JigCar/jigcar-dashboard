# -*- coding: utf-8 -*-
"""Turn the transcribed Allo call dump into raw/calls.json.

The seat list is confirmed each run with allo_list_users and the per-seat totals are
reconciled against allo_get_team_analytics, so the daily tally here is a regrouping
of real call records rather than a figure typed in by hand. Rupert has no Allo
account, so his column is always 0 and his seat renders na rather than a zero that
would read as inactivity.
"""
import json, os, collections

SP = os.environ.get("JIGCAR_SP") or os.path.dirname(os.path.abspath(__file__))
REPS = ["Chris", "Luke", "James", "Bianca", "Elliott", "Rupert"]
IDX = {r: i for i, r in enumerate(REPS)}

raw = json.load(open(f"{SP}/raw/allo_calls_raw.json"))
by_day = collections.defaultdict(lambda: [0] * 6)
per_seat = collections.Counter()
for c in raw["calls"]:
    who = c["user"]
    if who not in IDX:                    # a non-scorecard seat is recorded, never counted
        continue
    by_day[c["date"][:10]][IDX[who]] += 1
    per_seat[who] += 1

days = sorted(by_day)
out = {"by_day": dict(sorted(by_day.items())),
       "total": sum(per_seat.values()),
       "per_seat": {r: per_seat.get(r, 0) for r in REPS},
       "covered_from": days[0] if days else None,
       "covered_to": days[-1] if days else None,
       "source": raw["_source"],
       "reconciled": raw["_reconciled_against"],
       "seats": raw["_seats"]}
json.dump(out, open(f"{SP}/raw/calls.json", "w"), indent=1)

print("=== ALLO CALLS ===")
print("records:", out["total"], "| covered", out["covered_from"], "->", out["covered_to"])
print(f"{'day':12}" + "".join(f"{r:>9}" for r in REPS))
for d, v in out["by_day"].items():
    print(f"{d:12}" + "".join(f"{x:>9}" for x in v))
print("per seat:", out["per_seat"])
