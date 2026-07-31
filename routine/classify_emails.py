# -*- coding: utf-8 -*-
"""Tally sent emails per person per day, de-duped across mailbox copies.

Attio has no public emails REST endpoint (/v2/emails 404s), so the period is
paged through the MCP metadata search. Oversized pages overflow to a file and the
path is parsed from disk rather than read into context; a page that comes back
inline is persisted through the `extra` hook instead. Either way the record is on
disk before it is counted.

De-dupe key is (sender, subject, sent_at). The same email syncs into several
connected mailboxes, so without that key a note copied to three mailboxes counts
three times. Apollo sends route through these same mailboxes, so Apollo is never
counted separately.

Coverage is the point of this module as much as the tally is. Only days this run
actually paged are recomputed; earlier days are carried forward from the previous
state so the store accumulates a day per run, and the window is written out so the
dashboard labels it. A day outside the window must read as a floor, never a zero.
"""
import re, json, glob, os, collections, sys, datetime

SP = os.environ.get("JIGCAR_SP") or os.path.dirname(os.path.abspath(__file__))
REPS = ["Chris", "Luke", "James", "Bianca", "Elliott", "Rupert"]
TEAM = {"chris.white@jigcar.com": "Chris", "luke.nogueira@jigcar.com": "Luke",
        "james.griffin@jigcar.com": "James", "bianca.monteiro@jigcar.com": "Bianca",
        "elliott@jigcar.com": "Elliott", "rupert@jigcar.com": "Rupert"}
RANK = {"open": 3, "won": 2, "closed": 1}
STATES = ["open", "won", "closed", "none", "internal"]
# The first day this run paged continuously. Days before it are carried forward from
# the previous state; days from it onward are rebuilt from the pages on disk. Set it
# to the OLDEST day the run actually paged end to end, and never earlier: a day at or
# after FRESH_FROM that no page covers is neither carried nor rebuilt, so it does not
# fall back to the stored figure, it disappears from the store altogether.
# The default is today for that reason. It used to be a literal, frozen at the day the
# file was written, so a run that forgot the env var would have silently deleted every
# stored day from that literal up to yesterday. Defaulting to today is the conservative
# failure: at worst this run under-covers today, and no history is lost.
FRESH_FROM = os.environ.get("JIGCAR_EMAIL_FRESH_FROM") or datetime.date.today().isoformat()

dom = json.load(open(f"{SP}/raw/domain_deal.json"))


def classify(recipients):
    """Strongest state across the external recipients wins.

    A note to a live prospect that copies a vendor still reads as live deal.
    """
    ext = [x.split("@")[-1].lower().strip() for x in recipients.split(",")
           if "@" in x and not x.strip().lower().endswith("@jigcar.com")]
    best = None
    for d in ext:
        v = dom.get(d)
        if v and (best is None or RANK[v["state"]] > RANK[best["state"]]):
            best = v
    if best:
        return best["state"]
    return "internal" if not ext else "none"


sends = {}
files = sorted(glob.glob(f"{SP}/mail/*.txt"))
for f in files:
    for blk in open(f, encoding="utf-8").read().split("- mailbox_id:")[1:]:
        def g(p):
            m = re.search(p, blk, re.M)
            return m.group(1).strip().strip('"') if m else None
        s = (g(r"^\s*sender:\s*(.+)$") or "").lower()
        sent = g(r"^\s*sent_at:\s*(.+)$")
        if s and sent:
            sends[(s, g(r"^\s*subject_line:\s*(.+)$"), sent)] = g(r"^\s*recipients\[\d+\]:\s*(.*)$") or ""

extra_files = sorted(glob.glob(f"{SP}/raw/mail_*.json"))
# Days a page states it covered end to end, even if nothing team-sent turned up in
# them. A run at 08:00 routinely pages a day with no team sends yet, and that day IS
# classified: everything sent in it (nothing) has been read. Without this the day
# vanishes from the split window and the page would label its own coverage as null.
paged_days = set()
paged_bounds = []
for ef in extra_files:
    _p = json.load(open(ef))
    paged_days.update(_p.get("_paged_days") or [])
    paged_bounds += [b for b in (_p.get("_paged_from"), _p.get("_paged_to")) if b]
    for e in _p["sends"]:
        sends[(e["sender"].lower(), e["subject"], e["sent"])] = e["recipients"]


def z():
    return [0] * 6


