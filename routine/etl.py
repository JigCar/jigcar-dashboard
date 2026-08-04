# -*- coding: utf-8 -*-
"""Jigcar Team Momentum - deterministic ETL.

Every figure here traces to a pull recorded in raw/. The model is never used to
produce a metric value; it only writes the "Read & actions" narrative downstream.

Run order: parse_granola.py -> etl.py -> render.py -> qa.py -> slack_messages.py
"""
import json, collections, datetime, os, re, sys

SP = os.environ.get("JIGCAR_SP") or os.path.dirname(os.path.abspath(__file__))
# The run date defaults to TODAY, never to a literal. Both of these were once frozen
# at the day the file was written, so a run that forgot the env var would silently
# publish the whole dashboard dated to that day: wrong leave, wrong "off today",
# wrong period boundaries, wrong diff date on every stage move. Nothing in QA can
# catch it, because a fully-populated page dated last week parses perfectly. The
# env vars stay so a rerun can reproduce an earlier day deliberately.
#
# Reapplied after 02dd92a, a template-only commit, restored the literals from a
# stale copy. Please keep this when editing the file from an older checkout: the
# 07:28 run on 31 Jul actually tripped it and first reported the wrong people on
# leave, because 27 Jul was a day Bianca was off and Eerik Saksi was not.
_now = datetime.datetime.now()
RUN_DATE = os.environ.get("JIGCAR_RUN_DATE") or _now.strftime("%Y-%m-%d")
RUN_STAMP = os.environ.get("JIGCAR_RUN_STAMP") or _now.strftime("%d %b %Y, %H:%M")
QUARTER_TARGET = 400000                      # Q3 2026. One editable constant per quarter.
REPS = ["Chris", "Luke", "James", "Bianca", "Elliott", "Rupert"]
IDX = {r: i for i, r in enumerate(REPS)}
PROG = ["New Lead", "Buy Signal", "Qualification", "Demo", "Proposal", "Trial", "Contracts", "Closed Won"]
# Shut-off states. "Contacted - no outcome" joins Nurture, Closed Lost and Churn: a deal
# entering it counts as shut off, per the account owner on 29 Jul 2026.
SHUT = ["Nurture", "Closed Lost", "Churn", "Contacted - no outcome"]

# The same rename map pull_attio.py applies, repeated here because the COMMITTED state
# store still holds the pre-rename title in stage_snapshot and stage_moves. The pull
# normalises today's data; this normalises yesterday's baseline, and the diff only stays
# continuous if both sides use one name. "Non-ICP" is deliberately absent from SHUT
# above: every path reads stages through this map, so the canonical title is the only
# one the classification needs to know about.
STAGE_ALIAS = {"Non-ICP": "Contacted - no outcome"}


def canon_stage(s):
    return STAGE_ALIAS.get(s, s)


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
    # Warranty provider, no deal on the domain, convened by a Jigcar colleague rather
    # than by the counterparty. Partner exploration, not a deal-advancing meeting.
    ("2026-07-28", "Jigcar meeting at Euston office"): "partner / channel exploration, no deal attached",
    # Groovin is the LinkedIn tool this dashboard itself reads from: a vendor
    # check-in, not a deal-advancing meeting.
    ("2026-07-30", "Elliott Perks and Guillaume Bruere"): "tooling / vendor (Groovin)",
    # Same basis as the 28 Jul Euston meeting: WSG is a warranty provider with no
    # deal on the domain, so a Co-Buyer demo to them is partner / channel
    # exploration until a deal exists. The moment one is created, meetings count.
    ("2026-07-31", "Jigcar Co-Buyer Demo - WSG"): "partner / channel exploration, no deal attached",
    # Consultant to Sphere Global, an overlapping software vendor. He is contractually
    # unable to work with Jigcar, the call covered a possible licensing partnership and
    # offered introductions, and no deal or company exists on the address. Adviser plus
    # partner exploration on both counts.
    ("2026-08-03", "Introduction: Jigcar/Jason Blood"): "adviser / partner exploration, no deal attached",
}
EXCL_PREFIX = [(d, t[:40]) for (d, t) in EXCLUDED_MEETINGS]

