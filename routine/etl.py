# -*- coding: utf-8 -*-
"""Jigcar Team Momentum - deterministic ETL.

Every figure here traces to a pull recorded in raw/. The model is never used to
produce a metric value; it only writes the "Read & actions" narrative downstream.

Run order: parse_granola.py -> etl.py -> render.py -> qa.py -> slack_messages.py
"""
import json, collections, datetime, os, re, sys

SP = os.environ.get("JIGCAR_SP") or os.path.dirname(os.path.abspath(__file__))
RUN_DATE = os.environ.get("JIGCAR_RUN_DATE", "2026-07-27")
RUN_STAMP = os.environ.get("JIGCAR_RUN_STAMP", "27 Jul 2026, 15:45")
QUARTER_TARGET = 400000                      # Q3 2026. One editable constant per quarter.
REPS = ["Chris", "Luke", "James", "Bianca", "Elliott", "Rupert"]
IDX = {r: i for i, r in enumerate(REPS)}
PROG = ["New Lead", "Buy Signal", "Qualification", "Demo", "Proposal", "Trial", "Contracts", "Closed Won"]
SHUT = ["Nurture", "Closed Lost", "Churn", "Non-ICP"]


def z():
    return [0] * 6


# ---------- channel normalisation: spelling only, never a semantic remap ----------
CHAN_FIX = {"Inboud - linkedin": "Inbound - LinkedIn"}


def norm_chan(c):
    if not c:
        return None
    return CHAN_FIX.get(c, c)


deals = json.load(open(f"{SP}/raw/deals_all.json"))
for d in deals:
    d["acq"] = norm_chan(d.get("acq"))
    # The state store keys deals on the 8-char record-id prefix. Keep that so the
    # stage diff stays continuous with every snapshot the routine has committed.
    d["id"] = d["short"]

# ---------- confirmed back-book won dates (manually confirmed, see spec) ----------
WON_DATES = {
    "61411697": "2026-02-15",   # Focus VM                -> Q1 2026 (quarter confirmed)
    "58be4a55": "2026-05-15",   # RH Car Transport        -> Q2 2026 (quarter confirmed)
    "1988b641": "2026-05-15",   # Monmotors               -> Q2 2026 (quarter confirmed)
    "4680be99": "2026-05-15",   # Premier Travel          -> Q2 2026 (quarter confirmed)
    "0cb33403": "2026-07-14",   # Peter Cooper Group      -> Q3 2026 (date confirmed)
    "a2223c13": "2026-07-23",   # Hilton Coachworks Group -> Q3 2026 (date confirmed)
}
WON_DATE_QUARTER_ONLY = {"61411697", "58be4a55", "1988b641", "4680be99"}
PRE_2026_WON = {"f05e16a4", "12f2dbef", "30866ff1", "3f1a45e1", "3a825192", "921a8e55",
                "18ea02a6", "8826de8e", "1ff4cc2c", "e7e86ecb"}


def quarter_of(iso):
    y, m = int(iso[:4]), int(iso[5:7])
    return f"Q{(m - 1) // 3 + 1}-{y}"


# ---------- sales meetings (Granola) ----------
# Excluded per the spec's definition. Keyed by (date, title) so the same title on a
# different day is judged on its own merits. Stored in state so the call is auditable.
EXCLUDED_MEETINGS = {
    ("2026-07-06", "Simon / Elliott"): "adviser",
    ("2026-07-13", "Major Client Tender - Jigcar"): "supplier / 3PL carrier, no deal attached",
    ("2026-07-14", "Elliott / Paul - plant hire transport"): "exploratory, no deal attached",
    ("2026-07-14", "Introduction mtg. Jigcar and Thoughtline Digital"): "vendor / agency intro",
    ("2026-07-16", "Jigcar x Automotive Logistics catch up"): "media / press",
    ("2026-07-16", "Quick catch up with Jonathan Holland on Auction Houses"): "adviser",
    ("2026-07-20", "Groupe CAT / Jigcar"): "supplier / 3PL carrier",
    ("2026-07-21", "Jigcar sales team weekly"): "internal weekly (external addresses are own contractors)",
    ("2026-07-21", "TradeBid/Jigcar Potential Strategic Collaboration"): "partner / channel exploration, no deal attached",
    ("2026-07-24", "Book a 30-min meeting with Elliott at Jigcar (Rita Schmidt)"): "tooling / vendor (HERE maps)",
    ("2026-07-24", "Jig Car chat"): "investor",
}
EXCL_PREFIX = [(d, t[:40]) for (d, t) in EXCLUDED_MEETINGS]

