# Claude Code task: rebuild the Jigcar Team Momentum dashboard as a daily routine

## Goal

Regenerate the Jigcar Team Momentum dashboard every weekday at 08:00. Pull fresh data from the
connected tools, build a single self-contained HTML file, commit it to a GitHub repo served by
GitHub Pages, and post the link to two Slack channels: `#operation-foot-down` and `#deal-updates`.
No Slack Canvas, no file uploads to Slack.

## The canonical template is the code, not this prompt

**`routine/render.py` in the repo is the template.** It is the only source of truth for layout,
markup, styling and client-side behaviour. Wire live data into it and publish. Do not rebuild the
page from any HTML pasted into a prompt, including earlier versions of this one: doing so silently
reverts every improvement made since that snapshot was taken.

If you need to change the page, change `render.py` and commit it.

**"The code wins" covers layout and markup, never facts.** A sentence in the template that asserts
something about the data — how many deals moved today, which ones, what a total is — is data wearing
markup's clothes, and this rule would otherwise protect it forever. One had already been written in
as prose about "today's diff" naming four specific deals, and it would have gone stale by the next
morning while reading as authoritative. Any narrative that states a number or a name must be built
from the payload at render time. If you find one hardcoded, replace it with a span the render fills.

## This prompt is the specification for behaviour. The committed code must follow it.

The routine's source lives in `routine/`. That code is what executes, so **when this prompt and the
code disagree on behaviour, the prompt wins and the code must be changed to match**, in the same
run, and committed. Never preserve existing behaviour on the grounds that it is what previously ran.

The exception is the template itself, above: for layout and markup, the code wins.

On every run, before posting anything:

1. Re-read the Slack notification section and compare it against what the code will actually emit.
2. If they differ, change the code first and commit it.
3. Print the exact text destined for each channel so it can be checked before it goes.

A formatting regression in Slack is visible to the whole team rather than to the operator.

## Non-negotiables

1. **Do not fabricate numbers.** Every figure traces to a real pull. Where a signal does not exist,
   render `unknown`, a labelled floor, or `0` with a coverage note, never a guess. This outranks
   completeness.
2. **Deterministic ETL, model only for judgement.** All pulls, tallies, diffs and dating happen in
   plain code so the numbers are reproducible. The model writes only the "Read & actions" narrative
   and interprets connectivity. It never invents a metric value.
3. **The routine keeps its own history**, in `dashboard_state.json` committed to the repo. This is
   how progressed, shut off and real won-dates become accurate: by diffing today's snapshot against
   yesterday's, not by trusting a field Attio does not expose.
4. **State the coverage of every metric.** A metric that covers part of a period must say so on the
   page. A total that reads 0 because it was never classified is worse than no figure at all.
5. **Never judge a person on a number the data cannot support.** See the leave rules and the Slack
   performance rules below. This has gone wrong before and it is the most damaging failure mode
   this routine has.

## Cadence, hosting, output

Hosted on GitHub Pages from a public repo, one persistent URL, no authentication. That is
deliberate: do not add, request or wait for an access policy.

**Environment requirement.** Two separate things, which fail differently:

1. **Egress to `api.github.com`.** If denied by network policy, stop and report. Do not route around
   it and do not substitute another delivery method.
2. **Repo access granted to the session.** `JigCar/jigcar-dashboard` must be attached with write
   access. This is not the same as the PAT. Diagnostic: if `api.github.com/user` authenticates but
   `api.github.com/repos/<any public repo>` returns 403, the block is the session's repo gate, not
   the token or org approval, so regenerating the token is wasted effort. Say so and stop.

Confirm both before anything else and report which one is missing.

**Commit straight to `main`. This runs unattended, so nothing may wait on a human.**

- Push directly to `main`. No feature branch, no pull request, no review request.
- Pages serves from `main`, so a commit on any other branch leaves the live page unchanged even
  though the run otherwise looks successful.
- If a direct push to `main` is rejected, stop and report that specifically. Do not fall back to a
  branch and pull request: that silently breaks the daily publish.
- If another commit lands on `main` first, **merge, do not force**. Re-read the newer content, apply
  your changes on top, and republish. A human editing the page directly is a signal, not a
  collision to overwrite.

**Verifying the publish.** The sandbox cannot reach `jigcar.github.io`, so a failed fetch of that
URL is not a failed publish. Verify against `main`:

1. Fetch `https://raw.githubusercontent.com/JigCar/jigcar-dashboard/main/index-18.html`.
2. Confirm the **embedded last-refreshed timestamp matches this run**. File size is not proof, and
   neither is the commit response, because a commit can succeed on a branch Pages never serves.
