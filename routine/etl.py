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

# ---------- calls (Allo team analytics, per seat) ----------
# July total 16, confirmed against allo_get_team_analytics for 1-27 Jul:
# Elliott 7, James 4, Luke 4, Chris 1, Bianca 0. Rupert has no Allo seat.
# A 24-27 Jul query returned 0 calls, so the book closes at 23 Jul.
calls_daily = {
    "2026-07-21": [1, 0, 0, 0, 3, 0],
    "2026-07-22": [0, 1, 1, 0, 4, 0],
    "2026-07-23": [0, 3, 3, 0, 0, 0],
}

# ---------- emails (Attio multi-mailbox search, de-duped by sender+subject+sent_at) ----------
# Covered continuously from 2026-07-24 07:53 to the run stamp. Days before that are
# not covered by this run and are rendered as a labelled floor, never as zero activity.
emails_daily = {
    "2026-07-24": [16, 0, 0, 2, 6, 6],
    "2026-07-25": [1, 0, 0, 0, 1, 0],
    "2026-07-26": [0, 0, 0, 0, 1, 0],
    "2026-07-27": [1, 0, 0, 8, 10, 2],
}
EMAIL_COVERED_FROM = "2026-07-24"

# ---------- tasks completed (dated by completed_at from the Attio tasks API) ----------
tasks_daily = {
    "2026-07-07": [0, 0, 0, 1, 0, 0],
    "2026-07-22": [3, 0, 0, 0, 0, 0],
    "2026-07-23": [0, 0, 0, 1, 0, 0],
    "2026-07-24": [14, 0, 0, 0, 0, 0],
    "2026-07-27": [2, 0, 0, 0, 0, 0],
}

# ---------- LinkedIn ----------
# Connects: Attio's "LinkedIn invitation sent" notes carry no rep and no owner, so they
# are not per-person attributable from Attio alone. Attributed here via the cadence
# Touch-1 (a completed connect task on the owner's deal), which is the spec's fallback
# until Groovin per-seat data is wired. Every such task is linked to a deal, so the
# deal-associated figure equals the total.
li_conn_all = {
    "2026-07-22": [1, 0, 0, 0, 0, 0],
    "2026-07-23": [0, 0, 0, 1, 0, 0],
    "2026-07-24": [10, 0, 0, 0, 0, 0],
    "2026-07-27": [1, 0, 0, 0, 0, 0],
}
li_conn_deal = {k: list(v) for k, v in li_conn_all.items()}
LI_CONN_SENT_EVENTS = 14      # Groovin "invitation sent" notes, 21-27 Jul, rep unknown
LI_CONN_ATTRIBUTED = 13       # attributed via Touch-1; the gap is stated in coverage

# Messages: the rep is named in the chat-note title, so these are attributable.
# Counted once per person/company note pair.
li_msg_all = {
    "2026-07-21": [0, 0, 0, 0, 5, 0],
    "2026-07-22": [0, 0, 1, 0, 2, 0],
    "2026-07-23": [0, 0, 0, 0, 1, 0],
    "2026-07-24": [0, 1, 0, 0, 2, 0],
    "2026-07-27": [0, 0, 1, 0, 0, 0],
}
LI_NOTE_COVERED_FROM = "2026-07-21"

# deal-associated messages: resolved in code from the chat note's company -> deal join.
li_msg_deal = json.load(open(f"{SP}/raw/li_msg_deal.json"))

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
         "liMsgAll": li_msg_all, "liMsgDeal": li_msg_deal}

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
connectivity = json.load(open(f"{SP}/raw/connectivity.json"))
connectivity["updated"] = RUN_STAMP

# ---------- time ranges ----------
d0 = datetime.date(*[int(x) for x in RUN_DATE.split("-")])
DAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
MONTHS_FULL = ["January", "February", "March", "April", "May", "June", "July",
               "August", "September", "October", "November", "December"]


def dlabel(d):
    return f"{DAYS[d.weekday()]} {d.day} {MONTHS[d.month - 1]}"


wk_start = d0 - datetime.timedelta(days=6)
ranges = {"today": [RUN_DATE, RUN_DATE],
          "yesterday": [str(d0 - datetime.timedelta(days=1))] * 2,
          "week": [str(wk_start), RUN_DATE],
          "month": [f"{RUN_DATE[:7]}-01", RUN_DATE],
          "quarter": ["2026-07-01", RUN_DATE]}
rangeText = {"today": dlabel(d0),
             "yesterday": dlabel(d0 - datetime.timedelta(days=1)),
             "week": f"{wk_start.day}-{d0.day} {MONTHS[d0.month - 1]} (7 days)",
             "month": f"{MONTHS_FULL[d0.month - 1]}, 1-{d0.day}",
             "quarter": f"Q3 to date, 1-{d0.day} {MONTHS[d0.month - 1]}"}

coverage = {
    "progressed_shutoff": "measured by diffing this run's stage snapshot against the previous run's",
    "stage_diff": STAGE_DIFF,
    "stage_moves_accumulated": len(ALL_MOVES),
    "email_covered_from": EMAIL_COVERED_FROM,
    "email_note": "continuous from 24 Jul 07:53; earlier July days are not covered by this run and read as a floor",
    "email_rupert": "Rupert's own mailbox is not connected, so his sends are only visible where a teammate was a recipient",
    "linkedin_notes_covered_from": LI_NOTE_COVERED_FROM,
    "tasks_dated_by": "completed_at from the Attio tasks API",
    "li_connects_attributed_by": "cadence Touch-1 completed connect task on the owner's deal",
    "li_connect_gap": (f"Groovin logged {LI_CONN_SENT_EVENTS} invitation-sent events 21-27 Jul but the notes carry "
                       f"no rep; {LI_CONN_ATTRIBUTED} are attributed via Touch-1 tasks"),
    "calls_source": "Allo team analytics per seat; Rupert has no Allo account",
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
           "stageMoves": ALL_MOVES}
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
for q, a in archives.items():
    print(q, "created", a["createdCount"], "pipeline", a["createdPipeline"],
          "won", len(a["closedWon"]), "outcomes", a["outcomes"])