gran = json.load(open(f"{SP}/raw/granola.json"))
FIRST = {"chris.white@jigcar.com": "Chris", "luke.nogueira@jigcar.com": "Luke",
         "james.griffin@jigcar.com": "James", "bianca.monteiro@jigcar.com": "Bianca",
         "elliott@jigcar.com": "Elliott", "rupert@jigcar.com": "Rupert"}
seen = set()
meetings_daily = collections.defaultdict(z)
inc_count = exc_count = internal_count = 0
for m in gran:
    em = m["emails"]
    if not em or all(e.endswith("@jigcar.com") for e in em):
        internal_count += 1
        continue
    key = (m["date"], m["title"])
    if key in seen:                      # dedupe: one event per note-creator
        continue
    seen.add(key)
    if any(m["date"] == d and m["title"][:40] == p for (d, p) in EXCL_PREFIX):
        exc_count += 1
        continue
    inc_count += 1
    for e in em:
        if e in FIRST:
            meetings_daily[m["date"]][IDX[FIRST[e]]] += 1

# ---------- calls (Allo, per seat) ----------
# One row per call record from allo_search_conversation_items, reconciled against
# allo_get_team_analytics. Rupert has no Allo account, so his column is always 0
# and his seat renders na rather than a zero that looks like inactivity.
_calls = json.load(open(f"{SP}/raw/calls.json"))
calls_daily = _calls["by_day"]

# ---------- emails (Attio multi-mailbox search, de-duped by sender+subject+sent_at) ----------
# pull_emails.py owns the tally, the deal split and the coverage window. Days it did
# not page are carried forward from the previous state, never rebuilt as zero.
_em = json.load(open(f"{SP}/raw/emails.json"))
emails_daily = _em["by_day"]
emails_deal = _em["deal"]
emails_cust = _em["cust"]
EMAIL_COVERED_FROM = min(emails_daily) if emails_daily else None
EMAIL_SPLIT_FROM = min(_em["split_by_day"]) if _em["split_by_day"] else None
EMAIL_SPLIT_TO = max(_em["split_by_day"]) if _em["split_by_day"] else None

# ---------- tasks completed (dated by completed_at from the Attio tasks API) ----------
# completed_at, never created_at. An earlier build dated tasks by creation, which
# credited the day a task was written rather than the day the work was done.
_tasks = json.load(open(f"{SP}/raw/tasks.json"))
tasks_daily = collections.defaultdict(z)
for _t in _tasks:
    if not _t.get("is_completed") or not _t.get("completed_at"):
        continue
    for _a in _t.get("assignees") or []:
        if _a in IDX:
            tasks_daily[_t["completed_at"][:10]][IDX[_a]] += 1
tasks_daily = dict(sorted(tasks_daily.items()))
TASKS_UNASSIGNED = sum(1 for _t in _tasks if _t.get("is_completed") and not _t.get("assignees"))

# ---------- LinkedIn (Groovin notes in Attio, rep read from the note body) ----------
# The rep is NOT in the note title for invitations, which is why an earlier build fell
# back to cadence tasks and mis-attributed. It is in the body:
#   sent      "from <Rep> to <Contact>"
#   accepted  "<Rep> is now connected with <Contact>."
# Chat notes carry the rep in the title instead. Every event writes a person-side and a
# company-side note, so events are deduped on (date, rep, contact, kind) and the company
# side supplies the deal join. Deal-associated means an OPEN deal, New Lead through
# Contracts, the same test the email split uses.
_inv = json.load(open(f"{SP}/raw/li_invites.json"))
_msg = json.load(open(f"{SP}/raw/li_msgs.json"))
li_conn_all = _inv["sentAll"]        # invitations sent
li_conn_deal = _inv["sentDeal"]
li_acc_all = _inv["accAll"]          # invitations accepted, i.e. connections made
li_acc_deal = _inv["accDeal"]
li_msg_all = _msg["all"]
li_msg_deal = _msg["deal"]
LI_NOTE_COVERED_FROM = "2026-07-21"
LI_ATTRIBUTION = "read from the Groovin note body; no cadence-task proxy is used"

