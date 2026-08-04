# Team Momentum routine

Rebuilds `index-18.html` at the repo root each weekday at 08:00 and commits the
refreshed `dashboard_state.json` alongside it. GitHub Pages serves the result at
https://jigcar.github.io/jigcar-dashboard/index-18.html

## Run order

Pull steps first. Each writes only to `raw/`, so a transform never calls an API.

0a. `pull_attio.py` - deals, companies, tasks and the note index over the Attio REST
   API. Also builds `domain_deal.json`, the single deal-association test used by
   every `(deal)` metric, and `join_report.json`, its coverage.
0b. `pull_linkedin.py` - fetches the Groovin invitation note **bodies** and attributes
   requests sent, connections made and messages per person.
1. `parse_granola.py` - parses the Granola meeting dump into `raw/granola.json`. The
   dump path is passed in or discovered; it is never hardcoded.
1b. `parse_leave.py` - parses the Zelt absence feed into `raw/leave.json`.
1c. `parse_allo.py` - regroups the transcribed Allo call records into `raw/calls.json`
   per person per day. The seat list is confirmed each run with `allo_list_users` and
   the per-seat totals are reconciled against `allo_get_team_analytics`, so the daily
   tally is a regrouping of real call records rather than a figure typed in by hand.
1c. `classify_emails.py` - tallies sent emails per person per day from the paged MCP
   search, de-duped across mailbox copies, splits them by what the recipient is to
   us, and records the coverage window. Days it did not page are carried forward
   from the previous state, never rebuilt as zero.
2. `etl.py` - deterministic transform. Reads every metric from `raw/`, diffs the
   stage snapshot, and writes `dashboard_state.json` plus `payload.json`. It holds
   no metric values of its own.
3. `render.py` - injects the payload into the canonical template and writes
   `index-18.html`.
4. `qa.py` - the static output checks below. The build is not committed if any fails.
4b. `qa_browser.mjs` - loads the built file in headless Chromium and asserts the DATA
   renders, once with the chart CDN blocked and once with it served. **This is the
   check that matters.** The static QA once passed on a page that was completely
   blank, because it verified each render call sat in its own try/catch while the
   script was dying before those functions were even defined.
   Run: `node routine/qa_browser.mjs <path>/index-18.html` (needs `playwright`).

   In the sandbox `playwright` is installed **globally**, at
   `/opt/node22/lib/node_modules`, and there is no `node_modules` in this repo. ESM
   resolves bare imports from the importing file's own directory upwards, not from
   the working directory, so running the script from its place in `routine/` fails
   with ERR_MODULE_NOT_FOUND however you set the cwd. Copy it next to the package
   and run it there:

       cp routine/qa_browser.mjs /opt/node22/lib/node_modules/_jigcar_qa_browser.mjs
       node /opt/node22/lib/node_modules/_jigcar_qa_browser.mjs "$PWD/build/index-18.html"

   Pass an ABSOLUTE path: the script builds a `file://` URL from argv[2], and a
   relative one becomes `file://build/...`, which fails as ERR_INVALID_URL. Never run
   `playwright install`; `PLAYWRIGHT_BROWSERS_PATH` already points at the bundled
   Chromium at `/opt/pw-browsers/chromium`.
5. `slack_messages.py` - builds the two per-channel messages and prints them for
   review before anything is posted.

All of these read `JIGCAR_SP` for the working directory, so a run is reproducible
from any checkout.

All metric values are computed in plain code so they are reproducible run to run.
The model is used only for the written "Read & actions" narrative and for
interpreting connectivity status. It never invents a metric value.

## What the state file carries

- `stage_snapshot` - `{record_id: {stage, owner, value}}` for the next run's diff.
- `won_dates` - stamped when a deal first enters Closed Won, plus the confirmed
  back-book dates.
- `daily_metrics` - one row per person per day, feeding the period toggle and trend.
- `connectivity` - last run's per-connector and per-seat status.
- `archive` - frozen per-quarter snapshots.
- `meeting_classification` - the auditable include/exclude decision per meeting.
- `coverage` - the stated limits for the run.

## Known coverage limits

- Progressed / shut off need two snapshots. The first run seeds the baseline and
  both read 0 by construction; they are never backfilled.
- Tasks are dated by `completed_at` from the Attio tasks REST endpoint, which does
  expose a completion timestamp. An earlier build dated them by creation; that was
  wrong and has been corrected.
- LinkedIn invitations carry the rep in the note **body**, not the title: sent reads
  "from <Rep> to <Contact>", accepted reads "<Rep> is now connected with <Contact>".
  So requests sent and connections made are both attributed to a named person from
  Attio alone. An earlier build read only the title, found no rep, and fell back to
  counting cadence Touch-1 tasks; that credited the task assignee rather than the
  sender and was wrong by a wide margin (one person read 12 connects against 3
  actually sent, another 5 against 32). **That proxy is removed and must not return.**
- LinkedIn messages are rep-attributed from the chat-note title. Every event writes a
  person-side and a company-side note, so events are deduped on (date, rep, contact,
  kind) and the company side supplies the deal join.
- Connections made lag the invitation that earned them, often by weeks, so a high
  accepted count reflects earlier outreach rather than work done in the period.
