# -*- coding: utf-8 -*-
"""Jigcar Team Momentum - deterministic ETL. Run date 2026-07-27."""
import json, collections, datetime, os

SP="/tmp/claude-0/-home-user-jigcar-dashboard/b183b5d1-3506-53f2-a1fc-bfac32d1ea9e/scratchpad"
RUN_DATE="2026-07-27"
RUN_STAMP="27 Jul 2026, 08:00"
QUARTER_TARGET=400000
REPS=["Chris","Luke","James","Bianca","Elliott","Rupert"]
IDX={r:i for i,r in enumerate(REPS)}
PROG=["New Lead","Buy Signal","Qualification","Demo","Proposal","Trial","Contracts","Closed Won"]
SHUT=["Nurture","Closed Lost","Churn","Non-ICP"]

# ---------- channel normalisation: spelling only, never a semantic remap ----------
CHAN_FIX={"Inboud - linkedin":"Inbound - LinkedIn"}
def norm_chan(c):
    if not c: return None
    return CHAN_FIX.get(c, c)

deals=json.load(open(f"{SP}/raw/deals_all.json"))
for d in deals: d["acq"]=norm_chan(d.get("acq"))

# ---------- confirmed back-book won dates (manually confirmed; see spec + approved build) ----------
WON_DATES={
 "61411697":"2026-02-15",  # Focus VM      -> Q1 2026 (quarter confirmed, mid-quarter placeholder day)
 "58be4a55":"2026-05-15",  # RH Car Transport -> Q2 2026
 "1988b641":"2026-05-15",  # Monmotors        -> Q2 2026
 "4680be99":"2026-05-15",  # Premier Travel   -> Q2 2026
 "0cb33403":"2026-07-14",  # Peter Cooper     -> Q3 2026 (date confirmed)
 "a2223c13":"2026-07-23",  # Hilton Coachworks-> Q3 2026 (date confirmed)
}
WON_DATE_QUARTER_ONLY={"61411697","58be4a55","1988b641","4680be99"}
PRE_2026_WON={"f05e16a4","12f2dbef","30866ff1","3f1a45e1","3a825192","921a8e55",
              "18ea02a6","8826de8e","1ff4cc2c","e7e86ecb"}

def quarter_of(iso):
    y,m=int(iso[:4]),int(iso[5:7])
    return f"Q{(m-1)//3+1}-{y}"

# ---------- meeting classification (auditable, stored in state) ----------
EXCLUDED_MEETINGS={
 ("2026-07-06","Simon / Elliott"):"adviser",
 ("2026-07-13","Major Client Tender - Jigcar"):"supplier / 3PL carrier, no deal attached",
 ("2026-07-14","Elliott / Paul - plant hire transport"):"exploratory, no deal attached",
 ("2026-07-14","Introduction mtg. Jigcar and Thoughtline Digital"):"vendor / agency intro",
 ("2026-07-16","Jigcar x Automotive Logistics catch up"):"media / press",
 ("2026-07-16","Quick catch up with Jonathan Holland on Auction House opportunity"):"adviser",
 ("2026-07-20","Groupe CAT / Jigcar"):"supplier / 3PL carrier",
 ("2026-07-21","Jigcar sales team weekly"):"internal weekly (external addresses are own contractors)",
 ("2026-07-21","TradeBid/Jigcar Potential Strategic Collaboration"):"partner / channel exploration, no deal attached",
 ("2026-07-24","Book a 30-min meeting with Elliott at Jigcar (Rita Sharma)"):"tooling / vendor",
 ("2026-07-24","Jig Car chat"):"investor",
}
EXCL_PREFIX=[(d,t[:40]) for (d,t) in EXCLUDED_MEETINGS]

gran=json.load(open(f"{SP}/raw/granola.json"))
FIRST={"chris.white@jigcar.com":"Chris","luke.nogueira@jigcar.com":"Luke",
       "james.griffin@jigcar.com":"James","bianca.monteiro@jigcar.com":"Bianca",
       "elliott@jigcar.com":"Elliott","rupert@jigcar.com":"Rupert"}