# ---------- deal-association join coverage (pull_attio.py) ----------
# (deal) everywhere on the page means the counterparty's company has an OPEN deal.
# The join depends on Attio's deal <-> company links, so its coverage is reported
# rather than assumed: an unjoinable deal must not read as "no deal".
_join = json.load(open(f"{SP}/raw/join_report.json"))

# ---------- deals assigned per day (Attio created_at) ----------
deals_daily = collections.defaultdict(z)
for d in deals:
    if d["created"] >= "2026-07-01" and d["owner"] in IDX:
        deals_daily[d["created"]][IDX[d["owner"]]] += 1

# ---------- progressed / shut off: diff against the previous run's snapshot ----------
PREV_STATE = f"{SP}/raw/prev_state.json"
prev, prior_moves = {}, []
try:
    with open(PREV_STATE) as fh:
        _ps = json.load(fh)
    prev = _ps.get("stage_snapshot", {})
    prior_moves = _ps.get("stage_moves") or []
except FileNotFoundError:
    print("NOTE: no previous snapshot; this run seeds the baseline and the diff is empty")

STAGE_DIFF = []
for d in deals:
    before = prev.get(d["id"])
    if not before:
        continue                                  # new deal: counted as assigned, not progressed
    old_stage, new_stage = before["stage"], d["stage"]
    if old_stage == new_stage or not new_stage:
        continue
    owner = d["owner"]
    if owner not in IDX:
        continue                                  # non-scorecard owner: revenue panels only
    if new_stage in SHUT:
        kind = "shutoff"
    elif old_stage in PROG and new_stage in PROG and PROG.index(new_stage) > PROG.index(old_stage):
        kind = "progressed"
    elif old_stage in SHUT and new_stage in PROG:
        kind = "progressed"                       # reopened out of a shut-off state
    else:
        kind = "regressed"                        # backward move: recorded, counted neither way
    STAGE_DIFF.append({"record_id": d["id"], "name": d["name"], "owner": owner,
                       "from": old_stage, "to": new_stage, "kind": kind,
                       "date": RUN_DATE, "value": d["value"]})


# Observed moves accumulate. A second run on the same day sees no new diff (it already
# applied the change to its own baseline), so today's row is rebuilt from the union of
# everything observed, deduped by record/from/to/date.
def _key(m):
    return (m["record_id"], m["from"], m["to"], m["date"])


seen_moves = {_key(m) for m in prior_moves}
ALL_MOVES = list(prior_moves)
for m in STAGE_DIFF:
    if _key(m) not in seen_moves:
        seen_moves.add(_key(m))
        ALL_MOVES.append(m)

progressed_daily = collections.defaultdict(z)
shutoff_daily = collections.defaultdict(z)
newly_won = []
for m in ALL_MOVES:
    if m["owner"] not in IDX:
        continue
    if m["kind"] == "progressed":
        progressed_daily[m["date"]][IDX[m["owner"]]] += 1
    elif m["kind"] == "shutoff":
        shutoff_daily[m["date"]][IDX[m["owner"]]] += 1
    if m["to"] == "Closed Won" and m["record_id"] not in WON_DATES:
        WON_DATES[m["record_id"]] = m["date"]     # stamp the real won date on first entry
        newly_won.append(m)

