# -*- coding: utf-8 -*-
"""Pull deals, companies, tasks and Groovin notes from the Attio REST API.

REST is used rather than the MCP tools because it is far cheaper for bulk objects
and returns every field in one pass. Credentials are injected by the proxy, so no
token appears here. There is no public emails endpoint, so email stays on MCP.

Writes, all under $JIGCAR_SP/raw:
  deals_all.json    one row per deal, flattened, keyed on the 8-char id prefix
  companies.json    company -> domains, for the recipient/contact -> deal join
  domain_deal.json  domain -> {state, deal}, the single deal-association test
  tasks.json        completed tasks dated by completed_at
  notes.json        note index (id, title, actor, created, parent) for LinkedIn
  join_report.json  coverage of the deal <-> company join, reported on the page
"""
import json, os, re, sys, urllib.request, collections

SP = os.environ.get("JIGCAR_SP") or os.path.dirname(os.path.abspath(__file__))
API = "https://api.attio.com/v2"
MEMBERS = {
    "814dcafb-8d1e-4766-86fd-f8aa6d8ec9e7": "Chris",
    "10483700-4091-479f-9d93-5f211daaf782": "Luke",
    "b4d18eef-0a60-4053-8f02-372285421b69": "James",
    "4eb5d016-4e43-4999-b82d-d1472875acac": "Bianca",
    "67d33719-6e02-4e34-914b-1f47ab8f8226": "Elliott",
    "64faca79-2742-4958-ba9f-c3fc5fe2bd40": "Rupert",
    "35a5991c-1c83-45da-a10d-16576845abb4": "Jon Pollock",
    "0cd10c6b-3e9b-4850-926c-6ef2a3403c2b": "Bob O'Reilly",
    "5c0f0e89-1d4a-4c4c-9df6-8c9e41d72cc0": "Pierre de Villeplee",
}
OPEN_STAGES = ["New Lead", "Buy Signal", "Qualification", "Demo", "Proposal", "Trial", "Contracts"]

# Stage renames in Attio, normalised to the CURRENT title at the point of the pull so
# raw/ is canonical and every downstream step sees one name per stage.
#
# On 29 Jul 2026 "Non-ICP" was renamed to "Contacted - no outcome": it is absent from
# the status options entirely, not merely archived, "Contacted - no outcome" appeared
# in its place, and the same eight record ids sit in it. So this is a relabel, not a
# move. Without this map the stage diff would compare a stored "Non-ICP" against a
# pulled "Contacted - no outcome" and book eight shut-offs against their owners on a
# day nobody touched those deals. Both titles mean a shut-off state, so nothing about
# the classification changes; only the label does.
STAGE_ALIAS = {"Non-ICP": "Contacted - no outcome"}


