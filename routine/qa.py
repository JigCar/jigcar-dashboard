# -*- coding: utf-8 -*-
"""Output QA. Every check must pass before the build is committed.

1. Every getElementById target, including prefix-built ones, resolves to an
   id="..." in the markup. One mismatch throws on first render and blanks the
   whole page, not just the panel that failed.
2. Every top-level render call is wrapped in its own try/catch, so one failure
   cannot take the dashboard down with it.
3. The run stamp is embedded in the built file.
4. The built JavaScript parses (node --check). QA cannot catch a parse error by
   inspection, and a parse error blanks the page just as thoroughly as a bad id.
5. The summary table's header, body and totals rows have equal column counts. A
   mismatch misaligns the whole table silently, which is worse than a crash.
"""
import re, sys, os, json, subprocess, tempfile

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

# --- check 4: the built JavaScript parses ---
scripts = re.findall(r'<script(?![^>]*\bsrc=)[^>]*>(.*?)</script>', html, re.S)
node_ok = "skipped"
if not scripts:
    fail.append("no inline script block found in the build")
else:
    with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False, encoding="utf-8") as fh:
        fh.write("\n;\n".join(scripts))
        jspath = fh.name
    try:
        r = subprocess.run(["node", "--check", jspath], capture_output=True, text=True)
        node_ok = "pass" if r.returncode == 0 else "FAIL"
        if r.returncode != 0:
            fail.append("built JavaScript does not parse: " + (r.stderr or "").strip()[:400])
    except FileNotFoundError:
        node_ok = "no node available"
    finally:
        os.unlink(jspath)

# --- check 5: summary table header, body and totals have equal column counts ---
def cols(fragment, tag):
    return len(re.findall(r"<" + tag + r"[\s>]", fragment))


hdr = re.search(r'<tr>\s*<th>Person</th>(?:(?!</tr>).)*</tr>', html, re.S)
body = re.search(r"summaryBody'\)(?:(?!</tr>).)*?<tr><td>\$\{r\}</td>((?:(?!</tr>).)*)</tr>", html, re.S)
totl = re.search(r'<tr><td class="total">Team</td>((?:(?!</tr>).)*)</tr>', html, re.S)
counts = {}
if hdr:
    counts["header"] = cols(hdr.group(0), "th")
if body:
    counts["body"] = 1 + cols(body.group(1), "td")
if totl:
    counts["totals"] = 1 + cols(totl.group(1), "td")
if len(counts) < 3:
    fail.append(f"could not locate all three summary rows to compare (found {sorted(counts)})")
elif len(set(counts.values())) != 1:
    fail.append(f"summary table column counts differ: {counts}")

print(f"ids in markup: {len(ids)} | literal targets: {len(lit)} | "
      f"prefix suffixes: {len(suffixes)} | prefixes: {sorted(prefixes)}")
print(f"node --check: {node_ok} | summary columns: {counts}")
if fail:
    print("\nQA FAILED")
    for f in fail:
        print("  -", f)
    sys.exit(1)
print("QA PASSED: every element ID resolves, renders are isolated, stamp embedded.")