daily = {"meetings": dict(meetings_daily), "calls": calls_daily, "emails": emails_daily,
         "tasks": tasks_daily, "deals": dict(deals_daily), "progressed": dict(progressed_daily),
         "shutoff": dict(shutoff_daily), "liConnAll": li_conn_all, "liConnDeal": li_conn_deal,
         "liMsgAll": li_msg_all, "liMsgDeal": li_msg_deal,
         "liAccAll": li_acc_all, "liAccDeal": li_acc_deal,
         "emailsDeal": emails_deal, "emailsCust": emails_cust}

# ---------- revenue ----------
closed_won = [d for d in deals if d["stage"] == "Closed Won"]
contracts = [d for d in deals if d["stage"] == "Contracts"]
MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]


def pretty(iso):
    return f"{int(iso[8:10])} {MONTHS[int(iso[5:7]) - 1]} {iso[:4]}"


def est_label(d):
    """Estimated close for a Contracts deal, marked when it has already passed."""
    e = d.get("est_closed")
    if not e:
        return "est TBC"
    lbl = f"{int(e[8:10])} {MONTHS[int(e[5:7]) - 1]}"
    return f"{lbl} (est, passed)" if e < RUN_DATE else f"{lbl} (est)"


q3_won, won_ytd = [], []
for d in closed_won:
    wd = WON_DATES.get(d["id"])
    if not wd:
        continue                                  # pre-2026 book, excluded from 2026 views
    q = quarter_of(wd)
    entry = {"name": d["name"], "arr": d["value"], "owner": d["owner"],
             "quarter": q.split("-")[0], "channel": d["acq"] or "Unassigned",
             "date": ("%s 2026" % q.split("-")[0]) if d["id"] in WON_DATE_QUARTER_ONLY else pretty(wd)}
    won_ytd.append(entry)
    if q == "Q3-2026":
        q3_won.append(entry)

contract_deals = [{"name": d["name"], "arr": d["value"], "owner": d["owner"],
                   "date": est_label(d), "est_iso": d.get("est_closed"),
                   "passed": bool(d.get("est_closed") and d["est_closed"] < RUN_DATE)}
                  for d in contracts]
contract_deals.sort(key=lambda x: -x["arr"])
q3_won.sort(key=lambda x: -x["arr"])

# ---------- acquisition chart: full won book ----------
acq = collections.Counter((d["acq"] or "Unassigned") for d in closed_won)


# ---------- archive: reconstructed Q1/Q2 2026 ----------
def archive(qkey, start, end, label):
    cw = [e for e in won_ytd if e["quarter"] == qkey]
    created = [d for d in deals if start <= d["created"] <= end]
    byo = collections.defaultdict(lambda: {"created": 0, "value": 0})
    for d in created:
        byo[d["owner"]]["created"] += 1
        byo[d["owner"]]["value"] += d["value"]
    out = collections.Counter()
    for d in created:
        s = d["stage"]
        if s == "Closed Won":
            out["Now won"] += 1
        elif s == "Nurture":
            out["Nurture"] += 1
        elif s in ("Closed Lost", "Non-ICP", "Churn") or s is None:
            out["Non-ICP / Lost"] += 1
        else:
            out["Live (New Lead to Contracts)"] += 1
    return {"label": label,
            "closedWon": [{"name": e["name"], "arr": e["arr"], "owner": e["owner"],
                           "date": e["date"], "channel": e["channel"]}
                          for e in sorted(cw, key=lambda x: -x["arr"])],
            "acquisition": dict(collections.Counter(e["channel"] for e in cw)),
            "createdCount": len(created),
            "createdPipeline": sum(d["value"] for d in created),
            "byOwner": [{"name": k, "created": v["created"], "value": v["value"]}
                        for k, v in sorted(byo.items(), key=lambda kv: -kv[1]["created"])],
            "outcomes": dict(out)}


archives = {
    "Q2-2026": archive("Q2", "2026-04-01", "2026-06-30", "Q2 2026 (Apr - Jun) . reconstructed archive"),
    "Q1-2026": archive("Q1", "2026-01-01", "2026-03-31", "Q1 2026 (Jan - Mar) . reconstructed archive"),
}

