# -*- coding: utf-8 -*-
"""Build the two per-channel Slack messages.

The two channels get DIFFERENT messages and must never receive identical text.

#operation-foot-down  leadership. Up to four emoji-led lines plus the link:
                      revenue, what moved, deal risk, performance risk. Lines 3
                      and 4 are omitted entirely when nothing qualifies.
#deal-updates         whole team. Two lines plus the link, three when a
                      celebration trigger fires. Nobody is named unless a close,
                      a contract movement or a genuine activity spike fires.
                      Deal names are not people and are always allowed.

Every number here is read from payload.json / dashboard_state.json. This module
does no pulling and invents no figures.
"""
import json, sys, os, re, collections, datetime

SP = os.environ.get("JIGCAR_SP") or (sys.argv[1] if len(sys.argv) > 1 else ".")
DASHBOARD_URL = "https://jigcar.github.io/jigcar-dashboard/index-18.html"
REPS = ["Chris", "Luke", "James", "Bianca", "Elliott", "Rupert"]
# Only these seats carry outbound. James is Transport Director and Bianca runs
# onboarding, so low outbound activity is expected and is never flagged.
OUTBOUND_SEATS = ["Chris", "Luke", "Elliott"]
CORE_METRICS = ["meetings", "emails", "tasks"]

payload = json.load(open(f"{SP}/build/payload.json"))
state = json.load(open(f"{SP}/build/dashboard_state.json"))
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


def short_money(n):
    return f"£{int(n) // 1000}k" if n >= 1000 and n % 1000 == 0 else money(n)


def ucfirst(s):
    """Capitalise the first character only, so deal and people names keep their case."""
    return s[:1].upper() + s[1:] if s else s


NUM = {0: "no", 1: "One", 2: "Two", 3: "Three", 4: "Four", 5: "Five", 6: "Six",
       7: "Seven", 8: "Eight", 9: "Nine", 10: "Ten"}


def word(n, lower=False):
    w = NUM.get(n, str(n))
    return w.lower() if lower else w


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
new_deals_today = sum(agg("deals", "today"))


def _named(ms):
    return ", ".join(f"{m['name']}{' ' + money(m['value']) if m.get('value') else ''} ({m['owner']})"
                    for m in ms)


def moved_leadership():
    """Named, deal-level. Real changes only.

    Deals that made the same hop are collapsed onto one clause. Repeating "into
    Qualification" once per deal turns a four-word fact into a wall of text, and
    this is read on a phone.
    """
    if not moves_today and not new_deals_today:
        return "Nothing moved since yesterday."
    bits = []
    by_hop = collections.OrderedDict()
    for m in progressed:
        by_hop.setdefault(m["to"], []).append(m)
    for to, ms in by_hop.items():
        if len(ms) == 1:
            bits.append(f"{_named(ms)} into {to}")
        else:
            bits.append(f"{word(len(ms), lower=True)} into {to}: {_named(ms)}")
    for m in shut:
        val = f" {money(m['value'])}" if m.get("value") else ""
        bits.append(f"{m['name']}{val} ({m['owner']}) shut off to {m['to']}")
    if new_deals_today:
        bits.append(f"{word(new_deals_today, lower=True)} new deals in")
    tail = "" if (won_today or shut) else " Nothing won or lost."
    # Each clause is its own sentence, so each one starts with a capital.
    return ". ".join(ucfirst(b) for b in bits) + "." + tail


def moved_team():
    """Counts only, nobody named."""
    if not moves_today and not new_deals_today:
        return "Nothing moved since yesterday."
    bits = []
    if progressed:
        bits.append(f"{word(len(progressed))} deal{'' if len(progressed) == 1 else 's'} progressed")
    if shut:
        bits.append(f"{word(len(shut), lower=True)} shut off")
    if new_deals_today:
        bits.append(f"{word(new_deals_today, lower=True)} new deals in")
    tail = "" if (won_today or shut) else " Nothing won or lost."
    return ucfirst(", ".join(bits)) + "." + tail


# ---------- deal risk: the single highest-value concern ----------
stalled = sorted([d for d in payload["contractDeals"] if d.get("passed")], key=lambda d: -d["arr"])
deal_risk = None
if stalled:
    ref = datetime.date(*[int(x) for x in RUN_DATE.split("-")])
    names = " and ".join(f"{d['name']} {money(d['arr'])}" for d in stalled)
    # The oldest slip, not whichever happened to be read last.
    slips = [(ref - datetime.date(*[int(x) for x in d["est_iso"].split("-")])).days
             for d in stalled if d.get("est_iso")]
    days = max(slips) if slips else None
    daytxt = f"{word(days, lower=True) if days <= 10 else days} days" if days else "several days"
    joiner = "both past est close by" if len(stalled) == 2 else "past est close by"
    deal_risk = f"{names} {joiner} {daytxt}."

