# -*- coding: utf-8 -*-
"""Attribute LinkedIn activity per person from the Groovin notes in Attio.

The rep is in the note BODY for invitations, not the title. Reading only the
title has caused a real mis-attribution, so bodies are fetched and parsed:

  sent      body "from <Rep> to <Contact>",  title is the bare
            string "LinkedIn invitation sent" with no rep in it at all
  accepted  body "<Rep> is now connected with <Contact>."
  messages  rep is in the TITLE: "1:1 LinkedIn chat | <Contact> with <Rep>"

Never fall back to counting cadence Touch-1 tasks. That proxy credits whoever was
assigned the task rather than whoever sent the invitation, and it was wrong by a
wide margin: one person read 12 connects against 3 actually sent, another 5
against 32.

Every event writes a person-side and a company-side note, so events are deduped
on (date, rep, contact, kind). The company side supplies the deal join.
"""
import json, os, re, collections, urllib.request, concurrent.futures as cf

SP = os.environ.get("JIGCAR_SP") or os.path.dirname(os.path.abspath(__file__))
GROOVIN = "c020395f-1e1e-4a88-9d95-3c63937a06f8"
REPS = ["Chris", "Luke", "James", "Bianca", "Elliott", "Rupert"]
IDX = {r: i for i, r in enumerate(REPS)}
# Groovin writes full names; map to the scorecard first names.
REP_ALIAS = {
    "chris white": "Chris", "chris": "Chris",
    "luke nogueira": "Luke", "luke": "Luke",
    "james griffin": "James", "james": "James",
    "bianca monteiro": "Bianca", "bianca": "Bianca",
    "elliott perks": "Elliott", "elliott": "Elliott",
    "rupert wood": "Rupert", "rupert": "Rupert",
}
FROM = "2026-07-01"


def rep_of(raw):
    if not raw:
        return None
    k = re.sub(r"\s+", " ", raw).strip().lower().rstrip(".")
    if k in REP_ALIAS:
        return REP_ALIAS[k]
    # "Elliott P", "James Gri" - Groovin truncates in some titles
    for alias, name in REP_ALIAS.items():
        if " " in alias and (alias.startswith(k) or k.startswith(alias.split()[0] + " ")):
            return name
    return REP_ALIAS.get(k.split()[0]) if k else None


notes = json.load(open(f"{SP}/raw/notes.json"))
companies = json.load(open(f"{SP}/raw/companies.json"))
domain_deal = json.load(open(f"{SP}/raw/domain_deal.json"))
person_deal = json.load(open(f"{SP}/raw/person_deal.json"))

gro = [n for n in notes if n["actor"] == GROOVIN and n["created"] >= FROM]
inv = [n for n in gro if n["title"] in ("LinkedIn invitation sent", "LinkedIn invitation accepted")]
chats = [n for n in gro if n["title"].startswith("1:1 LinkedIn chat")]


def fetch_body(n):
    try:
        with urllib.request.urlopen(f"https://api.attio.com/v2/notes/{n['id']}", timeout=60) as fh:
            d = json.loads(fh.read().decode()).get("data", {})
        return {**n, "body": re.sub(r"\s+", " ", (d.get("content_plaintext") or "")).strip()}
    except Exception as exc:                       # a single failed body is a gap, not a guess
        return {**n, "body": "", "error": str(exc)}


with cf.ThreadPoolExecutor(max_workers=8) as ex:
    inv_full = list(ex.map(fetch_body, inv))
json.dump(inv_full, open(f"{SP}/raw/invite_notes.json", "w"), indent=0)

SENT_RE = re.compile(r"\bfrom\s+([A-Z][A-Za-z'\-]*(?:\s+[A-Z][A-Za-z'\-]*)*)\s+to\s+"
                     r"([A-Z][A-Za-z'\-.]*(?:\s+[A-Z][A-Za-z'\-.]*)*)")
ACC_RE = re.compile(r"^([A-Z][A-Za-z'\-]*(?:\s+[A-Z][A-Za-z'\-]*)*)\s+is now connected with\s+"
                    r"([A-Z][A-Za-z'\-.]*(?:\s+[A-Z][A-Za-z'\-.]*)*)")