seen=set(); meetings_daily=collections.defaultdict(lambda:[0]*6)
inc_count=0; exc_count=0; internal_count=0
for m in gran:
    em=m["emails"]
    if em and all(e.endswith("@jigcar.com") for e in em):
        internal_count+=1; continue
    if not em: internal_count+=1; continue
    key=(m["date"],m["title"])
    if key in seen: continue          # dedupe: one event per note-creator
    seen.add(key)
    if any(m["date"]==d and m["title"][:40]==p for (d,p) in EXCL_PREFIX):
        exc_count+=1; continue
    inc_count+=1
    for e in em:
        if e in FIRST: meetings_daily[m["date"]][IDX[FIRST[e]]]+=1

# ---------- calls (Allo, complete for July) ----------
calls_daily={
 "2026-07-21":[1,0,0,0,3,0],
 "2026-07-22":[0,1,1,0,4,0],
 "2026-07-23":[0,3,3,0,0,0],
}
# ---------- emails (Attio multi-mailbox, de-duped by sender+subject+sent_at) ----------
# Complete for the run date only. Earlier days in the period have no coverage this run
# (first run, no accumulated history) and are rendered as a labelled floor.
emails_daily={ "2026-07-27":[1,0,0,1,9,1] }
EMAIL_COVERED_FROM="2026-07-27"
# ---------- tasks completed (dated by created_at: Attio exposes no completion timestamp) ----------
tasks_daily={
 "2026-07-21":[4,0,0,0,0,0],
 "2026-07-22":[5,0,0,0,0,0],
 "2026-07-23":[3,0,0,1,0,0],
 "2026-07-24":[5,0,0,0,0,0],
 "2026-07-27":[1,0,0,0,0,0],
}
# ---------- LinkedIn ----------
# connects: attributed via cadence Touch-1 (completed connect task on the owner's deal).
# Every such task is linked to a deal, so the deal-associated figure equals the total.
li_conn_all={
 "2026-07-21":[3,0,0,0,0,0],
 "2026-07-22":[4,0,0,0,0,0],
 "2026-07-23":[2,0,0,1,0,0],
 "2026-07-24":[2,0,0,0,0,0],
}
li_conn_deal={k:list(v) for k,v in li_conn_all.items()}
# messages: rep parsed from Groovin chat-note titles, de-duped to one event per pair
li_msg_all={
 "2026-07-21":[0,0,0,0,3,0],
 "2026-07-22":[0,0,1,0,2,0],
 "2026-07-23":[0,0,0,0,1,0],
 "2026-07-24":[0,1,0,0,2,0],
}
# deal-associated messages: floor. Only pairs whose company record is confirmed to carry
# a deal are counted (Drive Motor Retail -> James 22 Jul, Morgan Auto Group -> Elliott 22 Jul).
li_msg_deal={ "2026-07-22":[0,0,1,0,1,0] }
LI_NOTE_COVERED_FROM="2026-07-22"

# ---------- deals assigned per day (from Attio created_at) ----------
deals_daily=collections.defaultdict(lambda:[0]*6)
for d in deals:
    if d["created"]>="2026-07-01" and d["owner"] in IDX:
        deals_daily[d["created"]][IDX[d["owner"]]]+=1

# ---------- progressed / shut off: first run seeds the baseline, no diff available ----------
progressed_daily={}; shutoff_daily={}

daily={"meetings":dict(meetings_daily),"calls":calls_daily,"emails":emails_daily,
       "tasks":tasks_daily,"deals":dict(deals_daily),"progressed":progressed_daily,
       "shutoff":shutoff_daily,"liConnAll":li_conn_all,"liConnDeal":li_conn_deal,
       "liMsgAll":li_msg_all,"liMsgDeal":li_msg_deal}

