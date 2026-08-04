# -*- coding: utf-8 -*-
"""Attribute LinkedIn activity per person from Attio.

Invitations sent and accepted come from the STRUCTURED invitation attributes on the
person record (last_linkedin_invite_sent_at / _sent_by and the accepted pair). Those
carry the real send time and name the sender by workspace-member id, and they are the
only LinkedIn source that covers the whole team: the Groovin connector authenticates
as one person's own LinkedIn account, so it can never measure a colleague and must
never be used as a benchmark for these figures.

Messages still come from the chat notes, because the attribute holds only the LAST
message per contact and a thread needs every message dated individually.

The person-side invitation notes are UNIONED IN, joined to the attribute on the person
record id so no name matching is involved. This matters because the attribute holds only
the LAST invitation per contact: when a contact is invited again the earlier sender loses
the credit, which cost Chris 3 of 15 and Elliott 8 of 64. The rep is in the note BODY for
invitations, not the title, and reading only the title has caused a real mis-attribution,
so bodies are fetched and parsed:

  sent      body "from <Rep> to <Contact>",  title is the bare
            string "LinkedIn invitation sent" with no rep in it at all
  accepted  body "<Rep> is now connected with <Contact>."
  messages  rep is in the TITLE: "1:1 LinkedIn chat | <Contact> with <Rep>"

Never fall back to counting cadence Touch-1 tasks. That proxy credits whoever was
assigned the task rather than whoever sent the invitation, and it was wrong by a
wide margin: one person read 12 connects against 3 actually sent, another 5
against 32.

Every event writes a person-side and a company-side note. Only the PERSON side is
counted, because it carries the record id the join needs and counting both would double
every figure. The company side still serves the deal split.
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
# Workspace-member id -> scorecard name. The invitation attributes reference the sender
# by id, so this is the attribution: no name parsing, no ambiguity over "Chris W".
MEMBERS = {
    "814dcafb-8d1e-4766-86fd-f8aa6d8ec9e7": "Chris",
    "10483700-4091-479f-9d93-5f211daaf782": "Luke",
    "b4d18eef-0a60-4053-8f02-372285421b69": "James",
    "4eb5d016-4e43-4999-b82d-d1472875acac": "Bianca",
    "67d33719-6e02-4e34-914b-1f47ab8f8226": "Elliott",
    "64faca79-2742-4958-ba9f-c3fc5fe2bd40": "Rupert",
}


def req(path, body=None):
    r = urllib.request.Request("https://api.attio.com/v2" + path,
                               method="POST" if body else "GET",
                               data=json.dumps(body).encode() if body else None,
                               headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(r, timeout=120) as fh:
        return json.loads(fh.read().decode())


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

# Chat bodies are fetched too, because the TITLE cannot carry a message count and the
# note's created date is not when the messages were sent. Two faults came from reading
# chat notes off the title alone:
#   1. Every conversation writes a person-side and a company-side note. The person-side
#      title has no contact in it ("1:1 LinkedIn chat | with Elliott Perks"), so a
#      contact-based dedupe key fell back to the record id, the two copies never
#      collapsed, and messages counted roughly double.
#   2. Groovin backfilled whole conversation histories on switch-on day, so threads
#      whose messages are from 2024 and 2025 were being dated 21 Jul 2026 and credited
#      as a day's work.
# Both are fixed by counting the individual messages in the body and dating each one by
# its own timestamp. The bodies of the two copies are identical, so (rep, timestamp)
# collapses them naturally.
with cf.ThreadPoolExecutor(max_workers=8) as ex:
    chats_full = list(ex.map(fetch_body, chats))
json.dump(chats_full, open(f"{SP}/raw/chat_notes.json", "w"), indent=0)

# The REP must look like a workspace member name, which is reliably capitalised. The
# CONTACT is whatever follows, to end of string: it is only used as a dedupe key, and
# requiring it to be capitalised silently dropped real events. A live invitation whose
# body read "from Luke Nogueira to bob galiger" was lost that way, so a rep who had
# sent nine requests showed eight.
SENT_RE = re.compile(r"\bfrom\s+([A-Z][A-Za-z'\-]*(?:\s+[A-Z][A-Za-z'\-]*)*)\s+to\s+(.+?)\s*$")
ACC_RE = re.compile(r"^([A-Z][A-Za-z'\-]*(?:\s+[A-Z][A-Za-z'\-]*)*)\s+is now connected with\s+(.+?)\s*\.?\s*$")
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

# ---------------------------------------------------------------------------
# PRIMARY SOURCE: the Attio invitation record on the person, not the note.
#
# Groovin writes two things into Attio for an invitation: a note, and structured
# attributes on the person record. The attributes are the better source on every axis
# except history, and are the base this routine counts from:
#   - last_linkedin_invite_sent_at is the REAL send time to the millisecond, where a
#     note can only be dated by when Groovin got round to writing it
#   - last_linkedin_invite_sent_by is a workspace-member REFERENCE, so the rep is an
#     id rather than a name parsed out of English prose
#   - it needs no person/company dedupe, because there is one record per contact
#   - it is fresher: on 4 Aug 2026 it already held two sends whose notes did not exist
# This is also the only source that works for the whole team. The Groovin connector
# authenticates as one person's own LinkedIn account, so it can never be used to
# measure a colleague, and a count taken from it must never be compared against these.
#
# The one thing the attributes cannot do is carry a HISTORY: they hold the LAST
# invitation per contact, so re-inviting the same person overwrites the earlier date.
# The notes do keep both, so note-only events are unioned back in below and the two
# counts are reconciled in the output rather than quietly reconciled away.
ATTR = {"sent": ("last_linkedin_invite_sent_at", "last_linkedin_invite_sent_by"),
        "accepted": ("last_linkedin_invite_accepted_at", "last_linkedin_invite_accepted_inviter")}


def _v(values, key):
    x = values.get(key) or []
    return x[0] if x else None


def page_people(ts_attr):
    out, off = [], 0
    while True:
        d = req("/objects/people/records/query",
                {"limit": 500, "offset": off, "filter": {ts_attr: {"$gte": FROM + "T00:00:00Z"}}})["data"]
        out += d
        if len(d) < 500:
            return out
        off += 500


def person_state(rec_id, company_id):
    """Deal state for a contact: the person's own deal first, else their company's.

    Same join as every other (deal) metric: contact -> company -> strongest deal state.
    """
    pd = person_deal.get(rec_id)
    if pd:
        return pd["state"]
    for dom in companies.get(company_id, {}).get("domains", []):
        if dom in domain_deal:
            return domain_deal[dom]["state"]
    return None


events = {}
unattributed = collections.Counter()
attr_counts = {k: collections.Counter() for k in ATTR}
attr_names = collections.defaultdict(set)      # (rep, kind) -> contact names already counted
# Contacts whose "no deal" verdict is a REPAIRABLE data gap rather than a fact: the
# person has no company link, or the company record has no domain. A contact on a
# domainless duplicate of a company that holds an open deal reads as "no deal" and
# silently under-reports the sender, so these are surfaced for repair, never inferred.
# Found live on 4 Aug 2026: Jon Flynn sat on "Vascor Transport Ltd" (no domain) while
# James's open deal sat on "VASCOR Logistics" (vascor.com), costing James one (deal).
join_gaps = []
for kind, (ts_attr, actor_attr) in ATTR.items():
    for r in page_people(ts_attr):
        vals = r["values"]
        ts, actor = _v(vals, ts_attr), _v(vals, actor_attr)
        if not ts:
            continue
        if not actor or actor.get("referenced_actor_type") != "workspace-member":
            unattributed[kind + "_no_sender"] += 1
            continue
        rep = MEMBERS.get(actor.get("referenced_actor_id"))
        if not rep:
            unattributed[kind + "_non_team_sender"] += 1
            continue
        rec_id = r["id"]["record_id"]
        nm = _v(vals, "name") or {}
        comp = _v(vals, "company") or {}
        st = person_state(rec_id, comp.get("target_record_id"))
        events[(rep, kind, rec_id)] = {
            "date": ts["value"][:10], "rep": rep, "kind": kind,
            "state": st, "src": "attribute"}
        attr_counts[kind][rep] += 1
        if nm.get("full_name"):
            attr_names[(rep, kind)].add(nm["full_name"].strip().lower())
        if st is None:
            cid = comp.get("target_record_id")
            cinfo = companies.get(cid, {}) if cid else {}
            if not cid:
                join_gaps.append({"contact": nm.get("full_name"), "rep": rep, "kind": kind,
                                  "date": ts["value"][:10], "reason": "no company on the person record"})
            elif not cinfo.get("domains"):
                join_gaps.append({"contact": nm.get("full_name"), "rep": rep, "kind": kind,
                                  "date": ts["value"][:10], "company": cinfo.get("name"),
                                  "reason": "company record has no domain, so it cannot join to a deal"})

# The notes are UNIONED IN, joined to the attribute by PERSON RECORD ID.
#
# The attribute holds only the LAST invitation per contact, so when a contact is invited
# again the earlier sender loses the credit entirely. That is not a rounding error: it
# cost Chris 3 of 15, Elliott 8 of 64, James 2 and Rupert 3. Ignoring it understates
# real work by a named person, which is the one thing this routine must never do.
#
# A first attempt matched notes to records by comparing the contact name parsed out of
# prose against the record's full_name. That was rightly rejected: it is fragile enough
# ("Robert Ourisman Jr. ." vs "Robert Ourisman Jr.") that it invented events. But the
# name was never needed. A person-side note carries parent_record, which IS the person
# record id the attribute is keyed on, so the join is exact and needs no name at all.
#
# Only the PERSON-side copy is counted. The company-side copy describes the same event
# and has no person id, so counting it would double everything; it still serves the deal
# join through deal_state.
note_counts = {k: collections.Counter() for k in ATTR}
note_only = []
for n in inv_full:
    kind = "sent" if n["title"].endswith("sent") else "accepted"
    body = n.get("body") or ""
    m = SENT_RE.search(body) if kind == "sent" else ACC_RE.search(body)
    rep = rep_of(m.group(1)) if m else None
    if not rep:
        unattributed[kind + "_note_unparsed"] += 1
        continue
    if n["parent_object"] != "people":
        continue
    note_counts[kind][rep] += 1
    key = (rep, kind, n["parent_record"])
    if key not in events:
        note_only.append((key, n))

# Resolve each recovered contact's company so its deal split uses the same
# contact -> company -> strongest deal state join as every other (deal) metric.
def company_of(rec_id):
    try:
        v = req(f"/objects/people/records/{rec_id}")["data"]["values"]
        return (_v(v, "company") or {}).get("target_record_id")
    except Exception:
        return None


with cf.ThreadPoolExecutor(max_workers=8) as ex:
    _comps = list(ex.map(lambda kn: company_of(kn[0][2]), note_only))
for (key, n), comp in zip(note_only, _comps):
    rep, kind, rec_id = key
    st = person_state(rec_id, comp)
    events[key] = {"date": n["created"], "rep": rep, "kind": kind,
                   "state": st if st else deal_state(n), "src": "note"}

# Each note event is written twice, person-side and company-side, so the raw note
# count is halved before it is compared with the attribute count.
note_counts = {k: collections.Counter({r: round(c / 2) for r, c in v.items()})
               for k, v in note_counts.items()}

# A message segment in a chat body reads "<Author> • Jul 21, 2026, 9:53 AM UTC <text>".
# Only segments authored by a rep are counted: an inbound reply is not outreach.
MSG_RE = re.compile(r"([A-Z][A-Za-z'\-.]*(?:\s+[A-Z][A-Za-z'\-.]*)*)\s+•\s+"
                    r"([A-Z][a-z]{2} \d{1,2}, \d{4}), (\d{1,2}:\d{2}\s*[AP]M)\s+UTC")
MONTHS = {"Jan": 1, "Feb": 2, "Mar": 3, "Apr": 4, "May": 5, "Jun": 6,
          "Jul": 7, "Aug": 8, "Sep": 9, "Oct": 10, "Nov": 11, "Dec": 12}
msg_backfilled = collections.Counter()      # rep-authored messages predating the window


def seg_date(datepart):
    m = re.match(r"([A-Z][a-z]{2}) (\d{1,2}), (\d{4})", datepart)
    return "%04d-%02d-%02d" % (int(m.group(3)), MONTHS[m.group(1)], int(m.group(2))) if m else None


for n in chats_full:
    tm = CHAT_RE.match(n["title"])
    title_rep = rep_of(tm.group(2)) if tm else None
    contact = re.sub(r"\s+", " ", tm.group(1)).strip().lower() if tm else ""
    body = n.get("body") or ""
    # finditer, not findall, so the message TEXT can be taken as the span between this
    # header and the next. The text is what makes the dedupe exact: the person-side and
    # company-side bodies are identical, so the same message yields the same key, while
    # two different threads written in the same minute stay separate.
    hits = list(MSG_RE.finditer(body))
    segs = [(h.group(1), h.group(2), h.group(3),
             body[h.end():(hits[i + 1].start() if i + 1 < len(hits) else len(body))].strip()[:120])
            for i, h in enumerate(hits)]
    if not segs:
        # No parseable message in the body. Recorded as a gap rather than counted from
        # the title, which would date the whole thread to the day Groovin synced it.
        unattributed["message_no_body"] += 1
        continue
    st = deal_state(n)
    for author, datepart, timepart, text in segs:
        rep = rep_of(author)
        if not rep:
            continue                       # inbound message from the contact, not outreach
        day = seg_date(datepart)
        if not day:
            continue
        if day < FROM:
            msg_backfilled[rep] += 1       # historic thread swept in on sync, never dated to today
            continue
        # The message itself: same rep, same minute, same words. Contact is deliberately
        # NOT in the key, because the person-side copy has no contact in its title and
        # including it is what stopped the two copies collapsing in the first place.
        key = (day, rep, timepart.replace(" ", ""), text, "message")
        cur = events.get(key)
        if cur is None or (st and (cur["state"] is None or RANK[st] > RANK[cur["state"]])):
            events[key] = {"date": day, "rep": rep, "kind": "message", "state": st}
    if not title_rep:
        unattributed["message_title_rep"] += 1


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
# Two independent Attio sources for the same events, reported side by side rather than
# silently merged. A wide divergence means one of them has broken and the page must say
# so instead of presenting a single confident number.
recon = {}
for kind in ATTR:
    recon[kind] = {"attribute": dict(attr_counts[kind]), "note": dict(note_counts[kind]),
                   "recovered_from_notes": sum(1 for e in events.values()
                                                 if e["kind"] == kind and e["src"] == "note")}
json.dump({"sentAll": sent_all, "sentDeal": sent_deal,
           "accAll": acc_all, "accDeal": acc_deal,
           "covered_from": dates[0] if dates else None,
           "unattributed": dict(unattributed),
           "reconciliation": recon,
           "source": ("Attio invitation attributes on the person record "
                      "(last_linkedin_invite_sent_at / _sent_by and the accepted pair) "
                      "unioned with the person-side Groovin notes, joined on the person "
                      "record id so no name matching is involved. The attribute gives the "
                      "real send time and id-based attribution; the notes recover events "
                      "whose attribute was overwritten by a later invitation to the same "
                      "contact, which would otherwise lose the earlier sender's credit."),
           "join_gaps": join_gaps,
           "events": len(events)},
          open(f"{SP}/raw/li_invites.json", "w"), indent=1)
json.dump({"all": msg_all, "deal": msg_deal,
           "backfilled_excluded": dict(msg_backfilled),
           "note": "each message is counted once and dated by its own timestamp in the "
                   "note body, not by the note's created date. Messages predating "
                   f"{FROM} are Groovin's initial sync of historic threads and are "
                   "excluded rather than credited to the sync day."},
          open(f"{SP}/raw/li_msgs.json", "w"), indent=1)


def tot(d):
    return [sum(v[i] for v in d.values()) for i in range(6)]


print("=== LINKEDIN (Attio invitation attributes, cross-checked against Groovin notes) ===")
print("invitation notes:", len(inv), "| chat notes:", len(chats),
      "| deduped events:", len(events))
print("bodies fetched:", sum(1 for n in inv_full if n.get("body")),
      "| body fetch errors:", sum(1 for n in inv_full if n.get("error")))
print("unattributed:", dict(unattributed) or "none")
for _k in ATTR:
    _a, _n = attr_counts[_k], note_counts[_k]
    _av, _nv = sum(_a.values()), sum(_n.values())
    _rec = sum(1 for e in events.values() if e["kind"] == _k and e["src"] == "note")
    print(f"  {_k:9} attribute {_av:4} | person-side notes {_nv:4} | recovered from notes "
          f"{_rec:3} | counted {_av + _rec:4}")
    _by = collections.Counter(e["rep"] for e in events.values()
                              if e["kind"] == _k and e["src"] == "note")
    if _by:
        print("      recovered per rep:", dict(_by))
print(f"{'':9}" + "".join(f"{r:>9}" for r in REPS))
for lbl, d in (("sent", sent_all), ("sent(deal)", sent_deal), ("accepted", acc_all),
               ("acc(deal)", acc_deal), ("msgs", msg_all), ("msgs(deal)", msg_deal)):
    print(f"{lbl:9}" + "".join(f"{x:>9}" for x in tot(d)))
print("covered from:", dates[0] if dates else None, "to", dates[-1] if dates else None)
if join_gaps:
    print(f"repairable join gaps ({len(join_gaps)}): a 'no deal' verdict that is a data gap, not a fact")
    for g in join_gaps[-8:]:
        print(f"   {g['date']} {g['rep']:8} {str(g['contact'])[:26]:26} {g.get('company') or '-':28.28} {g['reason']}")