# ---------- connectivity, from this run's actual results ----------
# The SHAPE here is a contract with render.py, and getting it wrong does not fail
# loudly, it ships a blank dashboard:
#   workspace : ARRAY of {name,status,note}  - renderConn calls workspace.map(...)
#   seats     : keyed by PERSON -> [Allo, Email, Groovin]  - the scorecard reads
#               connectivity.seats[r][0] for the Calls cell, so a wrong key or a
#               non-array takes out the metric cards and the summary table too.
# A run once wrote workspace as a dict and seats keyed by connector. Every render
# threw inside its own try/catch, so QA passed and the published page was empty.
# Validate here rather than discover it in a screenshot.
connectivity = json.load(open(f"{SP}/raw/connectivity.json"))
VALID_STATUS = {"ok", "partial", "unknown", "down", "na"}
if not isinstance(connectivity.get("workspace"), list):
    raise SystemExit("connectivity.workspace must be a LIST of {name,status,note}; "
                     f"got {type(connectivity.get('workspace')).__name__}")
for _w in connectivity["workspace"]:
    if not {"name", "status", "note"} <= set(_w):
        raise SystemExit(f"connectivity.workspace entry missing name/status/note: {_w}")
    if _w["status"] not in VALID_STATUS:
        raise SystemExit(f"connectivity.workspace bad status {_w['status']!r} for {_w['name']}")
_seats = connectivity.get("seats")
if not isinstance(_seats, dict) or set(_seats) != set(REPS):
    raise SystemExit("connectivity.seats must be keyed by person, exactly "
                     f"{REPS}; got {sorted(_seats) if isinstance(_seats, dict) else type(_seats).__name__}")
for _r, _v in _seats.items():
    if not isinstance(_v, list) or len(_v) != 3:
        raise SystemExit(f"connectivity.seats[{_r!r}] must be a 3-item list "
                         f"[Allo, Email, Groovin]; got {_v!r}")
    for _s in _v:
        if _s not in VALID_STATUS:
            raise SystemExit(f"connectivity.seats[{_r!r}] bad status {_s!r}")
connectivity["updated"] = RUN_STAMP

# ---------- time ranges ----------
d0 = datetime.date(*[int(x) for x in RUN_DATE.split("-")])
DAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
MONTHS_FULL = ["January", "February", "March", "April", "May", "June", "July",
               "August", "September", "October", "November", "December"]


def dlabel(d):
    return f"{DAYS[d.weekday()]} {d.day} {MONTHS[d.month - 1]}"


# "This week" is the calendar week, Monday to Sunday, capped at the run date because
# there is no data for days that have not happened. On a Monday that is a single day.
wk_start = d0 - datetime.timedelta(days=d0.weekday())
wk_days = (d0 - wk_start).days + 1
complete_week = d0.weekday() == 6          # only a Sunday run sees the full Mon-Sun week


def dm(d):
    return f"{d.day} {MONTHS[d.month - 1]}"


if wk_start == d0:
    wk_text = f"{dlabel(d0)} (week to date, 1 day)"
else:
    span = (f"{wk_start.day}-{d0.day} {MONTHS[d0.month - 1]}"
            if wk_start.month == d0.month else f"{dm(wk_start)} - {dm(d0)}")
    wk_text = f"{span} ({wk_days} days)" if complete_week else f"{span} (week to date, {wk_days} days)"

# Trailing seven days. Not shown in the UI toggle: this is the basis for the Slack
# performance threshold, which the spec defines over a full week. Reusing the calendar
# week there would flag someone for a quiet Monday morning.
t7_start = d0 - datetime.timedelta(days=6)

ranges = {"today": [RUN_DATE, RUN_DATE],
          "yesterday": [str(d0 - datetime.timedelta(days=1))] * 2,
          "week": [str(wk_start), RUN_DATE],
          "month": [f"{RUN_DATE[:7]}-01", RUN_DATE],
          "quarter": ["2026-07-01", RUN_DATE],
          "trailing7": [str(t7_start), RUN_DATE]}