# ---------- revenue ----------
def owner_name(o): return o
closed_won=[d for d in deals if d["stage"]=="Closed Won"]
contracts=[d for d in deals if d["stage"]=="Contracts"]
EST={"665c0cc1":"20 Jul (est, passed)","da844db1":"20 Jul (est, passed)","b26a3750":"est TBC"}
MONTHS=["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"]
def pretty(iso):
    return f"{int(iso[8:10])} {MONTHS[int(iso[5:7])-1]} {iso[:4]}"

q3_won=[]; won_ytd=[]
for d in closed_won:
    wd=WON_DATES.get(d["id"])
    if not wd: continue                      # pre-2026 book, excluded from 2026 views
    q=quarter_of(wd)
    entry={"name":d["name"],"arr":d["value"],"owner":d["owner"],
           "quarter":q.split("-")[0],"channel":d["acq"] or "Unassigned",
           "date":("%s 2026"%q.split("-")[0]) if d["id"] in WON_DATE_QUARTER_ONLY else pretty(wd)}
    won_ytd.append(entry)
    if q=="Q3-2026": q3_won.append(entry)

contract_deals=[{"name":d["name"],"arr":d["value"],"owner":d["owner"],
                 "date":EST.get(d["id"],"est TBC")} for d in contracts]
contract_deals.sort(key=lambda x:-x["arr"])
q3_won.sort(key=lambda x:-x["arr"])

# ---------- acquisition chart: full won book ----------
acq=collections.Counter((d["acq"] or "Unassigned") for d in closed_won)

# ---------- archive: reconstructed Q1/Q2 2026 ----------
def archive(qkey, start, end, label):
    cw=[e for e in won_ytd if e["quarter"]==qkey]
    created=[d for d in deals if start<=d["created"]<=end]
    byo=collections.defaultdict(lambda:{"created":0,"value":0})
    for d in created:
        byo[d["owner"]]["created"]+=1; byo[d["owner"]]["value"]+=d["value"]
    out=collections.Counter()
    wonids={e["name"] for e in cw}
    for d in created:
        s=d["stage"]
        if s=="Closed Won": out["Now won"]+=1
        elif s in ("Nurture",): out["Nurture"]+=1
        elif s in ("Closed Lost","Non-ICP","Churn"): out["Non-ICP / Lost"]+=1
        elif s is None: out["Non-ICP / Lost"]+=1
        else: out["Live (New Lead to Contracts)"]+=1
    return {"label":label,
            "closedWon":[{"name":e["name"],"arr":e["arr"],"owner":e["owner"],
                          "date":e["date"],"channel":e["channel"]} for e in sorted(cw,key=lambda x:-x["arr"])],
            "acquisition":dict(collections.Counter(e["channel"] for e in cw)),
            "createdCount":len(created),
            "createdPipeline":sum(d["value"] for d in created),
            "byOwner":[{"name":k,"created":v["created"],"value":v["value"]}
                       for k,v in sorted(byo.items(),key=lambda kv:-kv[1]["created"])],
            "outcomes":dict(out)}

archives={
 "Q2-2026":archive("Q2","2026-04-01","2026-06-30","Q2 2026 (Apr - Jun) . reconstructed archive"),
 "Q1-2026":archive("Q1","2026-01-01","2026-03-31","Q1 2026 (Jan - Mar) . reconstructed archive"),
}

# ---------- connectivity, from this run's actual results ----------
connectivity={"updated":RUN_STAMP,
 "workspace":[
   {"name":"Attio","status":"ok","note":"deals, tasks, notes, email search"},
   {"name":"Granola","status":"ok","note":"meetings, 121 in July"},
   {"name":"Apollo","status":"unknown","note":"sends route via mailboxes"}],
 "seats":{
   "Chris":["ok","ok","ok"], "Luke":["ok","unknown","ok"], "James":["ok","unknown","ok"],
   "Bianca":["unknown","ok","unknown"], "Elliott":["ok","ok","ok"], "Rupert":["na","ok","unknown"]}}