3. The raw CDN lags: expect to poll for up to two minutes, and confirm against the Contents API if
   in doubt. Only when the timestamp matches has the dashboard published. If it never matches,
   report it and do not post to Slack.

Configuration:

- `GH_REPO` = `JigCar/jigcar-dashboard` (public, Pages on `main`, root)
- `GH_FILE` = `index-18.html` (repo root; overwrite this exact filename so the URL never changes)
- `GH_TOKEN` = *(keep the value already in the scheduled task; it is deliberately not written into
  this file, because the repo is public)*
- `DASHBOARD_URL` = `https://jigcar.github.io/jigcar-dashboard/index-18.html`
- `STATE_FILE` = `dashboard_state.json` (repo root)

If the repo is mounted, prefer plain `git` and ignore `GH_TOKEN` entirely, which removes the
token-expiry failure mode. The Contents API is refused by this environment's proxy, so it is a
fallback only. On a 403, name the cause before reporting: session repo gate, org approval, or an
expired token. Never print `GH_TOKEN` anywhere.

## Architecture and run order

`pull_attio.py` → `pull_linkedin.py` → `parse_granola.py` → `parse_leave.py` → `classify_emails.py`
→ `etl.py` → `render.py` → `qa.py` → `qa_browser.mjs` → `slack_messages.py`. All read `JIGCAR_SP`
for the working directory.

The `pull_*` and `parse_*` steps write only to `raw/`, so a transform never calls an API and a rerun
is reproducible from the same checkout. `etl.py` holds no metric values of its own: every figure it
writes comes from `raw/` or from the previous state. If you find a tally hardcoded in `etl.py`, that
is a bug to fix, not data to trust — it was true on the day it was written and silently wrong after.

1. **Pull** every connector. Record per-connector and per-seat success or failure.
2. **Load** the previous state from `dashboard_state.json`.
3. **Compute** metrics deterministically, including the stage diff attributed by deal owner.
4. **Update** state: today's snapshot, new won-date stamps, today's metric row.
5. **Render**, then run **QA**. Do not commit if QA fails.
6. **Draft** the narrative from the computed numbers only.
7. **Deliver**: commit the HTML and the state to `main`, verify, then post the two Slack messages.

## Reference identifiers

Team (scorecard order): Chris, Luke, James, Bianca, Elliott, Rupert.

Attio workspace members:
- Chris White `814dcafb-8d1e-4766-86fd-f8aa6d8ec9e7`
- Luke Nogueira `10483700-4091-479f-9d93-5f211daaf782`
- James Griffin `b4d18eef-0a60-4053-8f02-372285421b69`
- Bianca Monteiro `4eb5d016-4e43-4999-b82d-d1472875acac`
- Elliott Perks `67d33719-6e02-4e34-914b-1f47ab8f8226`
- Rupert Wood `64faca79-2742-4958-ba9f-c3fc5fe2bd40`
- Back-book owners: Jon Pollock `35a5991c-1c83-45da-a10d-16576845abb4`, Bob O'Reilly
  `0cd10c6b-3e9b-4850-926c-6ef2a3403c2b`, Pierre de Villeplée `5c0f0e89-1d4a-4c4c-9df6-8c9e41d72cc0`.
  Include any owner in the revenue panels; the six above are the scorecard set.

Attio objects: deals slug `deals`; companies `4a58e655-0c97-44f5-b57b-5ed4e14e3772`; people
`773375e6-3af9-4569-a682-1beb98158137`. Groovin app author on LinkedIn notes
`c020395f-1e1e-4a88-9d95-3c63937a06f8`.

**Attio REST is available and much cheaper than the MCP tools** for deals, companies, people, tasks
and notes: `POST /v2/objects/<slug>/records/query` (limit 500), `GET /v2/tasks`, `GET /v2/notes`
(limit 50, paginate). Credentials are injected by the proxy. There is **no** public emails endpoint;
`/v2/emails` 404s, so email must go through the MCP search.

**Two deal attributes look like the estimated close date and only one is one.** `est_closed_date` is
a real date attribute. `est_close_date` is free text and holds values like `July`. Read the text one
as a date and the build crashes; worse, inferring a day from `July` would promote an estimate to a
fact, which this routine must never do. Prefer `est_closed_date`, accept a value only if it is a
valid ISO date, and render anything else as `est TBC`.