tot_daily = collections.defaultdict(z)
split_daily = collections.defaultdict(lambda: {s: [0] * 6 for s in STATES})
for (s, subj, sent), rc in sends.items():
    if s not in TEAM:
        continue
    day = sent[:10]
    # Only days this run paged END TO END are recomputed. A page that stops
    # mid-morning leaves its oldest day partial, and merging that over the
    # carried-forward full day silently replaces a complete count with a
    # smaller one. Drop it and let the carry-forward stand.
    if day < FRESH_FROM:
        continue
    i = REPS.index(TEAM[s])
    tot_daily[day][i] += 1
    split_daily[day][classify(rc)][i] += 1

# Carry forward days this run did not page. Rebuilding the store from only
# today's pull would silently drop last week and read as a quiet period.
carried = {}
prev_split_from = prev_split_to = None
try:
    prev = json.load(open(f"{SP}/raw/prev_state.json"))
    pdm = prev.get("daily_metrics", {})
    for day, row in (pdm.get("emails") or {}).items():
        if day < FRESH_FROM:
            carried[day] = row
    prev_deal = {d: v for d, v in (pdm.get("emailsDeal") or {}).items() if d < FRESH_FROM}
    prev_cust = {d: v for d, v in (pdm.get("emailsCust") or {}).items() if d < FRESH_FROM}
    _pc = prev.get("coverage") or {}
    prev_split_from, prev_split_to = _pc.get("email_split_from"), _pc.get("email_split_to")
except FileNotFoundError:
    prev_deal, prev_cust = {}, {}

# A paged day with no team sends is a real zero, not an absence. Write it explicitly
# so the period totals read 0 against a stated coverage window rather than dropping
# the day and leaving "covered but empty" indistinguishable from "never pulled".
zeros = {d: [0] * 6 for d in paged_days if d >= FRESH_FROM}
by_day = dict(sorted({**carried, **zeros, **{d: v for d, v in tot_daily.items()}}.items()))
deal = dict(sorted({**prev_deal, **zeros, **{d: v["open"] for d, v in split_daily.items()}}.items()))
cust = dict(sorted({**prev_cust, **zeros, **{d: v["won"] for d, v in split_daily.items()}}.items()))

# The split window is the union of what previous runs recorded and what this run
# paged. Deriving it from split_by_day alone made it collapse to null on a morning
# whose pages held no team sends, which would have published an unlabelled split.
_split_days = sorted(set(split_daily) | set(zeros)
                     | {d for d in (prev_split_from, prev_split_to) if d})
split_from = min(_split_days) if _split_days else None
split_to = max(_split_days) if _split_days else None

# The paged window is what was READ, not what was found. Prefer the range each page
# declares: deriving it from the sends reports the first and last team send, which on
# a morning whose first send was at 08:07 understated a page that ran from midnight,
# and reported no window at all when a page held no team sends.
stamps = sorted(paged_bounds) or sorted(k[2] for k in sends)
out = {"by_day": by_day, "deal": deal, "cust": cust,
       "split_by_day": {d: v for d, v in sorted(split_daily.items())},
       "split_from": split_from, "split_to": split_to,
       "paged_days": sorted(paged_days),
       "fresh_from": FRESH_FROM,
       "pulled_from": stamps[0] if stamps else None,
       "pulled_to": stamps[-1] if stamps else None,
       "carried_days": sorted(carried),
       "emails_seen": len(sends),
       "domains_resolving": len(dom),
       "pages": [os.path.basename(f) for f in files] + [os.path.basename(f) for f in extra_files]}
json.dump(out, open(f"{SP}/raw/emails.json", "w"), indent=1)

print("=== EMAIL PULL ===")
print(f"records on disk: {len(sends)} | pages: {out['pages']}")
print(f"pulled window: {out['pulled_from']} -> {out['pulled_to']}")
print(f"recomputed from {FRESH_FROM}; carried forward: {out['carried_days']}")
print(f"{'day':12}" + "".join(f"{r:>9}" for r in REPS) + "   (total sent)")
for d, v in by_day.items():
    tag = "" if d in tot_daily else ("  paged, no team sends" if d in zeros else "  carried")
    print(f"{d:12}" + "".join(f"{x:>9}" for x in v) + tag)
print("\n--- deal split, only for days actually classified ---")
for d, v in sorted(split_daily.items()):
    for i, r in enumerate(REPS):
        t = sum(v[s][i] for s in STATES)
        if not t:
            continue
        print(f"{d} {r:8} {t:3} sent | live deal {v['open'][i]:2} | customer {v['won'][i]:2} | "
              f"closed {v['closed'][i]:2} | no deal {v['none'][i]:2} | internal {v['internal'][i]:2}")
