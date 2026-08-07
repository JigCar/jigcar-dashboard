# -*- coding: utf-8 -*-
"""Parse the Granola meeting dump into raw/granola.json.

The MCP result is oversized and overflows to a file, which is what we want: the
path is passed in rather than reading hundreds of meetings into context.

Path resolution, in order: argv[1], $JIGCAR_GRANOLA_FILE, else the newest
mcp-Granola-list_meetings-*.txt under the tool-results directory. Hardcoding one
dump path meant a later run silently re-parsed the previous run's pull.
"""
import re, json, collections, os, sys, glob, html

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
# The meeting tag is matched attribute-by-attribute, tolerating any extras between
# date and the closing bracket. On 30 Jul 2026 Granola added captured_by_me /
# listed_as_participant / is_workspace_visible attributes and the previous strict
# pattern matched nothing, which would have silently published a zero-meeting
# dashboard; hence the tolerant pattern AND the hard failure below.
blocks = re.findall(r'<meeting id="([^"]+)" title="([^"]*)" date="([^"]*)"[^>]*>\s*'
                    r'<known_participants>(.*?)</known_participants>', raw, re.S)
_declared = re.search(r'<meetings_data[^>]*\bcount="(\d+)"', raw)
if not blocks and (_declared is None or int(_declared.group(1)) > 0):
    raise SystemExit("parse_granola: 0 meetings parsed from a dump that declares "
                     f"{_declared.group(1) if _declared else 'an unknown number of'} meetings. "
                     "The dump format has probably changed again. Refusing to overwrite "
                     "raw/granola.json with an empty list: a zero-meeting dashboard is a "
                     "silent lie, not a quiet day.")
MONTH = {'Jan': 1, 'Feb': 2, 'Mar': 3, 'Apr': 4, 'May': 5, 'Jun': 6,
         'Jul': 7, 'Aug': 8, 'Sep': 9, 'Oct': 10, 'Nov': 11, 'Dec': 12}
meetings = []
for mid, title, date, parts in blocks:
    m = re.match(r'(\w{3}) (\d{1,2}), (\d{4})', date.strip())
    if not m:
        continue
    iso = "%04d-%02d-%02d" % (int(m.group(3)), MONTH[m.group(1)], int(m.group(2)))
    # On 3 Aug 2026 the dump started HTML-escaping the participant block, so the
    # addresses arrived as &lt;a@b.com&gt; and the angle-bracket pattern matched
    # nothing at all. Every meeting parsed with zero attendees, which credits nobody
    # and reads as a team that took no external meeting all quarter. Unescape first,
    # which is a no-op on the older unescaped form, so both shapes parse.
    parts = html.unescape(parts)
    emails = [e.strip().lower() for e in re.findall(r'<([^>]+@[^>]+)>', parts)]
    creator = None
    cm = re.search(r"([A-Za-z .'-]+)\(note creator\)[^<]*<([^>]+)>", parts)
    if cm:
        creator = cm.group(2).strip().lower()
    # Titles are escaped in the same pass, and the exclusion list in etl.py is keyed
    # by the plain title, so "Show &amp; Tell" has to come back as "Show & Tell" or a
    # judged exclusion silently stops matching its meeting.
    # Start time, kept as minutes past midnight in the dump's own local offset. The
    # dump began carrying a clock time as well as a date, and it is the only signal
    # that separates two notes on one meeting from two genuinely separate meetings
    # with the same counterparty on the same day. -1 when the dump has no time.
    tm = re.search(r'(\d{1,2}):(\d{2})\s*([AP]M)', date)
    if tm:
        _h = int(tm.group(1)) % 12 + (12 if tm.group(3) == "PM" else 0)
        mins = _h * 60 + int(tm.group(2))
    else:
        mins = -1
    meetings.append({"id": mid, "title": html.unescape(title).strip(), "date": iso,
                     "mins": mins, "emails": emails, "creator": creator})

# A dump whose meetings all parse with no participants is the same class of silent
# failure as parsing no meetings, and it is worse to read: the page renders 154
# meetings and credits nobody, so every scorecard row shows 0 sales meetings and it
# looks like a quiet quarter rather than a broken parser. The 3 Aug 2026 escaping
# change did exactly this and the 0-meeting guard above did not catch it.
_with_emails = [m for m in meetings if m["emails"]]
if meetings and not _with_emails:
    raise SystemExit("parse_granola: parsed %d meetings but not one participant email. "
                     "The participant format has probably changed again. Refusing to "
                     "overwrite raw/granola.json: a dashboard that credits nobody for "
                     "any meeting is a silent lie, not a quiet quarter." % len(meetings))
if meetings and len(_with_emails) < 0.5 * len(meetings):
    raise SystemExit("parse_granola: only %d of %d meetings have any participant email. "
                     "That is too few to be real; the participant format has probably "
                     "changed for a subset. Refusing to overwrite raw/granola.json."
                     % (len(_with_emails), len(meetings)))

os.makedirs(f"{SP}/raw", exist_ok=True)
json.dump(meetings, open(f"{SP}/raw/granola.json", "w"), indent=0)
# The span this dump actually covers, written out so etl.py can tell "no meeting that
# day" apart from "that day is outside the dump". list_meetings defaults to a ROLLING
# last_30_days window, so a run on 7 Aug saw only from 8 Jul and the first week of the
# quarter fell out of the dump entirely. meetings is the one metric rebuilt purely from
# this pull with nothing to fall back on, so without this the Q3 meeting totals would
# quietly shed their oldest day every morning. Pull with an explicit custom range
# covering the quarter AND let the ETL carry forward anything older than the span.
json.dump({"from": min((m["date"] for m in meetings), default=None),
           "to": max((m["date"] for m in meetings), default=None),
           "dump": os.path.basename(F), "meetings": len(meetings)},
          open(f"{SP}/raw/granola_span.json", "w"), indent=1)
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