Deal stages: New Lead, Buy Signal, Qualification, Demo, Proposal, Trial, Contracts, Closed Won
(progression, in order) and Nurture, Closed Lost, Churn, `Contacted - no outcome` (shut-off states).

**`Contacted - no outcome` is the renamed `Non-ICP`, not a stage added beside it.** Confirmed on
29 Jul 2026: `Non-ICP` is absent from the status options altogether rather than archived, the new
title appeared in its place, and the same eight record ids sit in it having never moved. A renamed
stage is not a move, so both `pull_attio.py` and `etl.py` normalise through a `STAGE_ALIAS` map,
the pull for today's data and the ETL for the committed baseline. Drop either side and the diff
compares the old label against the new one and books a shut-off against every owner holding a deal
in it, on a day nobody touched them. The account owner described the stage as "Contacted - no
response"; the real title in Attio is "Contacted - no outcome", and the real title is what the code
must match. Read the live status options before trusting any stage name in a prompt, including
this one.

Allo: confirm the seat list each run with `allo_list_users`; use `allo_get_team_analytics` with all
user IDs in one call. Rupert has no Allo account (render `n/a`, calls `0`).

Zelt absence calendar: `c_394bfca8162a353b330bd82c20841ba18f041a86f8fafe24e610890a86f25331@group.calendar.google.com`.
The separate "Jigcar holidays" calendar holds no events after mid-2025. **Do not read it.**

`QUARTER_TARGET = 400000` for Q3 2026. One editable constant, rolled each quarter.

## Time periods

Filter: Today / Yesterday / This week / Last week / This month / This quarter.

**"This week" is the calendar week, Monday to Sunday**, capped at the run date because there is no
data for days that have not happened. On a Monday it is a single day, and the label must say
"week to date" with the day count so a short week is not mistaken for a quiet one. It must span
months and years correctly.

**"Last week" is the previous calendar week, Monday to Sunday**, added at the account owner's
request on 29 Jul 2026. It is wholly in the past, so it is always seven days and is never capped.
Derive it by stepping back from this week's Monday, not by subtracting seven days from the run date,
or it stops landing on week boundaries. It must span months and years correctly.

Because it reaches further back than this week does, it is the view most likely to sit partly before
a connector was switched on, so **it must state which metrics only partly cover it**. That includes
the email deal split, which is narrower than the email tally: an unclassified day renders as `(0)` in
the Emails column and would otherwise read as "nothing was deal-related" when it means "never
classified". Build the caveat from the coverage dates so each entry disappears by itself once
coverage predates the range, rather than hardcoding a list that goes stale.

**The Slack performance threshold does not use that filter.** It runs on a separate trailing
seven-day range, kept out of the UI toggle. Reusing the calendar week would flag nearly every
outbound seat every Monday for having done nothing by 09:00.

## Metric definitions (per person, per period)

- **Sales meetings** — external, deal-advancing meetings from Granola. A scheduled conversation with
  at least one participant outside Jigcar, at a prospect or customer, to move an opportunity or
  account forward: discovery, intro, demo, commercials, tender, negotiation, rollout, go-live, or a
  recurring account or site review. Credit every Jigcar attendee. **Exclude:** internal-only
  meetings (all attendees on jigcar.com), dailies, weeklies, all-hands, one-to-ones, prep and deck
  reviews; advisers and the chairman; investors; media and press; suppliers and 3PL carriers;
  tooling and vendor demos; partner or channel exploration not attached to a deal; recruitment and
  personal appointments. Dedupe on (date, title), since one meeting writes a note per creator. Keep
  the exclusion list keyed by (date, title) in state so each call is auditable.
- **Calls** — Allo calls for that seat.
- **Emails (deal)** — sent emails from Attio across all connected mailboxes where the sender is a
  team Jigcar address, de-duped by (sender, subject, sent_at). Apollo sends route through the same
  mailboxes, so do not count Apollo separately. Shown as `total (live deal)` with a customer figure
  on its own line. See the email split below.
- **LI requests sent (deal)** — LinkedIn connection requests sent.
- **LI connections made (deal)** — invitations accepted.
- **LI messages (deal)** — LinkedIn messages sent. See the LinkedIn section.
- **Tasks done** — Attio tasks completed by that assignee, dated by **`completed_at`**, which the
  tasks endpoint does expose. Do not date them by creation.
- **Deals assigned** — deals owned by that person, created in the period.
- **Progressed / Shut off** — from the stage diff, attributed by deal owner, not by who made the
  change.
- **Contract out (£)** — ARR of that person's deals currently in Contracts. A live snapshot: label
  it live and do not let the time filter change it.
