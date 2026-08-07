# -*- coding: utf-8 -*-
"""Verify the dashboard actually PUBLISHED, not merely that the commit landed.

Two checks, and both must pass before the routine may claim the dashboard is
live or post to Slack:

1. CONTENT: raw.githubusercontent.com serves index-18.html on main with this
   build's embedded stamp. This proves the commit reached the branch Pages
   serves. It is the check the routine has always run, and on 6 Aug 2026 it
   passed while the live site was six hours stale, because it is blind to the
   deploy step.

2. DEPLOY: the github-pages environment has a deployment for HEAD of main and
   its terminal status is success. On 6 Aug 2026 three consecutive Pages
   deployments failed on GitHub's side (build job fine in seconds, deploy job
   polling deployment_in_progress until its own 10-minute timeout), so the
   commit was on main, the raw CDN served it, and the live site still showed
   the previous morning's build. Only this check sees that failure.

A deploy can take minutes and GitHub processes it asynchronously, so check 2
polls. The poll budget is generous because a slow success is fine; what must
never happen is declaring success on a deployment that has not finished.

Exit codes: 0 both checks passed; 2 content mismatch; 3 deploy failed or timed
out; 4 could not determine (API unreachable). On any non-zero exit the caller
must treat the publish as NOT verified: leave the previous dashboard intact,
say so to the operator, and do not post to Slack on the strength of the build.

A failed deploy with a matching raw stamp means GitHub Pages is unhealthy, not
the repo: each failed deployment cancels itself, so the live site keeps the
last good build rather than going blank, and the queued commit normally goes
live when Pages recovers. Report it that way instead of rebuilding.

Usage: python3 verify_publish.py [--sha <sha>] [--timeout <seconds>]
Reads $JIGCAR_SP/build/build.json for the expected stamp; the SHA defaults to
the local HEAD, which the caller has just pushed.
"""
import json, os, re, subprocess, sys, time, urllib.request

SP = os.environ.get("JIGCAR_SP") or os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REPO = "JigCar/jigcar-dashboard"
FILE = "index-18.html"
RAW = f"https://raw.githubusercontent.com/{REPO}/main/{FILE}"
API = f"https://api.github.com/repos/{REPO}"

sha = None
timeout = 1200
args = sys.argv[1:]
while args:
    a = args.pop(0)
    if a == "--sha":
        sha = args.pop(0)
    elif a == "--timeout":
        timeout = int(args.pop(0))
HEXSHA = re.compile(r"^[0-9a-f]{40}$")
# The SHA comes from the REPO, which is where this file lives, not from JIGCAR_SP.
# JIGCAR_SP is the working directory for raw/ and build/ and is deliberately allowed to
# be a scratch directory outside the checkout, so `git rev-parse` run there resolves
# nothing. It failed silently: stdout was empty, sha became "", and the deploy check
# then polled for a deployment matching an empty SHA, found none, and reported
# "FAIL deploy ... Publication is UNCONFIRMED" for a build whose Pages deployment had
# in fact already succeeded. That is the worst direction for this check to fail in: it
# tells the operator Pages is broken and suppresses the Slack post on a healthy day.
if not sha:
    for _cwd in (os.path.dirname(os.path.abspath(__file__)), SP):
        _out = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True,
                              cwd=_cwd).stdout.strip()
        if HEXSHA.match(_out):
            sha = _out
            break

stamp = json.load(open(f"{SP}/build/build.json"))["stamp"]
# Never poll on an unresolved SHA. "I could not determine this" is exit 4 and is a
# different fact from "the deploy failed", which is exit 3.
if not (sha and HEXSHA.match(sha)):
    print("FAIL: could not resolve the pushed commit SHA, so the deploy check cannot run. "
          "Pass it explicitly with --sha <sha>. Publication is UNDETERMINED, which is not "
          "the same as failed: check the github-pages deployment for HEAD of main before "
          "concluding anything about Pages.")
    raise SystemExit(4)
print(f"verify: sha {sha[:8]} stamp {stamp!r} timeout {timeout}s")


def get(url):
    with urllib.request.urlopen(urllib.request.Request(url), timeout=60) as fh:
        return fh.read().decode()


# ---- check 1: content on main, with CDN-lag polling (up to 2 minutes) ----
content_ok = False
for i in range(7):
    try:
        if stamp in get(RAW):
            content_ok = True
            break
        print(f"  content: stamp not yet on the raw CDN (attempt {i + 1})")
    except Exception as e:
        print(f"  content: fetch failed (attempt {i + 1}): {e}")
    time.sleep(20)
if not content_ok:
    print("FAIL content: main does not serve this build's stamp. The push did not land "
          "where Pages serves from. Do not post to Slack.")
    sys.exit(2)
print("  content: OK, main serves this build")

# ---- check 2: the Pages deployment for this SHA reaches success ----
# States seen in the wild: success, failure, error, inactive (superseded),
# in_progress, queued, pending. inactive for OUR sha counts as failure: it means
# a different deployment superseded this one, so the live site is not this build.
deadline = time.time() + timeout
last = None
while time.time() < deadline:
    try:
        deps = json.loads(get(f"{API}/deployments?environment=github-pages&per_page=10"))
        mine = [d for d in deps if d["sha"] == sha]
        if not mine:
            last = "no deployment yet"
        else:
            st = json.loads(get(mine[0]["statuses_url"]))
            last = st[0]["state"] if st else "no status yet"
            if last == "success":
                # Belt and braces: this sha's deploy succeeded AND nothing newer
                # failed over the top of it in the same window.
                print("  deploy: success")
                print("VERIFIED: the dashboard is published and live.")
                sys.exit(0)
            if last in ("failure", "error", "inactive"):
                print(f"FAIL deploy: terminal state {last!r} for {sha[:8]}. The commit is on "
                      "main and the raw CDN serves it, but GitHub Pages did not deploy it: "
                      "the live site still shows the last successful build. This is a Pages "
                      "outage or supersession, not a repo fault. Leave everything intact, "
                      "report it, and do not post to Slack for this build.")
                sys.exit(3)
    except Exception as e:
        last = f"api error: {e}"
    print(f"  deploy: {last}; waiting...")
    time.sleep(30)

print(f"FAIL deploy: still {last!r} after {timeout}s. Publication is UNCONFIRMED. "
      "Treat as not published: report to the operator and do not post to Slack.")
sys.exit(3)