rangeText = {"today": dlabel(d0),
             "yesterday": dlabel(d0 - datetime.timedelta(days=1)),
             "week": wk_text,
             "month": f"{MONTHS_FULL[d0.month - 1]}, 1-{d0.day}",
             "quarter": f"Q3 to date, 1-{d0.day} {MONTHS[d0.month - 1]}",
             "trailing7": f"{dm(t7_start)} - {dm(d0)} (7 days)"}

# ---------- leave (Zelt absence feed) ----------
# Activity is only meaningful against days a person was actually at work. Without
# this, a booked holiday reads as a performance gap.
leave = json.load(open(f"{SP}/raw/leave.json"))
leave_by_person = leave["by_person"]
off_today = leave["by_date"].get(RUN_DATE, [])


def working_days(person, start, end):
    """Weekdays in the range that the person was not on full-day leave.

    A half day still counts as a working day: they were partly at work, so the
    day is not removed, it is just not treated as a full one.
    """
    days = leave_by_person.get(person, {})
    a, b = datetime.date(*[int(x) for x in start.split("-")]), datetime.date(*[int(x) for x in end.split("-")])
    n, cur = 0, a
    while cur <= b:
        if cur.weekday() < 5 and days.get(str(cur)) != "FULL":
            n += 1
        cur += datetime.timedelta(days=1)
    return n


attendance = {r: {v: working_days(r, *ranges[v]) for v in ranges} for r in REPS}
leave_summary = {r: sorted(k for k, v in leave_by_person.get(r, {}).items()) for r in REPS}

coverage = {
    "progressed_shutoff": "measured by diffing this run's stage snapshot against the previous run's",
    "leave_source": ("Zelt absence calendar; the Jigcar holidays calendar holds no events after "
                     "mid-2025 and is not read"),
    "attendance_note": ("activity is measured against working days attended, so booked leave is "
                        "never counted as inactivity; a half day still counts as attended"),
    "stage_diff": STAGE_DIFF,
    "stage_moves_accumulated": len(ALL_MOVES),
    "email_covered_from": EMAIL_COVERED_FROM,
    "email_note": (f"sent-email coverage starts {EMAIL_COVERED_FROM} and accumulates a day per run; "
                   f"this run paged {_em['pulled_from']} to {_em['pulled_to']} and carried forward "
                   f"{len(_em['carried_days'])} earlier day(s). July days before "
                   f"{EMAIL_COVERED_FROM} are not covered and read as a floor, never as zero."),
    "email_rupert": "Rupert's own mailbox is not connected, so his sends are only visible where a teammate was a recipient",
    "linkedin_notes_covered_from": LI_NOTE_COVERED_FROM,
    "tasks_dated_by": "completed_at from the Attio tasks API",
    "li_connects_attributed_by": LI_ATTRIBUTION,
    "li_connect_gap": ("none: every invitation sent and accepted is attributed to a named rep from the "
                       "note body, deduped across the person and company copies"),
    "li_accepted_note": ("connections made lag the invitation that earned them, often by weeks, so a high "
                         "accepted count reflects earlier outreach rather than work done in the period"),
    "calls_source": (f"Allo per-seat call records ({_calls['total']} calls "
                     f"{_calls['covered_from']} to {_calls['covered_to']}); Rupert has no Allo account, "
                     "so his calls are always 0 and his seat reads na"),
    "tasks_unassigned": TASKS_UNASSIGNED,
    "email_split_from": EMAIL_SPLIT_FROM,
    "email_split_to": EMAIL_SPLIT_TO,
    "email_split_note": (
        "sent emails split by recipient: live deal (an open deal, New Lead to Contracts), "
        "customer (Closed Won), or neither. Resolved by recipient domain to the Attio company "
        "and its strongest deal state. Only classified for the window above; days outside it "
        "show a total with no split."),
    "email_split_join": (f"{_em['domains_resolving']} domains resolve to a deal; "
                         f"{_join['joinable']} of {_join['open_deals']} open deals are joinable "
                         f"and {_join['joinable_pct_by_value']}% by pipeline value"),
    # Surfaced for repair rather than inferred. Never invent a domain to close the gap.
    "join_coverage": _join,
    "join_note": (f"{_join['unjoinable']} open deal(s) cannot be joined to a counterparty: "
                  "either no company is linked or the company has no domain. All carry £0, so "
                  f"{_join['joinable_pct_by_value']}% of pipeline value is joinable. Listed for "
                  "repair on the coverage panel; no domain is ever inferred."),
}