# ---------- time ranges ----------
d0=datetime.date(2026,7,27)
ranges={"today":[RUN_DATE,RUN_DATE],
        "yesterday":[str(d0-datetime.timedelta(days=1))]*2,
        "week":[str(d0-datetime.timedelta(days=6)),RUN_DATE],
        "month":["2026-07-01",RUN_DATE],
        "quarter":["2026-07-01",RUN_DATE]}
rangeText={"today":"Mon 27 Jul","yesterday":"Sun 26 Jul","week":"21-27 Jul (7 days)",
           "month":"July, 1-27","quarter":"Q3 to date, 1-27 Jul"}

state={"schema":2,"last_run":RUN_DATE,"last_run_stamp":RUN_STAMP,
  "quarter_target":QUARTER_TARGET,
  "stage_snapshot":{d["id"]:{"stage":d["stage"],"owner":d["owner"],"value":d["value"]} for d in deals},
  "won_dates":WON_DATES,
  "won_dates_quarter_only":sorted(WON_DATE_QUARTER_ONLY),
  "pre_2026_won":sorted(PRE_2026_WON),
  "daily_metrics":daily,
  "connectivity":connectivity,
  "archive":archives,
  "meeting_classification":{"excluded":{f"{d}|{t}":r for (d,t),r in EXCLUDED_MEETINGS.items()},
                            "included_count":inc_count,"excluded_count":exc_count,
                            "internal_only_count":internal_count},
  "coverage":{"progressed_shutoff":"first run seeds the baseline stage snapshot; diffs are accurate from the next run",
              "email_covered_from":EMAIL_COVERED_FROM,
              "linkedin_notes_covered_from":LI_NOTE_COVERED_FROM,
              "tasks_dated_by":"created_at (Attio exposes no completion timestamp)",
              "li_connects_attributed_by":"cadence Touch-1 completed connect task on the owner's deal",
              "junk_records":["6cd92151 (Rupert Wood) - website form naming a Jigcar colleague, counted as created"]}}

os.makedirs(f"{SP}/build",exist_ok=True)
json.dump(state,open(f"{SP}/build/dashboard_state.json","w"),indent=1,sort_keys=True)

payload={"RUN_STAMP":RUN_STAMP,"QUARTER_TARGET":QUARTER_TARGET,"daily":daily,
  "closedWonDeals":[{"name":e["name"],"arr":e["arr"],"date":e["date"],"owner":e["owner"],
                     "channel":e["channel"]} for e in q3_won],
  "contractDeals":contract_deals,
  "wonYTD":[{"name":e["name"],"arr":e["arr"],"owner":e["owner"],"quarter":e["quarter"],
             "channel":e["channel"]} for e in sorted(won_ytd,key=lambda x:x["quarter"])],
  "acqChannels":dict(acq.most_common()),
  "wonBookCount":len(closed_won),
  "connectivity":connectivity,"ranges":ranges,"rangeText":rangeText,"archives":archives,
  "coverage":state["coverage"]}
json.dump(payload,open(f"{SP}/build/payload.json","w"),indent=1)

print("=== VALIDATION ===")
print("deals:",len(deals),"| won book:",len(closed_won),"| contracts:",len(contracts))
print("meetings included:",inc_count,"excluded:",exc_count,"internal-only:",internal_count)
print("July meeting attendee-credits:",sum(sum(v) for v in meetings_daily.values()))
print("Q3 won:",sum(e['arr'] for e in q3_won),[ (e['name'],e['arr'],e['owner']) for e in q3_won])
print("contract out:",sum(c['arr'] for c in contract_deals))
print("acq (full won book):",dict(acq))
print("won 2026:",[(e['name'],e['quarter'],e['owner'],e['arr']) for e in won_ytd])
for q,a in archives.items():
    print(q,"created",a["createdCount"],"pipeline",a["createdPipeline"],"won",len(a["closedWon"]),"outcomes",a["outcomes"])
