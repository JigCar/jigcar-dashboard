import json, subprocess, concurrent.futures as cf
N=json.load(open('raw/notes.json'))
GRO="c020395f-1e1e-4a88-9d95-3c63937a06f8"
inv=[n for n in N if n['actor']==GRO and n['title'] in
     ('LinkedIn invitation sent','LinkedIn invitation accepted') and n['created']>='2026-07-01']
print("invitation notes to fetch:",len(inv))
def get(n):
    out=subprocess.run(["curl","-s",f"https://api.attio.com/v2/notes/{n['id']}"],capture_output=True,text=True).stdout
    try: d=json.loads(out).get("data",{})
    except Exception: return None
    return {**n,"body":(d.get("content_plaintext") or "").strip()}
with cf.ThreadPoolExecutor(max_workers=8) as ex:
    res=[r for r in ex.map(get,inv) if r]
json.dump(res,open('raw/invite_notes.json','w'),indent=0)
print("fetched:",len(res),"| with a body:",sum(1 for r in res if r['body']))
