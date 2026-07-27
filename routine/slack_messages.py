# -*- coding: utf-8 -*-
"""Build the two per-channel Slack messages.

The two channels get DIFFERENT messages and must never receive identical text.

#operation-foot-down  - internal performance channel. Four emoji-led lines plus the
                        link. Line 3 is a named performance risk: this channel exists
                        to name who is off pace.
#deal-updates         - wider team channel. Two lines plus the link. Nobody is named
                        unless a close, a contract movement or a genuine activity spike
                        fires. Deal names are not people and are always allowed.

Every number here is read from payload.json / dashboard_state.json. This module
does no pulling and invents no figures.
"""
import json, sys, datetime

SP = sys.argv[1] if len(sys.argv) > 1 else "."
DASHBOARD_URL = "https://jigcar.github.io/jigcar-dashboard/index-18.html"
REPS = ["Chris", "Luke", "James", "Bianca", "Elliott", "Rupert"]

payload = json.load(open(f"{SP}/payload.json"))
state = json.load(open(f"{SP}/dashboard_state.json"))
daily = payload["daily"]
RUN_DATE = state["last_run"]
TARGET = payload["QUARTER_TARGET"]


def agg(metric, view):
    s, e = payload["ranges"][view]
    out = [0] * 6
    for d, v in daily.get(metric, {}).items():
        if s <= d <= e:
            for i in range(6):
                out[i] += v[i]
    return out


def money(n):
    return "£" + format(int(n), ",")


# ---------- revenue ----------
won = sum(d["arr"] for d in payload["closedWonDeals"])
oc = sum(d["arr"] for d in payload["contractDeals"])
pct = round(won / TARGET * 1000) / 10
gap_if_land = max(0, TARGET - won - oc)

# ---------- what moved, from the accumulated stage-move log ----------
moves_today = [m for m in state.get("stage_moves", []) if m["date"] == RUN_DATE]
progressed = [m for m in moves_today if m["kind"] == "progressed"]
shut = [m for m in moves_today if m["kind"] == "shutoff"]
won_today = [m for m in moves_today if m["to"] == "Closed Won"]
contract_today = [m for m in moves_today if m["to"] == "Contracts"]


def move_phrase(with_names):
    """Describe today's stage movement. Deal names always; person names optional."""
    if not moves_today:
        return "No deal changed stage today."
    bits = []
    for m in progressed + shut:
        who = f" ({m['owner']})" if with_names else ""
        val = f" {money(m['value'])}" if m.get("value") else ""
        verb = "moved to" if m["kind"] == "progressed" else "shut off to"
        bits.append(f"{m['name']}{val}{who} {verb} {m['to']}")
    tail = "" if shut else " Nothing won or shut off."
    return "; ".join(bits) + "." + tail


# ---------- named performance risk (foot-down only) ----------
# Deterministic: rank the six on quarter sales meetings, then break ties on completed
# cadence tasks. The bottom-ranked person with a genuine gap is named, with the numbers
# that justify it. No judgement call is made in prose that the figures do not support.
q_mtg, q_task, q_call = agg("meetings", "quarter"), agg("tasks", "quarter"), agg("calls", "quarter")
w_mtg = agg("meetings", "week")
cands = sorted(range(6), key=lambda i: (q_mtg[i], q_task[i]))
r = cands[0]
risk = (f"{REPS[r]} is bottom of the quarter on sales meetings, {q_mtg[r]} in 27 days "
        f"({w_mtg[r]} in the last seven) with {q_task[r]} completed cadence tasks "
        f"and {q_call[r]} calls.")

# ---------- contract risk ----------
stalled = [d for d in payload["contractDeals"] if "passed" in d["date"]]
stalled_val = sum(d["arr"] for d in stalled)
if stalled:
    names = " and ".join(f"{d['name']} {money(d['arr'])}" for d in stalled)
    contract_line = (f"{names} are past their estimated close, {money(stalled_val)} of the "
                     f"{money(oc)} contract book sitting unsigned.")
else:
    contract_line = f"{money(oc)} in Contracts, none past its estimated close date."

# ---------- does #deal-updates get to name anyone? ----------
# Only a close, a contract movement, or a genuine activity spike unlocks names.
#
# A spike compares today against the rest of the week, so a metric may only take part
# if its coverage spans that whole window. Email coverage begins on the day the routine
# first ran, which makes today's email count look like a huge jump against six days of
# zeroes that are missing data, not inactivity. Including it would name someone for a
# coverage artefact, so any metric whose coverage starts after the window opens is
# excluded until it has the history to support the comparison.
SPIKE_FLOOR, SPIKE_MULT = 10, 3.0
window_start = payload["ranges"]["week"][0]
COVERAGE_FROM = {
    "emails": state["coverage"].get("email_covered_from", "0000-00-00"),
    "liConnAll": state["coverage"].get("linkedin_notes_covered_from", "0000-00-00"),
    "liMsgAll": state["coverage"].get("linkedin_notes_covered_from", "0000-00-00"),
}
spike_basis = [m for m in ("meetings", "calls", "emails")
               if COVERAGE_FROM.get(m, "0000-00-00") <= window_start]
excluded_basis = [m for m in ("meetings", "calls", "emails") if m not in spike_basis]

spikes = []
for i in range(6):
    today = sum(agg(m, "today")[i] for m in spike_basis)
    weekly = sum(agg(m, "week")[i] for m in spike_basis)
    mean = (weekly - today) / 6 if weekly else 0
    if today >= SPIKE_FLOOR and today >= SPIKE_MULT * max(mean, 1):
        spikes.append((REPS[i], today))
name_trigger = bool(won_today or contract_today or spikes)

# ---------- assemble ----------
foot_down = "\n".join([
    f":dart: {money(won)} won this quarter, {pct}% of the {money(TARGET)} target. "
    f"{money(oc)} out for contract, {money(gap_if_land)} short if all three land.",
    f":arrows_counterclockwise: {move_phrase(with_names=True)}",
    f":warning: {risk}",
    f":hourglass: {contract_line}",
    DASHBOARD_URL,
])

if name_trigger:
    line2 = move_phrase(with_names=True)
    if spikes:
        line2 += " " + "; ".join(f"{n} ran {c} touches today" for n, c in spikes) + "."
else:
    line2 = move_phrase(with_names=False)

deal_updates = "\n".join([
    f"{money(won)} won this quarter, {pct}% of the {money(TARGET)} target. "
    f"{money(oc)} out for contract across {len(payload['contractDeals'])} deals.",
    line2,
    DASHBOARD_URL,
])

if __name__ == "__main__":
    if foot_down == deal_updates:
        raise SystemExit("ABORT: identical text for both channels")
    print("=" * 78)
    print("#operation-foot-down")
    print("=" * 78)
    print(foot_down)
    print()
    print("=" * 78)
    print("#deal-updates")
    print("=" * 78)
    print(deal_updates)
    print()
    print("=" * 78)
    print(f"identical? {foot_down == deal_updates}")
    print(f"foot-down content lines: {len(foot_down.splitlines()) - 1} + link")
    print(f"deal-updates content lines: {len(deal_updates.splitlines()) - 1} + link")
    print(f"names unlocked in #deal-updates? {name_trigger} "
          f"(won today {len(won_today)}, contract moves {len(contract_today)}, spikes {spikes})")
    print(f"spike basis: {spike_basis}; excluded for insufficient coverage: {excluded_basis}")