state = {"schema": 3, "last_run": RUN_DATE, "last_run_stamp": RUN_STAMP,
         "quarter_target": QUARTER_TARGET,
         "stage_snapshot": {d["id"]: {"stage": d["stage"], "owner": d["owner"], "value": d["value"]} for d in deals},
         "won_dates": WON_DATES,
         "won_dates_quarter_only": sorted(WON_DATE_QUARTER_ONLY),
         "pre_2026_won": sorted(PRE_2026_WON),
         "daily_metrics": daily,
         "stage_moves": ALL_MOVES,
         "connectivity": connectivity,
         "archive": archives,
         "meeting_classification": {"excluded": {f"{d}|{t}": r for (d, t), r in EXCLUDED_MEETINGS.items()},
                                    "included_count": inc_count, "excluded_count": exc_count,
                                    "internal_only_count": internal_count},
         # carried forward, not recomputed: slack_messages.py owns this and needs the
         # history to escalate on the third consecutive day rather than repeat itself
         "perf_flags": (_ps.get("perf_flags", {}) if prev else {}),
         "leave": leave_summary,
         "off_today": off_today,
         "attendance": attendance,
         "coverage": coverage}

os.makedirs(f"{SP}/build", exist_ok=True)
json.dump(state, open(f"{SP}/build/dashboard_state.json", "w"), indent=1, sort_keys=True)

payload = {"RUN_STAMP": RUN_STAMP, "RUN_DATE": RUN_DATE, "QUARTER_TARGET": QUARTER_TARGET, "daily": daily,
           "closedWonDeals": [{"name": e["name"], "arr": e["arr"], "date": e["date"],
                               "owner": e["owner"], "channel": e["channel"]} for e in q3_won],
           "contractDeals": contract_deals,
           "wonYTD": [{"name": e["name"], "arr": e["arr"], "owner": e["owner"],
                       "quarter": e["quarter"], "channel": e["channel"]}
                      for e in sorted(won_ytd, key=lambda x: x["quarter"])],
           "acqChannels": dict(acq.most_common()),
           "wonBookCount": len(closed_won),
           "connectivity": connectivity, "ranges": ranges, "rangeText": rangeText,
           "archives": archives, "coverage": coverage,
           "stageMoves": ALL_MOVES,
           "leave": leave_summary, "offToday": off_today, "attendance": attendance}
json.dump(payload, open(f"{SP}/build/payload.json", "w"), indent=1)

print("=== VALIDATION ===")
print("deals:", len(deals), "| won book:", len(closed_won), "| contracts:", len(contracts))
print("meetings included:", inc_count, "excluded:", exc_count, "internal-only:", internal_count)
print("July meeting attendee-credits:", sum(sum(v) for v in meetings_daily.values()))
print("new stage moves this run:", len(STAGE_DIFF), "| accumulated:", len(ALL_MOVES))
for m in STAGE_DIFF:
    print("   ", m["name"], m["from"], "->", m["to"], f"({m['kind']}, {m['owner']}, £{m['value']:,.0f})")
print("newly won stamped:", [m["name"] for m in newly_won])
print("Q3 won:", sum(e["arr"] for e in q3_won), [(e["name"], e["arr"], e["owner"]) for e in q3_won])
print("contract out:", sum(c["arr"] for c in contract_deals))
print("acq (full won book):", dict(acq))
print("off today:", [f"{e['person']}{' (' + e['half'] + ')' if e['half'] else ''}" for e in off_today] or "nobody")
print("working days attended, trailing7:", {r: attendance[r]["trailing7"] for r in REPS})
for q, a in archives.items():
    print(q, "created", a["createdCount"], "pipeline", a["createdPipeline"],
          "won", len(a["closedWon"]), "outcomes", a["outcomes"])