gran = json.load(open(f"{SP}/raw/granola.json"))
FIRST = {"chris.white@jigcar.com": "Chris", "luke.nogueira@jigcar.com": "Luke",
         "james.griffin@jigcar.com": "James", "bianca.monteiro@jigcar.com": "Bianca",
         "elliott@jigcar.com": "Elliott", "rupert@jigcar.com": "Rupert"}
meetings_daily = collections.defaultdict(z)
inc_count = exc_count = internal_count = 0

# One meeting can produce several notes, and they are grouped before anything is
# counted so a Jigcar attendee is credited once per meeting, never once per note.
#
# Two notes are the same meeting when they share a date and either
#   (a) the same title            - the usual case, one note per creator, or
#   (b) the same external participant set and a start within SAME_MEETING_MINS.
#
# (b) exists because on 3 Aug 2026 one Big Motoring World call was written up twice,
# as "Jigcar x Berkay: Data Sync" at 13:30 and "Big Motoring World" at 13:33, and
# title-only dedupe counted it as two meetings, crediting Rupert, James and Bianca
# twice each for one call. Across the whole quarter this rule merges that single pair
# and nothing else, so it removes a double count without collapsing two genuine
# meetings with one counterparty on one day. Attendees are credited from the UNION of
# the group, because two creators can list slightly different participants and taking
# only the first note would silently drop whoever the other one saw.
SAME_MEETING_MINS = 30
groups = []                              # [{date, mins, ext, titles, emails}]
for m in gran:
    em = m["emails"]
    if not em or all(e.endswith("@jigcar.com") for e in em):
        internal_count += 1
        continue
    ext = frozenset(e for e in em if not e.endswith("@jigcar.com"))
    mins = m.get("mins", -1)
    hit = None
    for g in groups:
        if g["date"] != m["date"]:
            continue
        if m["title"] in g["titles"]:
            hit = g
            break
        if g["ext"] == ext and mins >= 0 and g["mins"] >= 0 \
                and abs(mins - g["mins"]) <= SAME_MEETING_MINS:
            hit = g
            break
    if hit is None:
        groups.append({"date": m["date"], "mins": mins, "ext": ext,
                       "titles": {m["title"]}, "emails": set(em)})
    else:
        hit["titles"].add(m["title"])
        hit["emails"].update(em)

for g in groups:
    # A judged exclusion matches on any title the meeting was written up under, so a
    # second note under a different name cannot smuggle an excluded meeting back in.
    if any(g["date"] == d and t[:40] == p for t in g["titles"] for (d, p) in EXCL_PREFIX):
        exc_count += 1
        continue
    inc_count += 1
    for e in g["emails"]:
        if e in FIRST:
            meetings_daily[g["date"]][IDX[FIRST[e]]] += 1

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
# classify_emails.py owns the split window: it unions what earlier runs recorded with
# what this run paged, so a morning whose pages held no team sends does not collapse
# the window to null and publish an unlabelled split.
EMAIL_SPLIT_FROM = _em.get("split_from")
EMAIL_SPLIT_TO = _em.get("split_to")

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

# Whether every LinkedIn event this run could be attributed to a named rep. An event
# whose note body did not come back is EXCLUDED rather than guessed, so it is a floor
# on the person's real figure and the page has to say so.
_unatt = {k: v for k, v in (_inv.get("unattributed") or {}).items() if v}
_metric_gap = {k: v for k, v in _unatt.items() if not k.endswith("_note_unparsed")}
if _metric_gap:
    _parts = ", ".join(f"{v} {k}" for k, v in sorted(_metric_gap.items()))
    LI_UNATTRIBUTED_NOTE = (
        f"{_parts}: that many invitation records carry a timestamp but no usable sender, so "
        "they are excluded rather than guessed and the per-person figures are a floor by "
        "that many.")
elif _unatt:
    _parts = ", ".join(f"{v} {k}" for k, v in sorted(_unatt.items()))
    LI_UNATTRIBUTED_NOTE = (
        "none: every invitation sent and accepted carries a sender referenced by "
        f"workspace-member id, so nothing is guessed. ({_parts} in the note cross-check "
        "only, which does not affect any count.)")
else:
    LI_UNATTRIBUTED_NOTE = ("none: every invitation sent and accepted carries a sender referenced "
                            "by workspace-member id, so nothing is guessed")