# ---------- performance risk: one person, role-aware, real threshold ----------
# Threshold, never a ranking: zero on at least two of the three core outbound
# metrics across a full week. A ranking always flags someone; this does not.
#
# Measured over the trailing seven days, NOT the dashboard's "This week" filter.
# That filter is the calendar week Monday to Sunday, so on a Monday it covers a
# single morning and would flag almost the whole team for having done nothing yet.
WEEK_BASIS = "trailing7" if "trailing7" in payload["ranges"] else "week"
wk = {m: agg(m, WEEK_BASIS) for m in CORE_METRICS}
qt = {m: agg(m, "quarter") for m in CORE_METRICS}

# Leave gate. Someone on booked holiday has not underperformed, they were not at
# work, and naming them to leadership for it is exactly the noise this line must
# avoid. Two guards: never flag a person who is off today, and never judge a
# window in which they attended too few days for it to mean anything.
MIN_ATTENDED = 4
OFF_TODAY_FULL = {e["person"] for e in state.get("off_today", []) if not e.get("half")}
ATTENDANCE = state.get("attendance", {})

cands = []
skipped = []
for name in OUTBOUND_SEATS:
    i = REPS.index(name)
    attended = ATTENDANCE.get(name, {}).get(WEEK_BASIS, 5)
    if name in OFF_TODAY_FULL:
        skipped.append((name, "on leave today"))
        continue
    if attended < MIN_ATTENDED:
        skipped.append((name, f"only {attended} working days attended"))
        continue
    zeros = [m for m in CORE_METRICS if wk[m][i] == 0]
    if len(zeros) >= 2:
        cands.append({"name": name, "i": i, "zeros": zeros, "nz": len(zeros),
                      "q_mtg": qt["meetings"][i], "attended": attended})
cands.sort(key=lambda c: (-c["nz"], c["q_mtg"]))

# escalate, do not repeat: count consecutive prior days this person was flagged
prior_flags = state.get("perf_flags", {})
perf_risk = None
flagged_name = None
if cands:
    c = cands[0]
    flagged_name = c["name"]
    streak, probe = 1, datetime.date(*[int(x) for x in RUN_DATE.split("-")])
    while True:
        probe -= datetime.timedelta(days=1)
        if prior_flags.get(str(probe)) == flagged_name:
            streak += 1
        else:
            break
    i = c["i"]
    lbl = {"meetings": "sales meeting", "emails": "sent email", "tasks": "completed task"}
    zero_txt = " or ".join(lbl[m] for m in c["zeros"])
    extras = [m for m in CORE_METRICS if m not in c["zeros"]]
    extra_txt = ""
    if extras:
        m = extras[0]
        extra_txt = f", {word(wk[m][i], lower=True)} {lbl[m]}{'' if wk[m][i] == 1 else 's'}"
    mq = qt["meetings"][i]
    covered = c["zeros"] + ([extras[0]] if extras else [])
    tail = f" {word(mq)} all quarter." if "meetings" in covered else f" {word(mq)} sales meetings all quarter."
    if streak >= 3:
        tail += " Third day running."
    att = c["attended"]
    span = (f"across {word(att, lower=True)} working days"
            if att < 5 else ("in the last seven days" if WEEK_BASIS == "trailing7" else "all week"))
    perf_risk = f"{flagged_name}: no {zero_txt} {span}{extra_txt}.{tail}"

# record today's flag so tomorrow can escalate rather than repeat
state.setdefault("perf_flags", {})[RUN_DATE] = flagged_name
json.dump(state, open(f"{SP}/build/dashboard_state.json", "w"), indent=1, sort_keys=True)

# ---------- does #deal-updates get to name anyone? ----------
# Only a close, a contract movement, or a genuine activity spike unlocks names.
# A spike is at least double that person's trailing four-week daily average on the
# metric and above a floor of three. Until the store holds four weeks of history,
# fire only on a same-day team record, so a coverage artefact can never name anyone.
SPIKE_FLOOR = 3
MIN_HISTORY_DAYS = 5
FOUR_WEEKS = 28
# History depth is judged PER METRIC, not across all of them pooled. Pooling the
# dates made 16 days of meetings plus 20 of tasks look like four weeks of both, so
# the average branch fired on a metric that had nowhere near four weeks behind it.
spikes = []
for m in CORE_METRICS:
    days = sorted(daily.get(m, {}))
    if len(days) < MIN_HISTORY_DAYS:
        continue                     # too thin to distinguish a spike from missing coverage
    if len(days) >= FOUR_WEEKS:
        # Double the person's own trailing four-week daily average.
        for i, name in enumerate(REPS):
            today_v = agg(m, "today")[i]
            past = [v[i] for d, v in daily[m].items() if d < RUN_DATE][-FOUR_WEEKS:]
            avg = sum(past) / len(past) if past else 0
            if today_v >= SPIKE_FLOOR and avg and today_v >= 2 * avg:
                spikes.append((name, m, today_v, "double their four-week average"))
    else:
        # Until the store holds four weeks of THIS metric, fire only on a genuine
        # same-day team record. Strictly greater: equalling the previous best is not
        # a record, and calling it one names someone for a claim that is not true.
        series = {d: sum(v) for d, v in daily[m].items()}
        today_v = series.get(RUN_DATE, 0)
        others = [v for d, v in series.items() if d != RUN_DATE]
        if today_v >= SPIKE_FLOOR and others and today_v > max(others):
            top_i = max(range(6), key=lambda i: agg(m, "today")[i])
            spikes.append((REPS[top_i], m, agg(m, "today")[top_i], "a team record for a single day"))