- **Closed won (£)** — ARR entering Closed Won in the period, from the stage diff and the won-date
  stamp. Quarter-level.

Summary table columns, in order: Person, Sales mtgs, Calls, Emails (deal), LI sent, LI conn, LI
msgs, Tasks, Deals, Progressed, Shut off, Contract out (£), Closed won (£), plus a team totals row.
**Header, body and totals must have the same column count**; a mismatch misaligns the table
silently.

## Deal-association: one definition everywhere

`(deal)` on any metric means **the counterparty's company has an open deal**, New Lead through
Contracts. Closed Won is a customer, not pipeline, and is counted separately where shown. Emails,
LI requests, LI connections and LI messages all use this same test so the columns are comparable.

The join is recipient or contact → company → that company's strongest deal state. It depends on
Attio's deal↔company links being present. **Report join coverage on the page** (open deals joinable,
and the share by pipeline value). If coverage drops, say so rather than letting unjoinable deals
read as "no deal".

Where a deal has no company, or a company has no domain, the join silently under-reports. Surface
those records for repair rather than inferring. Never invent a domain.

## Leave and attendance

Activity is only meaningful against days a person was actually at work. Read the Zelt calendar each
run.

Zelt mixes two date conventions in one feed, and assuming either universally gets the other wrong:

- single day: `start == end`, which would be zero-length under Google's exclusive-end rule
- multi-day: the end is exclusive, so a one-day bank holiday is stored `31 Aug -> 1 Sep`

Rule: `end <= start` means one day; otherwise expand end-exclusive. Half days are marked in the
summary text as `(AM)` or `(PM)` and still count as a day attended.

**Working days attended** = weekdays in the range minus full-day leave. Use it wherever activity is
judged. Show who is off today on the connectivity panel, including non-scorecard colleagues, and tag
the scorecard card of anyone on leave, so a quiet row can be read against the reason for it.

## The hard problems

### 1. Progressed, shut off, real won-date (stage diff)

Attio exposes no stage history and `days_since_stage_entry` reads empty. So:

- Each run, snapshot every deal `{record_id, stage, owner, value}`, keyed on the **8-character
  record-id prefix**, which is what the committed state uses. Changing the key breaks continuity.
- Diff against the previous snapshot. Forward on the ladder → **progressed**. Into a shut-off state
  → **shut off**. Into Closed Won → stamp **won date = today**.
- Attribute to the current owner, dated the run date.
- Observed moves accumulate: a second run on the same day sees no new diff because it already
  applied the change to its own baseline, so rebuild today's row from the union of everything
  observed, deduped on (record, from, to, date).
- Never backfill moves from before the routine existed.

### 2. Email tally and the deal split

Paginate the Attio MCP email search over the period, keep sends whose sender is a team address,
de-dupe across mailbox copies, tally per person per day.

Then classify each send by recipient: **live deal**, **customer** (Closed Won), **closed**,
**none** (external, no deal) or **internal**. Where an email has several external recipients the
strongest state wins, so a note to a live prospect that copies a vendor still reads as live deal.

The split is only valid for days whose recipient lists were actually pulled. **Record that window
and label it**, because a total outside it shows 0 deal-associated, which means unclassified, not
unrelated.

Oversized MCP results are written to a file and the path returned. Prefer that: request large pages
so they overflow to disk and parse them, rather than reading hundreds of emails into context.

Note **Rupert's own mailbox is not connected**. His sends are visible only where a teammate was a
recipient, so his email figure is a floor and his Email seat reads `partial`.

### 3. LinkedIn attribution (Groovin → Attio notes)

Groovin writes LinkedIn activity into Attio as notes authored by the app, in person/company pairs.
**Count the event once**, deduped on (date, rep, contact, kind); the company side supplies the deal
join.

**The rep is in the note body, not the title, for invitations.** This is the single most important
detail in this section, and reading only the title has caused a real mis-attribution:

- sent: body reads `from <Rep> to <Contact>`, title is the bare string `LinkedIn invitation sent`
- accepted: body reads `<Rep> is now connected with <Contact>.`
- messages: the rep is in the **title**, `1:1 LinkedIn chat | <Contact> with <Rep>`

So requests sent, connections made and messages are **all** attributable per person from Attio
alone. Fetch note bodies (`GET /v2/notes/<id>`) and parse them.

**Never fall back to counting cadence Touch-1 tasks.** That proxy credits whoever was assigned the
task rather than whoever sent the invitation, and it was wrong by a wide margin: it showed one
person on 12 connects against 3 actually sent, and another on 5 against 32.