CHAT_RE = re.compile(r"1:1 LinkedIn chat\s*\|\s*(.*?)\s+with\s+(.+)$")


def deal_state(n):
    """Deal state for the counterparty behind this note.

    The company-side copy resolves through the company's domains; the person-side
    copy resolves through the deal's associated people. Either is enough, because
    both copies of the same event are deduped to one and the strongest state wins.
    """
    if n["parent_object"] == "companies":
        for dom in companies.get(n["parent_record"], {}).get("domains", []):
            if dom in domain_deal:
                return domain_deal[dom]["state"]
    if n["parent_object"] == "people":
        pd = person_deal.get(n["parent_record"])
        if pd:
            return pd["state"]
    return None


RANK = {"open": 3, "won": 2, "closed": 1}
# event key -> (date, rep, best state seen across the person and company copies)
events = {}
unattributed = collections.Counter()
for n in inv_full:
    kind = "sent" if n["title"].endswith("sent") else "accepted"
    body = n.get("body") or ""
    m = SENT_RE.search(body) if kind == "sent" else ACC_RE.search(body)
    rep = rep_of(m.group(1)) if m else None
    contact = re.sub(r"\s+", " ", m.group(2)).strip().lower() if m else None
    if not rep or not contact:
        unattributed[kind] += 1
        continue
    key = (n["created"], rep, contact, kind)
    st = deal_state(n)
    cur = events.get(key)
    if cur is None or (st and (cur["state"] is None or RANK[st] > RANK[cur["state"]])):
        events[key] = {"date": n["created"], "rep": rep, "kind": kind, "state": st}

for n in chats:
    m = CHAT_RE.match(n["title"])
    rep = rep_of(m.group(2)) if m else None
    contact = re.sub(r"\s+", " ", m.group(1)).strip().lower() if m else ""
    if not rep:
        unattributed["message"] += 1
        continue
    key = (n["created"], rep, contact or n["parent_record"], "message")
    st = deal_state(n)
    cur = events.get(key)
    if cur is None or (st and (cur["state"] is None or RANK[st] > RANK[cur["state"]])):
        events[key] = {"date": n["created"], "rep": rep, "kind": "message", "state": st}


def z():
    return [0] * 6


def tally(kind):
    """Per-day per-person totals, plus the open-deal-associated subset."""
    allc, dealc = collections.defaultdict(z), collections.defaultdict(z)
    for e in events.values():
        if e["kind"] != kind:
            continue
        i = IDX[e["rep"]]
        allc[e["date"]][i] += 1
        if e["state"] == "open":
            dealc[e["date"]][i] += 1
    return dict(sorted(allc.items())), dict(sorted(dealc.items()))


sent_all, sent_deal = tally("sent")
acc_all, acc_deal = tally("accepted")
msg_all, msg_deal = tally("message")

dates = sorted({e["date"] for e in events.values()})
json.dump({"sentAll": sent_all, "sentDeal": sent_deal,
           "accAll": acc_all, "accDeal": acc_deal,
           "covered_from": dates[0] if dates else None,
           "unattributed": dict(unattributed),
           "events": len(events)},
          open(f"{SP}/raw/li_invites.json", "w"), indent=1)
json.dump({"all": msg_all, "deal": msg_deal}, open(f"{SP}/raw/li_msgs.json", "w"), indent=1)


def tot(d):
    return [sum(v[i] for v in d.values()) for i in range(6)]


print("=== LINKEDIN (Groovin notes, rep from the note body) ===")
print("invitation notes:", len(inv), "| chat notes:", len(chats),
      "| deduped events:", len(events))
print("bodies fetched:", sum(1 for n in inv_full if n.get("body")),
      "| body fetch errors:", sum(1 for n in inv_full if n.get("error")))
print("unattributed (no rep parsed):", dict(unattributed) or "none")
print(f"{'':9}" + "".join(f"{r:>9}" for r in REPS))
for lbl, d in (("sent", sent_all), ("sent(deal)", sent_deal), ("accepted", acc_all),
               ("acc(deal)", acc_deal), ("msgs", msg_all), ("msgs(deal)", msg_deal)):
    print(f"{lbl:9}" + "".join(f"{x:>9}" for x in tot(d)))
print("covered from:", dates[0] if dates else None, "to", dates[-1] if dates else None)
