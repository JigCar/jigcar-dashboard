# -*- coding: utf-8 -*-
"""Turn the Zelt absence feed into per-person leave dates.

Source: the Zelt calendar, not "Jigcar holidays". That second calendar still
exists and the routine has access, but it holds no events after mid-2025, so
reading it would report everyone as present every day.

Two date conventions live in the same feed and both have to be handled:
  - single day  : Zelt writes start == end, which under Google's normal
                  exclusive-end rule would be a zero-length event
  - multi-day   : the end date is exclusive, e.g. a one-day bank holiday is
                  stored as 31 Aug -> 1 Sep
Treating either rule as universal gets one of the two cases wrong, so the rule
here is: end <= start means a single day, otherwise expand to end-exclusive.
"""
import json, os, re, datetime

SP = os.environ.get("JIGCAR_SP") or os.path.dirname(os.path.abspath(__file__))
REPS = ["Chris", "Luke", "James", "Bianca", "Elliott", "Rupert"]
EMAIL_TO_REP = {
    "chris.white@jigcar.com": "Chris", "luke.nogueira@jigcar.com": "Luke",
    "james.griffin@jigcar.com": "James", "bianca.monteiro@jigcar.com": "Bianca",
    "elliott@jigcar.com": "Elliott", "rupert@jigcar.com": "Rupert",
}
# Public-holiday rows carry no attendee, so the person is read off the summary.
NAME_TO_REP = {
    "chris white": "Chris", "luke nogueira": "Luke", "james griffin": "James",
    "bianca monteiro": "Bianca", "elliott perks": "Elliott", "elliott": "Elliott",
    "rupert wood": "Rupert", "rupert": "Rupert",
}
SKIP = ("birthday", "work anniversary")


def d(s):
    return datetime.date(*[int(x) for x in s.split("-")])


def expand(start, end):
    a, b = d(start), d(end)
    if b <= a:
        return [a]
    out, cur = [], a
    while cur < b:                      # end exclusive for genuine multi-day rows
        out.append(cur)
        cur += datetime.timedelta(days=1)
    return out


def person_of(ev):
    em = (ev.get("email") or "").lower()
    if em in EMAIL_TO_REP:
        return EMAIL_TO_REP[em]
    s = ev["summary"]
    m = re.search(r"\bfor ([A-Z][A-Za-z'\-]*(?: [A-Z][A-Za-z'\-]*)*)\s*$", s)
    who = m.group(1) if m else re.split(r"\s+(?:Paid time off|Away)\b", s)[0]
    key = who.strip().lower()
    if key in NAME_TO_REP:
        return NAME_TO_REP[key]
    return who.strip()                  # non-scorecard colleague, kept for the off-today line


def half_of(s):
    if re.search(r"\(AM\)", s, re.I):
        return "AM"
    if re.search(r"\(PM\)", s, re.I):
        return "PM"
    return None


raw = json.load(open(f"{SP}/raw/leave_events.json"))
by_person = {}
by_date = {}
for ev in raw["events"]:
    s = ev["summary"]
    if any(k in s.lower() for k in SKIP):
        continue
    who = person_of(ev)
    half = half_of(s)
    for day in expand(ev["start"], ev["end"]):
        iso = str(day)
        by_person.setdefault(who, {})[iso] = half or "FULL"
        by_date.setdefault(iso, []).append({"person": who, "half": half})

out = {"source": raw["_source"], "pulled": raw["_pulled"], "range": raw["_range"],
       "by_person": {k: dict(sorted(v.items())) for k, v in sorted(by_person.items())},
       "by_date": {k: v for k, v in sorted(by_date.items())},
       "scorecard_people": REPS}
json.dump(out, open(f"{SP}/raw/leave.json", "w"), indent=1)

print("people with leave in range:", len(by_person))
for who in REPS:
    days = out["by_person"].get(who, {})
    if days:
        print(f"  {who:8} {len(days)} day(s): " + ", ".join(f"{k}{'' if v=='FULL' else ' ('+v+')'}"
                                                            for k, v in list(days.items())[:8]))
others = [w for w in out["by_person"] if w not in REPS]
print("non-scorecard colleagues with leave:", len(others))