**Connections made lag** the invitation that earned them, often by weeks. A high accepted count
reflects earlier outreach, not work done in the period. Say so on the page, or it flatters one
person and penalises whoever is sending today.

### 4. Connectivity reporting

Per workspace connector (Attio, Granola, Apollo) and per seat (Allo, Email, Groovin): `ok`,
`partial`, `unknown`, `down`, `na`. Set from the run's actual results.

**The shape is a contract with the template, and getting it wrong blanks most of the page rather
than just this panel:**

- `workspace` is an **array** of `{name, status, note}`. The template calls `.map()` on it.
- `seats` is keyed by **person**, each value a three-item list in the order
  `[Allo, Email, Groovin]`.

The scorecard reads `connectivity.seats[<person>][0]` for the Calls cell, so a dict where a list
belongs, or seats keyed by connector instead of by person, takes out the metric cards and the
summary table as well as the connector panel. `etl.py` validates both and must exit non-zero on a
mismatch. This has happened, it published a blank dashboard, and no static check caught it.

## Revenue, bonus and archive

**Revenue banner:** target, closed won (£ and % of target), out for contract, remaining if contracts
land (floored at 0), stacked bar. Closed won and out-for-contract panels with totals, deal lists and
by-owner charts, all owners, quarter-level, unaffected by the time filter.

**Acquisition channel chart:** all Closed Won deals by `acquisition`, the whole won book, labelled as
such. Normalise spelling only (`Inboud - linkedin` → `Inbound - LinkedIn`). Never map an
unrecognised or blank value onto a real channel; unset is `Unassigned`.

**Direct outbound bonus (payout-critical).** Paid on closed won deals whose channel is exactly
`Outbound - Direct`. Show per quarter: every closed won deal with name, ARR, owner, close date,
channel and whether it qualifies; a per-person table with qualifying count, ARR, deal names and
anything pending a channel; the value band and amount per deal; and a bonus-earned leaderboard.

Bands (effective July 2026, deal value = ACV on the signed agreement, boundaries take the higher
band, so these are inclusive lower bounds):

| Deal value | Bonus |
| --- | --- |
| £100,000 and above | £1,000 |
| £75,000 to £100,000 | £750 |
| £50,000 to £75,000 | £500 |
| £25,000 to £50,000 | £250 |
| £15,000 to £25,000 | £200 |
| £10,000 to £15,000 | £150 |
| £5,000 to £10,000 | £100 |
| Up to £5,000 | £50 |

State two limits on the view every run:

1. The policy pays when the **first invoice is sent within the quarter**. Invoicing data is not
   available, so deals are placed by close date as a proxy. A deal closed late and invoiced next
   quarter belongs in the next payment.
2. The policy test is whether the person made the first move, which is broader than the Attio
   field. An intro they engineered qualifies; one that arrived unprompted does not. Where field and
   policy disagree, the policy decides, so this is a basis for payment, not the final word.

A deal with no channel is `Unassigned` and **excluded from the qualifying total**, with a prominent
do-not-pay-yet warning naming the deals, ARR and owner. Attribute by deal owner at close. Carry all
of this through the archive quarters.