LI_NOTE_COVERED_FROM = _inv.get("covered_from") or "2026-07-14"
LI_ATTRIBUTION = ("the Attio invitation record on the person, whose sender is a workspace-member "
                  "reference; no name parsing and no cadence-task proxy")

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
    # Normalise the stored baseline through the rename map before diffing. A renamed
    # stage is not a move, and comparing the old label against the new one would
    # manufacture a shut-off for every deal sitting in it.
    for _v in prev.values():
        _v["stage"] = canon_stage(_v.get("stage"))
    for _m in prior_moves:
        _m["from"], _m["to"] = canon_stage(_m.get("from")), canon_stage(_m.get("to"))
except FileNotFoundError:
    print("NOTE: no previous snapshot; this run seeds the baseline and the diff is empty")

# The published state at the repo root is the most recent record of what the routine
# actually told leadership. Only perf_flags is read from it: everything else must be
# recomputed from raw/ so the figures stay reproducible from this checkout alone.
try:
    with open(f"{SP}/dashboard_state.json") as fh:
        PUBLISHED_FLAGS = (json.load(fh).get("perf_flags") or {})
except (FileNotFoundError, ValueError):
    PUBLISHED_FLAGS = {}

STAGE_DIFF = []
for d in deals:
    before = prev.get(d["id"])
    if not before:
        continue                                  # new deal: counted as assigned, not progressed
    old_stage, new_stage = before["stage"], d["stage"]
    if old_stage == new_stage or not new_stage:
        continue
    # Every owner's move is RECORDED here, including the back-book owners. Only the
    # per-person scorecard columns are restricted to the six, and that restriction
    # belongs at attribution below, not here. Dropping the move outright hid a
    # £36,000 deal moving into Contracts from the move log and from "what moved",
    # and it also skipped the won-date stamp, so a back-book owner closing a deal
    # would never have been dated and would never have reached Q3 revenue.
    owner = d["owner"]
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
    # Per-person columns cover the scorecard six only, because those are the only
    # people with a column. The won-date stamp is deliberately OUTSIDE that gate:
    # closed-won revenue counts every owner, so a back-book close must be dated.
    if m["owner"] in IDX:
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
        elif s in ("Closed Lost", "Contacted - no outcome", "Churn") or s is None:
            out["Lost / no outcome"] += 1
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

# "Last week" is the previous calendar week, Monday to Sunday. It is wholly in the
# past, so unlike "this week" it is never capped and is always seven days. Built by
# stepping back from this week's Monday rather than by subtracting seven days from
# the run date, so it lands on week boundaries whatever day the routine runs.
lw_start = wk_start - datetime.timedelta(days=7)
lw_end = wk_start - datetime.timedelta(days=1)


def span_text(a, b):
    """Date span that stays correct across month and year boundaries."""
    if a.year != b.year:                      # e.g. 28 Dec 2026 - 3 Jan 2027
        return f"{dm(a)} {a.year} - {dm(b)} {b.year}"
    if a.month == b.month:
        return f"{a.day}-{b.day} {MONTHS[b.month - 1]}"
    return f"{dm(a)} - {dm(b)}"


lw_text = f"{span_text(lw_start, lw_end)} (7 days)"

# Trailing seven days. Not shown in the UI toggle: this is the basis for the Slack
# performance threshold, which the spec defines over a full week. Reusing the calendar
# week there would flag someone for a quiet Monday morning.
t7_start = d0 - datetime.timedelta(days=6)

ranges = {"today": [RUN_DATE, RUN_DATE],
          "yesterday": [str(d0 - datetime.timedelta(days=1))] * 2,
          "week": [str(wk_start), RUN_DATE],
          "lastweek": [str(lw_start), str(lw_end)],
          "month": [f"{RUN_DATE[:7]}-01", RUN_DATE],
          "quarter": ["2026-07-01", RUN_DATE],
          "trailing7": [str(t7_start), RUN_DATE]}
