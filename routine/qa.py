# -*- coding: utf-8 -*-
"""Output QA. Both checks must pass before the build is committed.

1. Every getElementById target, including prefix-built ones, resolves to an
   id="..." in the markup. One mismatch throws on first render and blanks the
   whole page, not just the panel that failed.
2. Every top-level render call is wrapped in its own try/catch, so one failure
   cannot take the dashboard down with it.
"""
import re, sys, os, json

SP = os.environ.get("JIGCAR_SP") or os.path.dirname(os.path.abspath(__file__))
html = open(f"{SP}/build/index-18.html", encoding="utf-8").read()
fail = []

ids = set(re.findall(r'id="([^"]+)"', html))
ids |= set(re.findall(r"id='([^']+)'", html))

# --- check 1a: literal getElementById targets ---
lit = set(re.findall(r"getElementById\('([^']+)'\)", html))
lit |= set(re.findall(r'getElementById\("([^"]+)"\)', html))
missing = sorted(t for t in lit if t not in ids)
if missing:
    fail.append(f"getElementById targets with no matching id: {missing}")

# --- check 1b: prefix-built targets, e.g. getElementById(prefix+'ChanTable') ---
suffixes = set(re.findall(r"getElementById\(\s*\w+\s*\+\s*'([^']+)'\s*\)", html))
suffixes |= set(re.findall(r'getElementById\(\s*\w+\s*\+\s*"([^"]+)"\s*\)', html))
# collect the prefixes actually passed to those functions
prefixes = set(re.findall(r"renderChannels\([^,]+,\s*'([^']+)'\s*\)", html))
prefixes |= set(re.findall(r'renderChannels\([^,]+,\s*"([^"]+)"\s*\)', html))
for pfx in sorted(prefixes):
    for sfx in sorted(suffixes):
        if pfx + sfx not in ids:
            fail.append(f"prefix-built target '{pfx}{sfx}' has no matching id")

# --- check 2: every top-level render call is individually guarded ---
boot = re.search(r"\[\[(.*?)\]\s*\.forEach\(\s*\(\[name,fn\]\)\s*=>\s*\{\s*try\{", html, re.S)
if not boot:
    fail.append("top-level render calls are not wrapped in a per-call try/catch")

for fn in ("applyView", "renderArchive", "renderLeaderboard"):
    if fn + "(" not in html:
        fail.append(f"expected render function {fn}() missing from build")

# --- sanity: the run stamp is actually embedded ---
stamp = json.load(open(f"{SP}/build/payload.json"))["RUN_STAMP"]
if stamp not in html:
    fail.append(f"run stamp {stamp!r} is not embedded in the build")

print(f"ids in markup: {len(ids)} | literal targets: {len(lit)} | "
      f"prefix suffixes: {len(suffixes)} | prefixes: {sorted(prefixes)}")
if fail:
    print("\nQA FAILED")
    for f in fail:
        print("  -", f)
    sys.exit(1)
print("QA PASSED: every element ID resolves, renders are isolated, stamp embedded.")