def req(path, body=None, method=None):
    r = urllib.request.Request(API + path, method=method or ("POST" if body else "GET"),
                               data=json.dumps(body).encode() if body else None,
                               headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(r, timeout=90) as fh:
        return json.loads(fh.read().decode())


def page_query(slug, limit=500):
    """Records for an object, paged. limit 500 is the documented maximum."""
    out, offset = [], 0
    while True:
        d = req(f"/objects/{slug}/records/query", {"limit": limit, "offset": offset})["data"]
        out.extend(d)
        if len(d) < limit:
            return out
        offset += limit


def v1(rec, attr, key="value"):
    vals = rec["values"].get(attr) or []
    return vals[0].get(key) if vals else None


def status_of(rec, attr):
    vals = rec["values"].get(attr) or []
    return (vals[0].get("status") or {}).get("title") if vals else None


def option_of(rec, attr):
    vals = rec["values"].get(attr) or []
    return (vals[0].get("option") or {}).get("title") if vals else None


def actor_of(rec, attr):
    vals = rec["values"].get(attr) or []
    return MEMBERS.get(vals[0].get("referenced_actor_id")) if vals else None


def refs_of(rec, attr):
    return [x.get("target_record_id") for x in (rec["values"].get(attr) or [])]


ISO = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def est_close_of(rec):
    """The estimated close date, and only if it really is a date.

    Attio carries two attributes here: est_closed_date is a real date, while
    est_close_date is free text and holds values like "July". Reading the text
    field as a date crashes the build, and worse, guessing a day from "July"
    would promote an estimate to a fact. Anything that is not an ISO date is
    dropped and renders as "est TBC".
    """
    for attr in ("est_closed_date", "est_close_date"):
        raw = (v1(rec, attr) or "")[:10]
        if ISO.match(raw):
            return raw
    return None


# ---------------- deals ----------------
raw_deals = page_query("deals")
deals = []
for r in raw_deals:
    rid = r["id"]["record_id"]
    money = v1(r, "value", "currency_value")
    deals.append({
        "record_id": rid,
        "short": rid[:8],
        "name": v1(r, "name") or "(unnamed)",
        "stage": STAGE_ALIAS.get(status_of(r, "stage"), status_of(r, "stage")),
        "owner": actor_of(r, "owner"),
        "value": float(money or 0),
        "acq": option_of(r, "acquisition"),
        "created": (v1(r, "created_at") or "")[:10],
        "est_closed": est_close_of(r),
        "est_close_text": v1(r, "est_close_date"),
        "companies": refs_of(r, "associated_company"),
        "people": refs_of(r, "associated_people"),
    })
json.dump(deals, open(f"{SP}/raw/deals_all.json", "w"), indent=0)

# ---------------- companies -> domains ----------------
raw_co = page_query("companies")
companies = {}
for r in raw_co:
    rid = r["id"]["record_id"]
    doms = [d.get("domain") for d in (r["values"].get("domains") or []) if d.get("domain")]
    companies[rid] = {"name": v1(r, "name"), "domains": [d.lower() for d in doms]}
json.dump(companies, open(f"{SP}/raw/companies.json", "w"), indent=0)

# ---------------- the one deal-association test ----------------
# (deal) anywhere on the page means: the counterparty's company has an OPEN deal,
# New Lead through Contracts. Closed Won is a customer, counted separately. Every
# metric that carries (deal) uses this same map so the columns are comparable.
def state_of(stage):
    if stage in OPEN_STAGES:
        return "open"
    if stage == "Closed Won":
        return "won"
    return "closed"


RANK = {"open": 3, "won": 2, "closed": 1}
domain_deal, person_deal = {}, {}
for d in deals:
    st = state_of(d["stage"])
    for cid in d["companies"]:
        for dom in companies.get(cid, {}).get("domains", []):
            cur = domain_deal.get(dom)
            if cur is None or RANK[st] > RANK[cur["state"]]:
                domain_deal[dom] = {"state": st, "deal": d["name"], "owner": d["owner"],
                                    "stage": d["stage"], "value": d["value"]}
    for pid in d["people"]:
        cur = person_deal.get(pid)
        if cur is None or RANK[st] > RANK[cur["state"]]:
            person_deal[pid] = {"state": st, "deal": d["name"], "owner": d["owner"]}
json.dump(domain_deal, open(f"{SP}/raw/domain_deal.json", "w"), indent=0)
json.dump(person_deal, open(f"{SP}/raw/person_deal.json", "w"), indent=0)

# ---------------- join coverage, reported on the page ----------------
# Where a deal has no company, or the company has no domain, the join silently
# under-reports. Surface those for repair rather than inferring a domain.
open_deals = [d for d in deals if d["stage"] in OPEN_STAGES]
joinable, unjoinable = [], []
for d in open_deals:
    doms = [x for cid in d["companies"] for x in companies.get(cid, {}).get("domains", [])]
    (joinable if doms else unjoinable).append(d)
open_val = sum(d["value"] for d in open_deals)
join_val = sum(d["value"] for d in joinable)
join_report = {
    "open_deals": len(open_deals),
    "joinable": len(joinable),
    "unjoinable": len(unjoinable),
    "pipeline_value": open_val,
    "joinable_value": join_val,
    "joinable_pct_by_value": round(join_val / open_val * 100, 1) if open_val else 0.0,
    "domains_resolving": len(domain_deal),
    "unjoinable_deals": [{"name": d["name"], "owner": d["owner"], "value": d["value"],
                          "stage": d["stage"],
                          "reason": "no company linked" if not d["companies"] else "company has no domain"}
                         for d in sorted(unjoinable, key=lambda x: -x["value"])],
}
json.dump(join_report, open(f"{SP}/raw/join_report.json", "w"), indent=1)

# ---------------- tasks, dated by completed_at ----------------
tasks, offset = [], 0
while True:
    d = req(f"/tasks?limit=500&offset={offset}")["data"]
    for t in d:
        assignees = [MEMBERS.get(a.get("referenced_actor_id")) for a in (t.get("assignees") or [])]
        tasks.append({"id": t["id"]["task_id"], "completed_at": t.get("completed_at"),
                      "created_at": t.get("created_at"),
                      "is_completed": bool(t.get("is_completed")),
                      "assignees": [a for a in assignees if a],
                      "content": (t.get("content_plaintext") or "")[:120]})
    if len(d) < 500:
        break
    offset += 500
json.dump(tasks, open(f"{SP}/raw/tasks.json", "w"), indent=0)

# ---------------- notes index (Groovin LinkedIn activity lives here) ----------------
notes, offset = [], 0
while True:
    d = req(f"/notes?limit=50&offset={offset}")["data"]
    for n in d:
        pr = n.get("parent_object")
        notes.append({"id": n["id"]["note_id"], "title": (n.get("title") or "").strip(),
                      "actor": (n.get("created_by_actor") or {}).get("id"),
                      "actor_type": (n.get("created_by_actor") or {}).get("type"),
                      "created": (n.get("created_at") or "")[:10],
                      "parent_object": pr, "parent_record": n.get("parent_record_id")})
    if len(d) < 50:
        break
    offset += 50
json.dump(notes, open(f"{SP}/raw/notes.json", "w"), indent=0)

print("=== ATTIO PULL ===")
print("deals:", len(deals), "| companies:", len(companies), "| domains resolving:", len(domain_deal))
print("stages:", dict(collections.Counter(d["stage"] for d in deals)))
print("open deals:", join_report["open_deals"], "joinable:", join_report["joinable"],
      f"({join_report['joinable_pct_by_value']}% by value)")
for u in join_report["unjoinable_deals"]:
    print(f"   UNJOINABLE  {u['name'][:38]:38} {u['owner']} £{u['value']:,.0f}  {u['reason']}")
print("tasks:", len(tasks), "| completed:", sum(1 for t in tasks if t["is_completed"]))
print("notes:", len(notes))
gro = [n for n in notes if n["actor"] == "c020395f-1e1e-4a88-9d95-3c63937a06f8"]
print("Groovin notes:", len(gro), "|", dict(collections.Counter(n["title"][:34] for n in gro).most_common(8)))