- **Every LinkedIn column is a floor, because of a Groovin pairing gap.** Groovin
  writes the invitation into Attio only for a profile PAIRED to a CRM contact with
  sync enabled (see `toggle_linkedin_sync`: enabling is what "tracks the LinkedIn
  invitation/connection state in the CRM"). An invitation to an unpaired profile is
  sent on LinkedIn and never writes a note, so it cannot be counted. Measured 4 Aug
  2026 against LinkedIn on the one seat this routine can read directly: 122
  still-pending sent invitations since 14 Jul, of which 57 were paired, against 61
  sent recorded in Attio. So the true figure is at least double the recorded one on
  the BEST-covered seat.
  This is not a parsing fault and must not be "fixed" in the parser: all 597
  invitation bodies parse and every one of the 352 deduped events carries a named rep,
  so nothing present in Attio is missed. What is missing never arrived. It understates
  most for whoever prospects contacts who are not yet in Attio, which is why Chris and
  Luke read lowest. Every Groovin seat therefore reads `partial`, never `ok`, and a low
  LinkedIn figure is evidence about pairing rather than about effort. Closing it means
  pairing those profiles in Groovin and enabling sync, which is a Groovin action, not
  a change to this routine.
- LinkedIn returns week-granular dates for older invitations, so LinkedIn events are
  dated by when Groovin recorded them. Day-level LinkedIn attribution is approximate
  beyond roughly the last week, and one unusually large day is more likely a sync
  catching up than a day's work. Do not let LinkedIn drive a celebration trigger.
- The stage diff RECORDS moves for every owner, including the back-book owners, and
  only the per-person scorecard columns are restricted to the six. An earlier build
  dropped non-scorecard owners before recording the move, which hid a £36,000 deal
  moving into Contracts from the move log, from "what moved" and from the celebration
  trigger. It also skipped the won-date stamp, so a back-book owner closing a deal
  would never have been dated and would never have reached closed-won revenue.
- Because the table has a column per scorecard person while the revenue panels count
  every owner, the banner can legitimately exceed the table's Contract out and Closed
  won totals. The page states the difference and names the deals whenever it is
  non-zero, so the gap cannot read as an error.
- `perf_flags` is merged from the diff baseline AND the published state at the repo
  root. The baseline is yesterday's snapshot, so on a same-day re-run it does not know
  about a flag an earlier run wrote today; taking only the baseline reset the streak.
- Email is a de-duped multi-mailbox sent count keyed on (sender, subject, sent_at).
  Attio has no public emails REST endpoint, so the period is paged through the MCP
  search and filtered by sender. Coverage starts at `coverage.email_covered_from`;
  earlier days in the period are a labelled floor, never a zero.
- Rupert's own mailbox is not connected, so his sends are only visible where a
  teammate was a recipient. His email figure is a floor and his Email seat reads
  `partial`. Rupert has no Allo account either, so his Allo seat reads `na`.
- A day that was paged end to end but held no team sends is written as an explicit
  zero row, not left absent, and the split window is the union of what earlier runs
  recorded with what this run paged. The 08:00 run routinely pages a day before
  anyone has sent anything: deriving the window from the sends alone collapsed it to
  null and would have published an unlabelled split, which is exactly the "0 that
  means unclassified" the spec forbids.

## Output QA (all must pass before committing)

1. Every `getElementById` target, including prefix-built ones, resolves to an
   `id="..."` in the markup. One mismatch blanks the whole page.
2. Every top-level render call is wrapped in its own try/catch.
3. The run stamp is embedded in the built file.
4. The built JavaScript parses (`node --check`). A parse error blanks the page just
   as thoroughly as a bad id, and no amount of inspection catches it reliably.
5. The summary table's header, body and totals rows have equal column counts. A
   mismatch misaligns the table silently, which is worse than a crash.

Charts are (re)built when a tab becomes visible, because a chart drawn inside a
hidden tab renders at zero height.

## Time period filter

Today / Yesterday / This week / Last week / This month / This quarter. `etl.py` owns
the date maths and writes `ranges` and `rangeText`; the toggle and `agg()` are generic
over whatever keys those hold, so a new period needs a range entry, a button and a
`viewLabel` entry, nothing more. `trailing7` is deliberately in `ranges` but has no
button: it is the Slack performance basis, not a UI view.

Both week views run Monday to Sunday. This week is capped at the run date and labelled
"week to date" with the day count. Last week is the previous whole week, always seven
days, derived by stepping back from this week's Monday so it keeps landing on week
boundaries whatever day the routine runs. Both labels carry the year when the span
crosses one.

The week views append a coverage caveat built from `coverage.email_covered_from`,
`calls_covered_from`, `linkedin_notes_covered_from` and `email_split_from`. Last week
reaches further back than this week, so it is the view most likely to predate a
connector switch-on. The split window matters most: outside it the Emails column shows
`(0)`, which means unclassified, not unrelated. Each caveat drops out on its own once
coverage predates the range, so nothing needs editing as coverage accumulates.

## Two ways this page has come out blank. Do not reintroduce either.

1. **An unguarded `Chart` reference at the top of the script.** Chart.js is fetched
   from a CDN. When it did not arrive, `Chart.defaults.color=...` threw a
   ReferenceError before any render function was defined, so the entire page was
   empty. `CHART_OK` now guards it and a stub satisfies `new Chart()` / `.destroy()`,
   so a missing library costs the graphs and never the numbers. A visible amber
   notice says so, because a blank graph must not read as zero data.
2. **A wrong `connectivity` shape.** `workspace` must be an ARRAY of
   `{name,status,note}` and `seats` must be keyed by PERSON with a 3-item
   `[Allo, Email, Groovin]` list. The scorecard reads `connectivity.seats[r][0]` for
   the Calls cell, so a wrong shape blanks the metric cards and the summary table as
   well as the connector panel. `etl.py` now validates this and exits non-zero.

Neither was caught by static QA. Both are caught by `qa_browser.mjs`.
