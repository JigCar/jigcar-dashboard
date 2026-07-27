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
- Attio exposes no task completion timestamp, so tasks are dated by creation.
- LinkedIn connections carry no rep in Attio. They are attributed via the cadence
  Touch-1 completed connect task on the owner's deal until Groovin per-seat data
  is wired.
- Email is a de-duped multi-mailbox sent count. Attio's email search cannot be
  filtered to the company's own domain, so the routine pulls the period and filters
  by sender itself; history accumulates one day per run.

## Output QA (both must pass before committing)

1. Every `getElementById` target, including prefix-built ones, resolves to an
   `id="..."` in the markup. One mismatch blanks the whole page.
2. Every top-level render call is wrapped in its own try/catch.

Charts are (re)built when a tab becomes visible, because a chart drawn inside a
hidden tab renders at zero height.
