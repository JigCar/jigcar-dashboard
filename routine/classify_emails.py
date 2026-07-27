# -*- coding: utf-8 -*-
"""Split sent emails by what the recipient is to us: live deal, customer, or neither.

A raw sent count says how busy someone looks, not whether the work touched
pipeline. Bianca sends a lot because she runs onboarding, and almost all of it
goes to existing accounts, which is exactly her job. A single number hides that.

The join is recipient domain -> Attio company -> that company's best deal state:
  live deal  an open deal, New Lead through Contracts
  customer   Closed Won, so an existing account rather than pipeline
  closed     Closed Lost, Churn or Non-ICP
  none       an external address with no deal behind it (vendors, advisers, admin)
  internal   jigcar.com only

Only the strongest state counts when an email has several external recipients,
so a note to a live prospect that copies a vendor still reads as live deal.

Coverage is stated, never assumed. The split only covers emails whose recipient
list this run actually pulled, and that window is written into the output so the
dashboard can label it rather than implying the whole period is classified.
"""
import re, json, glob, os, collections

SP = os.environ.get("JIGCAR_SP") or os.path.dirname(os.path.abspath(__file__))
REPS = ["Chris", "Luke", "James", "Bianca", "Elliott", "Rupert"]
TEAM = {"chris.white@jigcar.com": "Chris", "luke.nogueira@jigcar.com": "Luke",
        "james.griffin@jigcar.com": "James", "bianca.monteiro@jigcar.com": "Bianca",
        "elliott@jigcar.com": "Elliott", "rupert@jigcar.com": "Rupert"}
RANK = {"open": 3, "won": 2, "closed": 1}
STATES = ["open", "won", "closed", "none", "internal"]

dom = json.load(open(f"{SP}/raw/domain_deal.json"))


def classify(recipients):
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


# (sender, subject, sent_at) is the same de-dupe key the tally uses, so an email
# synced to several mailboxes is counted once here too.
sends = {}

for f in sorted(glob.glob(f"{SP}/mail/*.txt")):
    for blk in open(f, encoding="utf-8").read().split("- mailbox_id:")[1:]:
        def g(p):
            m = re.search(p, blk, re.M)
            return m.group(1).strip().strip('"') if m else None
        s = (g(r"^\s*sender:\s*(.+)$") or "").lower()
        sent = g(r"^\s*sent_at:\s*(.+)$")
        if s and sent:
            sends[(s, g(r"^\s*subject_line:\s*(.+)$"), sent)] = g(r"^\s*recipients\[\d+\]:\s*(.*)$") or ""

extra = f"{SP}/raw/mail_morning_27jul.json"
if os.path.exists(extra):
    for e in json.load(open(extra))["sends"]:
        sends[(e["sender"].lower(), e["subject"], e["sent"])] = e["recipients"]

daily = collections.defaultdict(lambda: {s: [0] * 6 for s in STATES})
for (s, subj, sent), rc in sends.items():
    if s not in TEAM:
        continue
    daily[sent[:10]][classify(rc)][REPS.index(TEAM[s])] += 1

stamps = sorted(k[2] for k in sends)
out = {"by_day": {d: v for d, v in sorted(daily.items())},
       "covered_from": stamps[0] if stamps else None,
       "covered_to": stamps[-1] if stamps else None,
       "emails_seen": len(sends),
       "domains_resolving": len(dom)}
json.dump(out, open(f"{SP}/raw/email_split.json", "w"), indent=1)

print(f"emails with recipients: {len(sends)} | window {out['covered_from']} -> {out['covered_to']}")
print(f"domains resolving to a deal: {len(dom)}")
for d, v in sorted(daily.items()):
    print(f"\n{d}")
    for i, r in enumerate(REPS):
        tot = sum(v[s][i] for s in STATES)
        if not tot:
            continue
        print(f"  {r:8} {tot:3} sent | live deal {v['open'][i]:2} | customer {v['won'][i]:2} | "
              f"closed {v['closed'][i]:2} | no deal {v['none'][i]:2} | internal {v['internal'][i]:2}")