rangeText = {"today": dlabel(d0),
             "yesterday": dlabel(d0 - datetime.timedelta(days=1)),
             "week": wk_text,
             "lastweek": lw_text,
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

# ---------- movement: period-over-period deltas + the daily pipeline shape ----------
# Requested by the commercial director, 29 Jul 2026. Everything is computed here so
# the page only displays it. Two rules are load-bearing:
#   1. Completed days only. The 08:00 run must never compare a full day against two
#      waking hours, so day-on-day is the last two complete working days, and the
#      weekly column is this week THROUGH YESTERDAY against the same weekdays of
#      last week, like for like.
#   2. Coverage gating. A cell renders only when both periods sit fully inside the
#      metric's coverage window, else it carries the reason instead of a number. A
#      covered week against an uncovered one reads as growth that is actually the
#      coverage window opening, which is the exact lie this table must not tell.
STAGE_DIFF_FROM = "2026-07-27"          # first day the stage diff existed
Q_START = "2026-07-01"


def prev_working(day):
    day -= datetime.timedelta(days=1)
    while day.weekday() >= 5:
        day -= datetime.timedelta(days=1)
    return day


y1 = prev_working(d0)                   # last complete working day
y0 = prev_working(y1)

# closed-won £ by real close date. Quarter-only back-book seeds are excluded: their
# stored dates are placeholders, and a placeholder inside a daily comparison would
# invent a win on a day nobody closed anything.
won_by_day = collections.defaultdict(float)
for _d in closed_won:
    _wd = WON_DATES.get(_d["id"])
    if _wd and _d["id"] not in WON_DATE_QUARTER_ONLY:
        won_by_day[_wd] += _d["value"]


def series_total(key, a, b):
    if key == "wonGBP":
        return round(sum(v for k, v in won_by_day.items() if str(a) <= k <= str(b)))
    return sum(sum(v) for k, v in (daily.get(key) or {}).items() if str(a) <= k <= str(b))


MOVE_METRICS = [
    # (daily key, label, covered from, valence: 1 = more is better, 0 = neutral, gbp)
    ("deals",      "Deals created",      Q_START,         0, False),
    ("progressed", "Deals progressed",   STAGE_DIFF_FROM, 1, False),
    ("shutoff",    "Deals shut off",     STAGE_DIFF_FROM, 0, False),
    ("wonGBP",     "Closed won",         Q_START,         1, True),
    ("meetings",   "Sales meetings",     Q_START,         1, False),
    ("calls",      "Calls",              _calls["covered_from"] or RUN_DATE, 1, False),
    ("emailsDeal", "Emails (deal)",      EMAIL_SPLIT_FROM or RUN_DATE,       1, False),
    ("liConnDeal", "LI requests (deal)", LI_NOTE_COVERED_FROM,               1, False),
    ("tasks",      "Tasks completed",    Q_START,         1, False),
]

_wtd_ok = y1 >= wk_start                # false on a Monday: no completed day this week
_swlw_a = wk_start - datetime.timedelta(days=7)
_swlw_b = _swlw_a + (y1 - wk_start) if _wtd_ok else None
_pfw_a = lw_start - datetime.timedelta(days=7)
_pfw_b = lw_start - datetime.timedelta(days=1)

MOVE_COLS = [
    {"key": "dod", "label": "Day on day",
     "curText": dlabel(y1), "prevText": dlabel(y0),
     "cur": (y1, y1), "prev": (y0, y0)},
    {"key": "wow", "label": "Week to date, like for like",
     "curText": (f"Mon-{DAYS[y1.weekday()]} this week" if _wtd_ok else "no completed day yet"),
     "prevText": "same weekdays last week",
     "cur": (wk_start, y1) if _wtd_ok else None,
     "prev": (_swlw_a, _swlw_b) if _wtd_ok else None},
    {"key": "fw", "label": "Last full week vs prior",
     "curText": span_text(lw_start, lw_end), "prevText": span_text(_pfw_a, _pfw_b),
     "cur": (lw_start, lw_end), "prev": (_pfw_a, _pfw_b)},
]

movement_rows = []
for _key, _label, _from, _val, _gbp in MOVE_METRICS:
    cells = []
    for _c in MOVE_COLS:
        if _c["cur"] is None:
            cells.append({"na": "no completed working day this week yet"})
        elif str(_c["prev"][0]) < _from:
            cells.append({"na": f"coverage began {_from}, after this comparison window opens"})
        else:
            cells.append({"cur": series_total(_key, *_c["cur"]),
                          "prev": series_total(_key, *_c["prev"])})
    movement_rows.append({"key": _key, "label": _label, "valence": _val, "gbp": _gbp,
                          "coveredFrom": _from, "cells": cells})

# ---------- the What moved tab: three short periods, per-rep, VP-of-sales view ----
# Deliberately short-range (yesterday / week to date / last week) so the view never
# reaches back far enough to be noise. Yesterday means the last COMPLETE working
# day, so a Monday shows Friday. Week to date includes today and says so instead of
# pretending to be comparable; its KPI tiles carry a progress note, never a delta.


def wd_count(a, b):
    n, cur = 0, a
    while cur <= b:
        if cur.weekday() < 5:
            n += 1
        cur += datetime.timedelta(days=1)
    return n


KPI_METRICS = [("progressed", "Deals progressed", STAGE_DIFF_FROM, 1),
               ("shutoff", "Shut off", STAGE_DIFF_FROM, 0),
               ("wonGBP", "Closed won", Q_START, 1),
               ("deals", "New deals", Q_START, 0),
               ("meetings", "Sales meetings", Q_START, 1)]

_period_defs = [
    {"key": "yesterday", "label": dlabel(y1), "a": y1, "b": y1,
     "pa": y0, "pb": y0, "prevLabel": dlabel(y0), "complete": True},
    {"key": "week", "label": f"Week to date, {span_text(wk_start, d0)}", "a": wk_start, "b": d0,
     "pa": None, "pb": None, "prevLabel": None, "complete": False},
    {"key": "lastweek", "label": f"Last week, {span_text(lw_start, lw_end)}", "a": lw_start, "b": lw_end,
     "pa": _pfw_a, "pb": _pfw_b, "prevLabel": span_text(_pfw_a, _pfw_b), "complete": True},
]

mov_periods = []
for _p in _period_defs:
    a, b = str(_p["a"]), str(_p["b"])
    kpi = {}
    for _key, _label, _from, _val in KPI_METRICS:
        # A period that opens before the metric's coverage gets NO number at all. A
        # tile reading 0 for a week the stage diff did not exist would say "nothing
        # progressed" when the truth is "nothing was measured".
        if a < _from:
            kpi[_key] = {"naValue": f"not measured: coverage began {_from}", "valence": _val}
            continue
        cell = {"cur": series_total(_key, a, b), "valence": _val}
        if _p["pa"] is None:
            cell["progress"] = f"{wd_count(wk_start, d0)} of 5 working days, today still in flight"
        elif str(_p["pa"]) < _from:
            cell["na"] = f"no comparison: coverage began {_from}"
        else:
            cell["prev"] = series_total(_key, str(_p["pa"]), str(_p["pb"]))
        kpi[_key] = cell
    mov_periods.append({
        "key": _p["key"], "label": _p["label"], "range": [a, b],
        "prevLabel": _p["prevLabel"], "complete": _p["complete"],
        "workdays": wd_count(_p["a"], _p["b"]),
        "attendance": {r: working_days(r, a, b) for r in REPS},
        "kpi": kpi})

# Won deals with an ISO date so the tab can place them inside a period. Quarter-only
# back-book seeds stay excluded: a placeholder date must never surface as a day.
won_deals_dated = [{"name": _d["name"], "arr": _d["value"], "owner": _d["owner"],
                    "date": WON_DATES[_d["id"]]}
                   for _d in closed_won
                   if WON_DATES.get(_d["id"]) and _d["id"] not in WON_DATE_QUARTER_ONLY]

movement = {"cols": [{k: c[k] for k in ("key", "label", "curText", "prevText")} for c in MOVE_COLS],
            "rows": movement_rows,
            "periods": mov_periods,
            "wonDeals": won_deals_dated,
            "diffFrom": STAGE_DIFF_FROM,
            "note": ("Completed working days only, so today never appears part-built. Deals "
                     "progressed and shut off are observed by the stage diff, which has existed "
                     f"since {STAGE_DIFF_FROM}; nothing earlier was measured and nothing is "
                     "backfilled. Closed won is by real close date and counts dated wins only. "
                     "The move log above lists every owner including the back book, while this "
                     "table's progressed and shut off rows count the six scorecard people to "
                     "match the scorecard columns, so the log can legitimately total one or two "
                     "higher on a day a back-book owner moved a deal.")}

# Daily pipeline shape: count and value per stage, one row per run day, carried
# forward. This is what unlocks "Qualification grew £84k this week" once a couple of
# weeks of history exist. It cannot be backfilled, so it starts accruing today.
prev_shape = (_ps.get("stage_shape") or {}) if prev else {}
_today_shape = {}
for _d in deals:
    _e = _today_shape.setdefault(_d["stage"] or "None", [0, 0.0])
    _e[0] += 1
    _e[1] += _d["value"]
stage_shape = {**prev_shape, RUN_DATE: _today_shape}
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
    "li_message_basis": (
        "LinkedIn messages count individual messages sent by that person, each dated by its own "
        f"timestamp inside the Groovin note, not by the date the note was created. "
        f"{sum(_msg.get('backfilled_excluded', {}).values())} message(s) in the synced threads "
        "predate July and are excluded rather than credited to the day Groovin first synced them. "
        "Every conversation writes a person-side and a company-side note with identical bodies, so "
        "each message is counted once. Coverage before 21 Jul is a floor: it only includes threads "
        "Groovin has since synced."),
    "tasks_dated_by": "completed_at from the Attio tasks API",
    "li_connects_attributed_by": LI_ATTRIBUTION,
    # Built from the pull, never asserted. This read "none: every invitation ... is
    # attributed" as a frozen sentence, and on 3 Aug 2026 one invitation body failed
    # to fetch and went unattributed, so the page would have claimed full attribution
    # while quietly dropping an event. A statement about the data has to come from the
    # data.
    "li_connect_gap": LI_UNATTRIBUTED_NOTE,
    "li_accepted_note": ("connections made lag the invitation that earned them, often by weeks, so a high "
                         "accepted count reflects earlier outreach rather than work done in the period"),
    # Two independent Attio sources for the same events, published side by side rather
    # than merged, because merging them meant matching a name parsed out of prose
    # against a record's full_name and that invented events out of punctuation.
    #
    # An earlier build of this note asserted that every LinkedIn column was a floor,
    # on the strength of comparing 122 pending invitations from the Groovin connector
    # against 61 recorded in Attio. That comparison was invalid and the claim is
    # withdrawn: the Groovin connector authenticates as ONE person's own LinkedIn
    # account, so it says nothing about a colleague, and LinkedIn dates older pending
    # invitations only to the week, which bunched older outreach into the window. The
    # two Attio sources agree to within 8 events across five weeks, which is the real
    # measure of confidence here.
    "li_source_note": (
        "LinkedIn invitations sent and accepted are counted from the invitation record on the Attio "
        "person, which carries the real send time and names the sender by workspace-member id rather "
        "than by parsing prose. That record holds only the LAST invitation per contact, so when a "
        "contact is invited again the earlier sender loses the credit; the person-side Groovin notes "
        "are therefore unioned in, joined on the person record id so no name matching is involved. "
        "This quarter that recovers {rec} invitations sent and {reca} accepted that the record alone "
        "had overwritten, giving {tot} sent in total. Messages come from the chat notes, which date "
        "each message individually."
    ).format(rec=_inv.get("reconciliation", {}).get("sent", {}).get("recovered_from_notes", 0),
             reca=_inv.get("reconciliation", {}).get("accepted", {}).get("recovered_from_notes", 0),
             tot=sum(sum(v) for v in li_conn_all.values())),
    "calls_source": (f"Allo per-seat call records ({_calls['total']} calls "
                     f"{_calls['covered_from']} to {_calls['covered_to']}); Rupert has no Allo account, "
                     "so his calls are always 0 and his seat reads na"),
    # Machine-readable so the period notes can compare a selected range against it.
    # Parsing the date back out of calls_source prose would break the moment the
    # wording changed, and a silently wrong coverage claim is worse than none.
    "calls_covered_from": _calls["covered_from"],
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
         # history to escalate on the third consecutive day rather than repeat itself.
         # Merged from BOTH the diff baseline and the currently published state. The
         # baseline is yesterday's snapshot, so on a same-day re-run it does not yet
         # know about a flag an earlier run wrote today; taking only the baseline
         # dropped that flag and reset the streak, which is the exact failure the
         # spec warns about. The published state is the later record, so it wins.
         "perf_flags": {**(_ps.get("perf_flags", {}) if prev else {}), **PUBLISHED_FLAGS},
         "leave": leave_summary,
         "off_today": off_today,
         "attendance": attendance,
         "stage_shape": stage_shape,
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
           "movement": movement,
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
