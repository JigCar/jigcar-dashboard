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
import re, json, glob, os, collections, sys

SP = os.environ.get("JIGCAR_SP") or os.path.dirname(os.path.abspath(__file__))
REPS = ["Chris", "Luke", "James", "Bianca", "Elliott", "Rupert"]
TEAM = {"chris.white@jigcar.com": "Chris", "luke.nogueira@jigcar.com": "Luke",
        "james.griffin@jigcar.com": "James", "bianca.monteiro@jigcar.com": "Bianca",
        "elliott@jigcar.com": "Elliott", "rupert@jigcar.com": "Rupert"}
RANK = {"open": 3, "won": 2, "closed": 1}
STATES = ["open", "won", "closed", "none", "internal"]
# Days this run paged continuously. Anything outside is carried forward, not zeroed.
FRESH_FROM = os.environ.get("JIGCAR_EMAIL_FRESH_FROM", "2026-07-27")

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
for ef in extra_files:
    for e in json.load(open(ef))["sends"]:
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
try:
    prev = json.load(open(f"{SP}/raw/prev_state.json"))
    pdm = prev.get("daily_metrics", {})
    for day, row in (pdm.get("emails") or {}).items():
        if day < FRESH_FROM:
            carried[day] = row
    prev_deal = {d: v for d, v in (pdm.get("emailsDeal") or {}).items() if d < FRESH_FROM}
    prev_cust = {d: v for d, v in (pdm.get("emailsCust") or {}).items() if d < FRESH_FROM}
except FileNotFoundError:
    prev_deal, prev_cust = {}, {}

by_day = dict(sorted({**carried, **{d: v for d, v in tot_daily.items()}}.items()))
deal = dict(sorted({**prev_deal, **{d: v["open"] for d, v in split_daily.items()}}.items()))
cust = dict(sorted({**prev_cust, **{d: v["won"] for d, v in split_daily.items()}}.items()))

stamps = sorted(k[2] for k in sends)
out = {"by_day": by_day, "deal": deal, "cust": cust,
       "split_by_day": {d: v for d, v in sorted(split_daily.items())},
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
    tag = "" if d in tot_daily else "  carried"
    print(f"{d:12}" + "".join(f"{x:>9}" for x in v) + tag)
print("\n--- deal split, only for days actually classified ---")
for d, v in sorted(split_daily.items()):
    for i, r in enumerate(REPS):
        t = sum(v[s][i] for s in STATES)
        if not t:
            continue
        print(f"{d} {r:8} {t:3} sent | live deal {v['open'][i]:2} | customer {v['won'][i]:2} | "
              f"closed {v['closed'][i]:2} | no deal {v['none'][i]:2} | internal {v['internal'][i]:2}")
