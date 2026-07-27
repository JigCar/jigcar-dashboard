import re, json, collections
F="/root/.claude/projects/-home-user-jigcar-dashboard/b183b5d1-3506-53f2-a1fc-bfac32d1ea9e/tool-results/mcp-Granola-list_meetings-1785157095976.txt"
raw=open(F,encoding="utf-8").read()
blocks=re.findall(r'<meeting id="([^"]+)" title="([^"]*)" date="([^"]*)">\s*<known_participants>(.*?)</known_participants>',raw,re.S)
MONTH={'Jan':1,'Feb':2,'Mar':3,'Apr':4,'May':5,'Jun':6,'Jul':7,'Aug':8,'Sep':9,'Oct':10,'Nov':11,'Dec':12}
meetings=[]
for mid,title,date,parts in blocks:
    m=re.match(r'(\w{3}) (\d{1,2}), (\d{4})',date.strip())
    iso="%04d-%02d-%02d"%(int(m.group(3)),MONTH[m.group(1)],int(m.group(2)))
    emails=re.findall(r'<([^>]+@[^>]+)>',parts)
    emails=[e.strip().lower() for e in emails]
    # note creator
    creator=None
    cm=re.search(r'([A-Za-z .\'-]+)\(note creator\)[^<]*<([^>]+)>',parts)
    if cm: creator=cm.group(2).strip().lower()
    meetings.append({"id":mid,"title":title.strip(),"date":iso,"emails":emails,"creator":creator})
json.dump(meetings,open("raw/granola.json","w"),indent=0)
print("meetings parsed:",len(meetings))
internal=[m for m in meetings if all(e.endswith("@jigcar.com") for e in m["emails"]) and m["emails"]]
external=[m for m in meetings if not(all(e.endswith("@jigcar.com") for e in m["emails"]) and m["emails"])]
print("internal-only:",len(internal)," with-external:",len(external))
dom=collections.Counter()
for m in external:
    for e in m["emails"]:
        d=e.split("@")[-1]
        if d!="jigcar.com": dom[d]+=1
print("\n=== external domains (count of participant-appearances) ===")
for d,c in dom.most_common(200): print(f"{c:3d}  {d}")
