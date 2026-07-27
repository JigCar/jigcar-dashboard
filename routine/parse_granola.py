# -*- coding: utf-8 -*-
"""Parse the Granola meeting dump into raw/granola.json.

The MCP result is oversized and overflows to a file, which is what we want: the
path is passed in rather than reading hundreds of meetings into context.

Path resolution, in order: argv[1], $JIGCAR_GRANOLA_FILE, else the newest
mcp-Granola-list_meetings-*.txt under the tool-results directory. Hardcoding one
dump path meant a later run silently re-parsed the previous run's pull.
"""
import re, json, collections, os, sys, glob

SP = os.environ.get("JIGCAR_SP") or os.path.dirname(os.path.abspath(__file__))


def find_dump():
    if len(sys.argv) > 1:
        return sys.argv[1]
    if os.environ.get("JIGCAR_GRANOLA_FILE"):
        return os.environ["JIGCAR_GRANOLA_FILE"]
    pats = glob.glob("/root/.claude/projects/*/*/tool-results/mcp-Granola-list_meetings-*.txt")
    if not pats:
        raise SystemExit("no Granola dump found; pass the path as argv[1]")
    return max(pats, key=os.path.getmtime)


F = find_dump()
raw = open(F, encoding="utf-8").read()
blocks = re.findall(r'<meeting id="([^"]+)" title="([^"]*)" date="([^"]*)">\s*'
                    r'<known_participants>(.*?)</known_participants>', raw, re.S)
MONTH = {'Jan': 1, 'Feb': 2, 'Mar': 3, 'Apr': 4, 'May': 5, 'Jun': 6,
         'Jul': 7, 'Aug': 8, 'Sep': 9, 'Oct': 10, 'Nov': 11, 'Dec': 12}
meetings = []
for mid, title, date, parts in blocks:
    m = re.match(r'(\w{3}) (\d{1,2}), (\d{4})', date.strip())
    if not m:
        continue
    iso = "%04d-%02d-%02d" % (int(m.group(3)), MONTH[m.group(1)], int(m.group(2)))
    emails = [e.strip().lower() for e in re.findall(r'<([^>]+@[^>]+)>', parts)]
    creator = None
    cm = re.search(r"([A-Za-z .'-]+)\(note creator\)[^<]*<([^>]+)>", parts)
    if cm:
        creator = cm.group(2).strip().lower()
    meetings.append({"id": mid, "title": title.strip(), "date": iso,
                     "emails": emails, "creator": creator})

os.makedirs(f"{SP}/raw", exist_ok=True)
json.dump(meetings, open(f"{SP}/raw/granola.json", "w"), indent=0)
print("dump:", F)
print("meetings parsed:", len(meetings))
internal = [m for m in meetings if m["emails"] and all(e.endswith("@jigcar.com") for e in m["emails"])]
external = [m for m in meetings if not (m["emails"] and all(e.endswith("@jigcar.com") for e in m["emails"]))]
print("internal-only:", len(internal), " with-external:", len(external))
print("date span:", min((m["date"] for m in meetings), default="-"),
      "->", max((m["date"] for m in meetings), default="-"))
dom = collections.Counter()
for m in external:
    for e in m["emails"]:
        d = e.split("@")[-1]
        if d != "jigcar.com":
            dom[d] += 1
print("\n=== external domains (participant appearances) ===")
for d, c in dom.most_common(200):
    print(f"{c:3d}  {d}")
print("\n=== external meetings, deduped by (date, title) ===")
seen = set()
for m in sorted(external, key=lambda x: (x["date"], x["title"])):
    k = (m["date"], m["title"])
    if k in seen:
        continue
    seen.add(k)
    ext = sorted({e.split("@")[-1] for e in m["emails"] if not e.endswith("@jigcar.com")})
    jig = sorted({e.split("@")[0] for e in m["emails"] if e.endswith("@jigcar.com")})
    print(f"{m['date']}  {m['title'][:54]:54} ext={','.join(ext)[:40]:40} jig={','.join(jig)[:30]}")
