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
1c. `classify_emails.py` - tallies sent emails per person per day from the paged MCP
   search, de-duped across mailbox copies, splits them by what the recipient is to
   us, and records the coverage window. Days it did not page are carried forward
   from the previous state, never rebuilt as zero.
2. `etl.py` - deterministic transform. Reads every metric from `raw/`, diffs the
   stage snapshot, and writes `dashboard_state.json` plus `payload.json`. It holds
   no metric values of its own.
3. `render.py` - injects the payload into the canonical template and writes
   `index-18.html`.
4. `qa.py` - the output checks below. The build is not committed if any fails.
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
- Email is a de-duped multi-mailbox sent count keyed on (sender, subject, sent_at).
  Attio has no public emails REST endpoint, so the period is paged through the MCP
  search and filtered by sender. Coverage starts at `coverage.email_covered_from`;
  earlier days in the period are a labelled floor, never a zero.
- Rupert's own mailbox is not connected, so his sends are only visible where a
  teammate was a recipient. His email figure is a floor and his Email seat reads
  `partial`. Rupert has no Allo account either, so his Allo seat reads `na`.

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