celebration = None
if won_today:
    m = max(won_today, key=lambda x: x["value"])
    celebration = f"🏆 {m['owner']} closed {m['name']}, {money(m['value'])}."
elif contract_today:
    m = max(contract_today, key=lambda x: x["value"])
    celebration = f"📄 {m['name']} {money(m['value'])} out for contract, {m['owner']}."
elif spikes:
    name, metric, v, basis = spikes[0]
    lbl = {"meetings": "sales meetings", "emails": "emails", "tasks": "completed tasks"}[metric]
    celebration = f"🔥 {name} ran {v} {lbl} today, {basis}."

# ---------- connector failure, which owns line 3 on a partial run ----------
# On a partial run where a build did publish, the failure replaces deal risk. A
# reader needs to know a number is missing before they need to know it is bad.
conn = payload.get("connectivity", {})
down = [k for k, v in (conn.get("workspace") or {}).items()
        if (v.get("status") if isinstance(v, dict) else v) == "down"]
for seat, per in (conn.get("seats") or {}).items():
    if isinstance(per, dict) and any(v == "down" for v in per.values()):
        down.append(seat)
partial_note = None
if down:
    who = " and ".join(down)
    partial_note = (f"Partial run: {who} {'is' if len(down) == 1 else 'are'} down, so those figures "
                    "are the last good values. Everything else refreshed.")

# ---------- assemble ----------
# Every emoji-led point is separated by a BLANK line, including before the link.
# Slack renders single newlines tightly and the message reads as a wall of text.
SEP = "\n\n"
n_oc = len(payload["contractDeals"])
land = ("if it lands" if n_oc == 1
        else f"if all {word(n_oc, lower=True)} land" if n_oc <= 10
        else f"if all {n_oc} land")
foot_lines = [
    f"🎯 {money(won)} won this quarter, {pct}% of {short_money(TARGET)}. "
    f"{money(oc)} out for contract, {money(gap_if_land)} short {land}.",
    f"🔄 {moved_leadership()}",
]
if partial_note:
    foot_lines.append(f"⚠️ {partial_note}")
elif deal_risk:
    foot_lines.append(f"⚠️ {deal_risk}")
if perf_risk:
    foot_lines.append(f"🚩 {perf_risk}")
foot_lines.append(f"🔗 {DASHBOARD_URL}")
foot_down = SEP.join(foot_lines)

team_lines = []
if celebration:
    team_lines.append(celebration)
team_lines.append(f"🎯 {money(won)} won this quarter, {pct}% of {short_money(TARGET)}. "
                  f"{money(oc)} out for contract.")
team_lines.append(f"🔄 {moved_team()}")
team_lines.append(f"🔗 {DASHBOARD_URL}")
deal_updates = SEP.join(team_lines)

if __name__ == "__main__":
    if foot_down == deal_updates:
        raise SystemExit("ABORT: identical text for both channels")
    for name in REPS:
        if name in deal_updates and not celebration:
            raise SystemExit(f"ABORT: {name} named in #deal-updates with no celebration trigger")
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
    print(f"foot-down content lines: {len(foot_lines) - 1} + link (max 4 + link)")
    print(f"deal-updates content lines: {len(team_lines) - 1} + link")
    for lbl, msg in (("#operation-foot-down", foot_down), ("#deal-updates", deal_updates)):
        if "\n" in msg and SEP not in msg:
            raise SystemExit(f"ABORT: {lbl} points are not blank-line separated")
        if re.search(r"[^\n]\n[^\n]", msg):
            raise SystemExit(f"ABORT: {lbl} has a single newline between points")
    print(f"deal risk fired: {bool(deal_risk)} | perf risk fired: {bool(perf_risk)} -> {flagged_name}")
    print(f"connectors down: {down or 'none'} | line 3 = "
          f"{'partial-run failure' if partial_note else ('deal risk' if deal_risk else 'omitted')}")
    print(f"celebration trigger: {celebration!r}")
    print("spike basis per metric: " + str({m: ("4wk avg" if len(daily.get(m, {})) >= FOUR_WEEKS
                                                else f"team record ({len(daily.get(m, {}))}d history)"
                                                if len(daily.get(m, {})) >= MIN_HISTORY_DAYS
                                                else "too thin, skipped")
                                            for m in CORE_METRICS}))
    print("metric history depth: " + str({m: len(daily.get(m, {})) for m in CORE_METRICS}))
    print(f"perf candidates: {[(c['name'], c['zeros'], str(c['attended']) + 'd attended') for c in cands]}")
    print(f"perf skipped by the leave gate: {skipped}")
    print(f"off today: {[(e['person'], e['half'] or 'full') for e in state.get('off_today', [])] or 'nobody'}")