**Closed won leaderboard** (restructured at the account owner's request, 29 Jul 2026). Four
independent ranked boards, not one mixed table: ARR closed won and deals closed won for the live
quarter, then the same pair for the year to date as their own separate boards. The quarter boards
never show the year figure alongside. Each board ranks on its own measure, drawn as the same plain
HTML bars as the activity leaderboard so a blocked chart CDN costs nothing. Any owner who closed a
deal is ranked, including back-book owners, alongside the six.

**Quarterly activity leaderboard** (added at the account owner's request, 29 Jul 2026;
deal-scoped and extended the same day). Lives in the Leaderboard & bonus tab, under the closed-won
boards. Ranks the six scorecard people on one switchable measure at a time: total activity, sales
meetings, calls, **deal-associated** emails, **deal-associated** LinkedIn requests / connections /
messages, completed tasks, deals assigned, and deals progressed. The email and LinkedIn measures use
the deal split, the same open-deal join as the scorecard's `(deal)` columns, not the raw tallies.
Calls stay unfiltered because Allo carries no per-call deal join, and the note says so. Total
activity is one point per deal-facing action: meetings + calls + deal emails + deal LI requests +
deal LI messages + tasks, with connections accepted excluded because they lag the request that
earned them. Two coverage truths the notes must carry: the email deal split starts later than the
raw email tally (`email_split_from`), so the deal-email view is a floor twice over for Rupert; and
deals progressed is measured by the stage diff, which has only existed since 27 Jul 2026, so it is
a floor, not a quarter total. Rules that must hold:

- It reads the same daily store and quarter range as the scorecard, so its numbers always reconcile
  with the summary table's quarter view, and it rolls to Q4 with no edit.
- **Q3 2026 onward only.** The feeding tools did not exist before July 2026, so there is nothing
  honest to rank for Q1 or Q2, and the panel must never appear on the reconstructed archives.
- Drawn as plain HTML bars, deliberately not Chart.js, so the ranking survives a blocked CDN
  exactly like the tables do.
- Every per-metric caveat is built from the coverage fields, never hardcoded: email and call floors,
  Rupert's n/a Allo seat and floor mailbox, the acceptance lag. Each caveat disappears by itself
  once coverage predates the quarter.
- Each row shows working days attended, so a quiet row reads against booked leave.
- Activity is volume, not outcome, and the panel says so; the closed-won table above it stays the
  scoreboard. This leaderboard feeds no Slack line and no performance flag.
- When Q3 freezes, the archive's full activity snapshot carries the per-person quarter totals so the
  archived quarter can still show its leaderboard.

**Archive dual-mode.** Q3 2026 onward archive as the full activity snapshot. Pre-tooling quarters
(Q1, Q2 2026) use the reconstructed shape: closed won by close date, plus deals-created and
current-outcome as context, with the note that calls, emails, tasks and LinkedIn did not exist then.
Do not render pre-tooling quarters as if they had activity data.

**Back-book won dates** (confirmed manually, seed into `won_dates`): Focus VM £24,840 (Rupert) Q1;
RH Car Transport £8,400 (Luke) Q2; Monmotors £43,200 (Elliott) Q2; Premier Travel Logistics £17,820
(Luke) Q2; Peter Cooper Group £14,400 (Chris) Q3; Hilton Coachworks Group £12,000 (Chris) Q3. The
rest of the won book closed before 2026.

## Persistent state

`dashboard_state.json` at the repo root on `main`, committed each run. Holds at minimum:

- `stage_snapshot` — `{short_record_id: {stage, owner, value}}`
- `won_dates`, `won_dates_quarter_only`, `pre_2026_won`
- `daily_metrics` — one row per person per day for every scorecard metric
- `stage_moves` — the accumulated observed moves
- `connectivity`, `archive`, `meeting_classification`, `coverage`
- `leave`, `off_today`, `attendance`
- `perf_flags` — `{date: person}`, written by the Slack step so it can escalate on the third
  consecutive day. **The ETL must carry this forward**; rebuilding state without it silently resets
  the streak and a worsening pattern reads as a first flag every morning.

If the state cannot be read, restore the last good version from git history rather than wiping it,
and flag it in the Slack message. The repo is public, so this file is publicly readable: that was an
explicit decision by the account owner.

## Slack notification

Two channels, two audiences, two different messages. Never send the same text to both. Write for a
phone screen: one line per point, each led by its emoji, no preamble, no headers, no bullet lists,
no routine mechanics (baselines, diffs, seeding, state files).

**Spacing.** Separate every emoji-led point with a **blank line** (`\n\n`), including before the
link. Slack renders single newlines tightly and the message reads as a wall of text.

### `#operation-foot-down` — leadership, every morning

Posts every scheduled run provided a build reached `main`, even when nothing changed. Four lines
maximum plus the link:

1. 🎯 **Revenue.** Closed won this quarter, % of target, out for contract, gap if contracts land.
2. 🔄 **What moved since yesterday.** Real changes only, with name and value. If nothing moved, say
   so in four words.
3. ⚠️ **Deal risk.** The single highest-value concern. One item, the biggest.
4. 🚩 **Performance risk.** One person, named, with the specific gap.
5. 🔗 The link on its own line.

Rules for line 4, which otherwise degrades into noise:

- **One person only**, the most severe. If two are struggling, the second waits for tomorrow.
- **Role-aware.** Only seats carrying outbound: currently Chris, Luke, Elliott. James is Transport
  Director and Bianca runs onboarding, so low outbound activity is expected and is never flagged.
- **A real threshold, not a ranking.** Zero on at least two of the three core metrics (sales
  meetings, sent emails, completed tasks) across the trailing seven days. Never "below team
  average", which always flags someone.
- **Never flag anyone who is on leave that day, and never judge a window with fewer than four
  working days attended.** Someone on booked holiday has not underperformed. Where a flag does fire
  on a short week, say "across four working days" rather than implying a full one.
- **Escalate, do not repeat.** On the third consecutive day for the same person, say it is the third
  day running.
- **Omit lines 3 and 4 entirely when nothing qualifies.** Never pad them.

```
🎯 £26,400 won, 6.6% of £400k. £195,600 out for contract, £178,000 short if all three land.

🔄 Nelson (Bianca) into Qualification. Six new buy-signal deals. Nothing won or lost.

⚠️ Citygate £75,600 and West Herr £72,000 both seven days past est close.

🚩 Luke: no sent email or completed task in the last seven days, one sales meeting. Four all quarter.

🔗 https://jigcar.github.io/jigcar-dashboard/index-18.html
```

### `#deal-updates` — whole team, every morning

Two lines plus the link normally, three when something is worth celebrating.

1. 🎯 **Quarter position.** Closed won, % of target, out for contract.
2. 🔄 **What moved, without naming anyone.** Counts only. If nothing moved, say so in four words.
3. 🔗 The link on its own line.

**Naming a person is the exception.** Add a named line at the top only when one of three triggers
fires:

1. 🏆 **A deal closed won** since the last post. Name the person, deal and value.
2. 📄 **A deal moved into Contracts** since the last post.
3. 🔥 **A genuine activity spike**: at least double that person's trailing four-week daily average on
   the metric, above a floor of three. Until the store holds four weeks, fire only on a same-day team
   record — and **only on a metric with at least five days of history**, or thin coverage names
   someone for an artefact rather than an achievement.
   **History depth is judged per metric, never pooled across them.** Pooling the dates made sixteen
   days of meetings plus twenty of tasks look like four weeks of both, fired the average branch, and
   printed "a team record for a single day" about a figure that was not a record. A record must be
   **strictly greater** than every other day, and the wording must state whichever basis actually
   fired. Equalling the previous best is not a record, and naming someone for it is a false claim
   about a real person.

**Never** put performance concern, deal risk, aged contracts or anyone's shortfall in this channel,
and never name a person in a neutral or negative context here. Named credit goes to the team; named
concern goes to leadership only.

### Posting mechanics

The Slack connector cannot edit or delete, so posting is once per day. Both target channels are
**private**, so the default channel search will not find them: search with
`channel_types: "public_channel,private_channel"`.

- **The leadership post always goes**, provided a build published to `main`. A quiet day is
  information; silence reads as the routine being broken.
- **A re-run later the same day does not post.** Read the channel first; if today's message is
  there, do not post again.
- Exception: if figures materially changed (a deal won, lost, or moved into or out of Contracts),
  post a short follow-up. A zero-value move between early stages does not clear that bar.
- **If nothing published**, including a commit that landed anywhere other than `main`, post to
  neither channel and report to the operator.
- On a partial run where a build did publish, replace line 3 of the leadership message with the
  failure and the connector that is down.
- If the Slack connection is not a member of either channel, flag it to the operator.

Never paste tables or the dashboard's contents into Slack. Never create a canvas. Never print the
token.

## Output QA before publishing

Run `qa.py` every time and do not commit if it fails:

1. **Every element ID resolves.** Every `getElementById` target, including prefix-built ones, has a
   matching `id="..."`. One mismatch throws on first render and blanks the whole page.
2. **Renders are isolated.** Each top-level render call sits in its own try/catch.
3. **The run stamp is embedded** in the built file.
4. **Syntax-check the built JavaScript** (`node --check`). A parse error blanks the page and static
   inspection does not catch it.
5. **The summary table's header, body and totals rows have equal column counts.**

**Then run `qa_browser.mjs`, and do not commit if it fails. This is the check that matters.**
Checks 1 to 5 are necessary and nowhere near sufficient: a build once passed all of them while the
published page was completely blank. Static QA cannot see a script that dies before its render
functions are defined, and it cannot see a malformed data shape at all.

Load the built file in headless Chromium and assert the **data** is on the page, not merely that the
markup parsed:

- the scorecard has one row per person plus the team totals row, and the first row is not empty
- the run stamp, the coverage panel, the stage-move note and the connector panel are all populated
- no uncaught page error, and no render reported a failure into the console

Run it **twice: once with the chart CDN blocked and once with it served.** The blocked pass is the
real test, because that is the failure that reached the team: a print taken where the CDN is
unreachable. Every number must survive it. Simulate the served pass with a stub rather than relying
on the network, or the check silently never runs.

The browser check needs the `playwright` package and the pre-installed Chromium. If it cannot run,
**say so and do not publish on the strength of the static checks alone** — they have already been
proven to pass on a blank page. Never treat "the CDN was unreachable from the sandbox" as a build
failure; treat it as the condition to test against.

Also:

- A chart drawn inside a hidden tab renders at zero height, so re-render a tab's charts when it
  becomes visible.

## Brand and writing

Dark `#0a0a0a`, cards `#1A1A1A`, green `#088E4D`, bright `#6AD98E`, amber `#E0A93B`, red `#E05B5B`,
blue `#4B9FE0`. Inter stack. British English. Short sentences. No em dashes. Section titles and the
daily read state a conclusion, not a topic label. Keep hard numbers separate from soft commentary.

## Guardrails

- If a connector fails, render `down`, keep the last good value with a stale marker, note it in
  coverage. Never silently substitute.
- Never promote an estimate to a fact. The only real close dates are stamped by the stage diff or
  the confirmed back-book list.
- The written read must reconcile with the tables.
- **No unguarded reference to an external library at the top of the script.** Chart.js is fetched
  from a CDN, and a bare `Chart.defaults` assignment at script top-level threw a ReferenceError
  before a single render function was defined, so the entire dashboard published blank. Guard it,
  stub `new Chart()` and `.destroy()` when the library is absent, and show a visible notice that the
  graphs are blank while the tables are correct. **A missing chart library may cost the charts, never
  the numbers**, and a blank graph must never be readable as zero data.
- The page is a static build. It carries a **data-as-at stamp**, not a refresh control. Do not add a
  button that appears to fetch live data: it cannot, because the page has no credentials and the
  repo is public. If you add any control that re-fetches, it must compare the published build stamp
  against the current one and say which happened, never restamp without fetching.

## Definition of done

- `index-18.html` renders from `render.py` with live data, and QA plus the JS syntax check pass.
- **The browser check passes with the chart CDN blocked**, proving the scorecard, the connector panel
  and every figure are actually on the published page. A build that only passes static QA is not
  done: that combination has shipped a blank dashboard.
- Every scorecard number traces to a pull or the state store.
- Progressed, shut off and closed won come from the stage diff, attributed by owner.
- Emails are the de-duped multi-mailbox count with a labelled live-deal / customer split.
- LinkedIn requests sent, connections made and messages are each attributed per person **from the
  note body or title**, deduped across the person and company copies, each with the deal split.
- Leave is read from Zelt, attendance drives any activity judgement, and nobody on leave is flagged.
- Connectivity reflects the actual run.
- Every closed won deal shows its acquisition channel, and the bonus basis reconciles: only
  `Outbound - Direct` counts, unassigned listed separately and flagged.
- Committed to `main` and verified by reading the file back from `raw.githubusercontent.com` and
  matching the embedded timestamp. No branch, no pull request.
- `dashboard_state.json` committed on `main`, with `perf_flags` carried forward.
- No Slack Canvas. Each emoji-led point separated by a blank line. The two messages are never
  identical, and nobody is named in `#deal-updates` without a celebration trigger.

## Ops

- Weekday **08:00 local**, set on the task itself.
- On failure, wipe nothing. Leave the previous dashboard and state intact.
- If a connector is down but a build published, post with a down status. If nothing published, post
  to neither channel and report to the operator.
- If there is no writable destination, do not run the ETL.
- Keep the run idempotent: re-running the same day overwrites that day's metric row.
- Dependencies: Attio, Allo, Granola, Groovin, Apollo, Google Calendar (Zelt), the Slack connection
  being a member of both private channels, and egress to `api.github.com`.
- The browser check also needs the `playwright` package and the pre-installed Chromium at
  `/opt/pw-browsers/chromium`. Never run `playwright install`; `PLAYWRIGHT_BROWSERS_PATH` already
  points at it. `playwright` resolves from the directory it is installed in, so run the check from
  there rather than relying on `NODE_PATH`.

## Known gaps, carried forward

State these on the page rather than letting them read as zero:

- Email coverage begins partway through the period and accumulates a day per run. The deal split
  covers a narrower window still.
- Rupert's mailbox is not connected; his email figure is a floor.
- Rupert has no Allo seat; calls are always 0.
- Calls and completed cadence tasks only begin around 21-22 July 2026.
- Connections made lag the invitations that earned them.
- A handful of £0 open deals still have no company or no domain and cannot be joined. Every open
  deal carrying value is joinable.
