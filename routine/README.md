# Team Momentum routine

Rebuilds `index-18.html` at the repo root each weekday at 08:00 and commits the
refreshed `dashboard_state.json` alongside it. GitHub Pages serves the result at
https://jigcar.github.io/jigcar-dashboard/index-18.html

## Run order

1. `parse_granola.py` - parses the Granola meeting dump into `raw/granola.json`.
2. `etl.py` - deterministic transform. Loads the deal pages, classifies meetings,
   computes every scorecard metric per person per day, and writes
   `dashboard_state.json` plus `payload.json`.
3. `render.py` - injects the payload into the canonical template and writes
   `index-18.html`.
4. `qa.py` - the two output checks below. The build is not committed if either fails.
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
- LinkedIn connections carry no rep in Attio: the "LinkedIn invitation sent" note has
  no author and no owner. They are attributed via the cadence Touch-1 completed
  connect task on the owner's deal until Groovin per-seat data is wired, and the
  residual gap between Groovin's event count and the attributed count is recorded in
  `coverage.li_connect_gap`.
- LinkedIn messages are rep-attributed from the chat-note title and counted once per
  person/company note pair. The deal split is a real company -> deal join in code.
- Email is a de-duped multi-mailbox sent count keyed on (sender, subject, sent_at).
  Attio has no public emails REST endpoint, so the period is paged through the MCP
  search and filtered by sender. Coverage starts at `coverage.email_covered_from`;
  earlier days in the period are a labelled floor, never a zero.
- Rupert's own mailbox is not connected, so his sends are only visible where a
  teammate was a recipient. His email figure is a floor and his Email seat reads
  `partial`. Rupert has no Allo account either, so his Allo seat reads `na`.

## Output QA (both must pass before committing)

1. Every `getElementById` target, including prefix-built ones, resolves to an
   `id="..."` in the markup. One mismatch blanks the whole page.
2. Every top-level render call is wrapped in its own try/catch.

Charts are (re)built when a tab becomes visible, because a chart drawn inside a
hidden tab renders at zero height.
