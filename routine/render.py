# -*- coding: utf-8 -*-
import json, io, os, datetime as _dt
SP=os.environ.get("JIGCAR_SP") or os.path.dirname(os.path.abspath(__file__))
p=json.load(open(f"{SP}/build/payload.json"))
J=lambda o: json.dumps(o,ensure_ascii=False)

HEAD = r'''<!DOCTYPE html>
<html lang="en-GB">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Jigcar Team Momentum</title>
<script src="https://cdnjs.cloudflare.com/ajax/libs/Chart.js/4.4.1/chart.umd.min.js"></script>
<style>
  :root{
    --bg:#0a0a0a; --card:#1A1A1A; --card2:#151515; --line:#2e2e2e;
    --green:#088E4D; --bright:#6AD98E; --amber:#E0A93B; --red:#E05B5B; --blue:#4B9FE0; --purple:#A06AD9;
    --text:#EDEDED; --muted:#9a9a9a;
    --font:'Inter',-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,Helvetica,Arial,sans-serif;
  }
  *{box-sizing:border-box}
  body{margin:0;background:var(--bg);color:var(--text);font-family:var(--font);line-height:1.5;font-size:15px}
  .wrap{max-width:1100px;margin:0 auto;padding:34px 26px 80px}
  .logo{display:flex;align-items:center;gap:10px;margin-bottom:14px}
  .logo .dot{width:28px;height:28px;border-radius:6px;background:var(--green);display:flex;align-items:center;justify-content:center;font-size:15px;font-weight:800;color:#0a0a0a}
  .logo span{font-weight:700;letter-spacing:.3px}
  h1{font-size:27px;margin:0 0 4px;font-weight:700;letter-spacing:-.4px}
  .sub{color:var(--muted);font-size:13.5px;margin-bottom:20px}
  .topbar{display:flex;flex-wrap:wrap;gap:14px;align-items:center;justify-content:space-between;margin:0 0 12px;padding:12px 16px;background:var(--card);border:1px solid var(--line);border-radius:12px}
  .qsel{display:flex;align-items:center;gap:8px;font-size:13px;color:var(--muted)}
  select{background:var(--card2);color:var(--text);border:1px solid var(--line);border-radius:8px;padding:7px 10px;font-family:var(--font);font-size:13.5px}
  .refresh{display:flex;align-items:center;gap:10px}
  .refresh .ts{color:var(--muted);font-size:11.5px}
  .stamp{display:inline-flex;align-items:center;gap:9px;background:rgba(8,142,77,.14);
    border:1px solid #1f5c3a;border-radius:999px;padding:8px 15px}
  .stamp .dotlive{width:8px;height:8px;border-radius:50%;background:var(--bright);flex:none}
  .stamp .lbl{font-size:10.5px;text-transform:uppercase;letter-spacing:.6px;color:var(--muted);font-weight:700}
  .stamp .val{font-size:13px;font-weight:700;color:var(--bright);letter-spacing:-.1px}
  .stamp .cad{font-size:11px;color:var(--muted)}
  @media(max-width:560px){.stamp{flex-wrap:wrap;gap:5px}.stamp .cad{width:100%}}
  .conn{background:var(--card2);border:1px solid var(--line);border-radius:12px;padding:14px 16px;margin:0 0 20px}
  .conn .ttl{font-size:11px;text-transform:uppercase;letter-spacing:.6px;color:var(--muted);font-weight:700;margin-bottom:10px}
  .conn .ws{display:flex;flex-wrap:wrap;gap:18px;margin-bottom:12px;padding-bottom:12px;border-bottom:1px solid var(--line)}
  .chip{display:flex;align-items:center;gap:7px;font-size:13px}
  .chip b{font-weight:600} .chip small{color:var(--muted);font-size:11px}
  .cdot{width:9px;height:9px;border-radius:50%;flex:none}
  .ok{background:var(--bright)} .partial{background:var(--amber)} .unknown{background:#6a6a6a} .down{background:var(--red)} .na{background:#333;border:1px solid #444}
  .cmatrix{width:100%;border-collapse:collapse;font-size:12.5px}
  .cmatrix th,.cmatrix td{text-align:center;padding:5px 8px;border:none}
  .cmatrix th:first-child,.cmatrix td:first-child{text-align:left;color:var(--muted)}
  .cmatrix thead th{color:var(--muted);font-weight:600;font-size:11px;text-transform:uppercase;letter-spacing:.4px}
  .cmatrix td .cdot{display:inline-block;vertical-align:middle}
  .offrow{display:flex;flex-wrap:wrap;align-items:center;gap:8px;margin-top:12px;padding-top:11px;border-top:1px solid var(--line);font-size:12.5px}
  .offrow .k{font-size:10.5px;text-transform:uppercase;letter-spacing:.6px;color:var(--muted);font-weight:700}
  .offpill{display:inline-flex;align-items:center;gap:6px;background:rgba(224,169,59,.13);border:1px solid #5c4a1f;
    color:var(--amber);border-radius:999px;padding:3px 10px;font-size:12px;font-weight:600}
  .offpill small{color:var(--muted);font-weight:600}
  .card .leavetag{display:inline-block;background:rgba(224,169,59,.15);color:var(--amber);font-size:10.5px;
    font-weight:700;padding:2px 8px;border-radius:20px;margin-left:6px;vertical-align:middle}
  .legend{display:flex;gap:14px;flex-wrap:wrap;margin-top:10px;font-size:11px;color:var(--muted)}
  .legend span{display:flex;align-items:center;gap:5px}
  .target{background:linear-gradient(135deg,#123b26 0%,#0d1f16 60%,#141414 100%);border:1px solid #1f5c3a;border-radius:16px;padding:22px 24px;margin:0 0 16px}
  .target .thead{display:flex;justify-content:space-between;align-items:baseline;flex-wrap:wrap;gap:8px;margin-bottom:16px}
  .target .tlabel{font-size:12px;color:var(--bright);font-weight:700;letter-spacing:.6px;text-transform:uppercase}
  .target .tbig{font-size:34px;font-weight:800;letter-spacing:-1px;line-height:1.05}
  .target .tbig small{font-size:14px;font-weight:600;color:var(--muted);letter-spacing:0}
  .tbar{height:26px;border-radius:8px;background:#0c0c0c;border:1px solid #262626;overflow:hidden;display:flex}
  .tbar .won{background:var(--green);height:100%}
  .tbar .oc{background:repeating-linear-gradient(45deg,#0e6b3a,#0e6b3a 7px,#0a5730 7px,#0a5730 14px);height:100%}
  .tlegend{display:flex;gap:22px;flex-wrap:wrap;margin-top:14px;font-size:13px;color:#cfcfcf}
  .tlegend .k{display:flex;align-items:center;gap:7px}
  .tlegend .sw{width:12px;height:12px;border-radius:3px;flex:none}
  .tlegend b{font-weight:700;color:var(--text)}
  .revpanel{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:18px}
  .revpanel .rlab{font-size:12px;text-transform:uppercase;letter-spacing:.5px;color:var(--muted);font-weight:600}
  .revpanel .rbig{font-size:30px;font-weight:800;letter-spacing:-.5px;margin:2px 0}
  .revpanel .rsub{font-size:12.5px;color:var(--muted);margin-bottom:12px}
  .tabs{display:flex;gap:6px;background:var(--card2);border:1px solid var(--line);border-radius:12px;padding:5px;margin:0 0 6px}
  .tabs button{flex:1;background:transparent;border:none;color:var(--muted);padding:11px 14px;border-radius:9px;cursor:pointer;font-family:var(--font);font-size:13.5px;font-weight:700;transition:.15s}
  .tabs button:hover{color:var(--text)}
  .tabs button.on{background:var(--green);color:#fff}
  .ctxtitle{font-size:12.5px;color:var(--muted);margin:0 0 18px;padding-left:2px}
  .ctxtitle b{color:var(--bright);font-weight:700}
  .filterbar{display:flex;flex-wrap:wrap;gap:12px;align-items:center;margin:26px 0 4px;padding:12px 14px;background:var(--card2);border:1px solid var(--line);border-radius:12px}
  .toggle{display:flex;gap:4px;background:#0e0e0e;border:1px solid var(--line);border-radius:10px;padding:4px}
  .toggle button{background:transparent;border:none;color:var(--muted);padding:7px 13px;border-radius:7px;cursor:pointer;font-family:var(--font);font-size:13px;font-weight:600;transition:.15s}
  .toggle button:hover{color:var(--text)}
  .toggle button.on{background:var(--green);color:#fff}
  .range{color:var(--bright);font-size:12.5px;font-weight:600}
  h2{font-size:18px;margin:34px 0 6px;font-weight:700;letter-spacing:-.2px}
  h2 .bar{color:var(--green)}
  .lead{color:var(--muted);font-size:13.5px;margin:0 0 16px}
  .cards{display:grid;grid-template-columns:repeat(2,1fr);gap:14px;margin:16px 0}
  .card{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:16px}
  .card .name{font-weight:700;font-size:15px;margin-bottom:1px}
  .card .role{color:var(--muted);font-size:11.5px;margin-bottom:12px}
  .stat{display:flex;justify-content:space-between;font-size:13px;padding:3px 0;border-bottom:1px dashed #262626}
  .stat:last-child{border-bottom:none}
  .stat .v{font-weight:700}
  .g{color:var(--bright)} .r{color:var(--red)} .a{color:var(--amber)} .m{color:var(--muted)}
  table{width:100%;border-collapse:collapse;margin:8px 0 6px;font-size:13.5px}
  th,td{text-align:center;padding:9px 8px;border-bottom:1px solid var(--line)}
  th:first-child,td:first-child{text-align:left}
  thead th{color:var(--muted);font-weight:600;font-size:12px;text-transform:uppercase;letter-spacing:.5px}
  tbody tr:hover{background:#151515}
  td.total,th.total{font-weight:700;color:var(--bright)}
  .lb td:first-child{width:44px;text-align:center;color:var(--muted);font-weight:700}
  .lb .medal{font-size:15px}
  .chartbox{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:18px 16px;margin:16px 0}
  .chartbox h3{margin:0 0 12px;font-size:13.5px;font-weight:600}
  .note{background:#141414;border-left:3px solid var(--green);border-radius:0 8px 8px 0;padding:12px 16px;margin:14px 0;font-size:13.5px;color:#cfcfcf}
  .warn{border-left-color:var(--amber)} .flag{border-left-color:var(--red)}
  ul{margin:8px 0;padding-left:20px} li{margin:5px 0}
  .pill{display:inline-block;font-size:11px;padding:2px 8px;border-radius:20px;font-weight:600}
  .pill.green{background:rgba(8,142,77,.18);color:var(--bright)}
  .pill.red{background:rgba(224,91,91,.15);color:var(--red)}
  .pill.amber{background:rgba(224,169,59,.15);color:var(--amber)}
  .pill.grey{background:#262626;color:var(--muted)}
  .two{display:grid;grid-template-columns:1fr 1fr;gap:16px}
  .archive{background:var(--card2);border:1px dashed var(--line);border-radius:12px;padding:22px;color:var(--muted);font-size:13.5px}
  .qbadge{display:inline-block;background:rgba(8,142,77,.15);color:var(--bright);font-size:12px;font-weight:700;padding:3px 10px;border-radius:20px}
  .ask{background:var(--card2);border:1px solid var(--line);border-radius:12px;padding:14px 16px;margin:0 0 14px}
  .ask .ttl{font-size:11px;text-transform:uppercase;letter-spacing:.6px;color:var(--muted);font-weight:700;margin-bottom:8px}
  .ask p{margin:0 0 12px;font-size:12.5px;color:var(--muted)}
  .ask .row{display:flex;flex-wrap:wrap;gap:8px;align-items:center}
  .agentbtn{text-decoration:none;display:inline-flex;align-items:center;gap:9px;background:#fff;color:#4C1D95;
    border:2px solid #7C3AED;border-radius:999px;padding:11px 20px;font-family:var(--font);
    font-size:14px;font-weight:700;cursor:pointer;letter-spacing:-.1px;
    box-shadow:0 0 0 4px rgba(124,58,237,.20), 0 0 18px rgba(124,58,237,.35);transition:.18s}
  .agentbtn:hover{box-shadow:0 0 0 5px rgba(124,58,237,.28), 0 0 26px rgba(124,58,237,.5);transform:translateY(-1px)}
  .agentbtn:active{transform:translateY(0)}
  .agentbtn svg{flex:none}
  .askmsg{font-size:12px;color:var(--bright);margin-top:10px;min-height:16px}
  .foot{color:var(--muted);font-size:12px;margin-top:40px;border-top:1px solid var(--line);padding-top:16px}
  #liveMomentum,#liveBoard,#archMomentum,#archBoard{display:none}
  @media(max-width:820px){.cards{grid-template-columns:1fr}.two{grid-template-columns:1fr}}
</style>
</head>
<body>
<div class="wrap">
  <div class="logo"><div class="dot">J</div><span>JIGCAR</span></div>
  <h1>Team Momentum</h1>
  <div class="sub">Chris . Luke . James . Bianca . Elliott . Rupert &nbsp;|&nbsp; Live quarter runs from its start; closed quarters archive automatically.</div>

  <div class="topbar">
    <div class="qsel">
      Quarter:
      <select id="quarter" onchange="onQuarterChange()">
        <option value="Q3-2026" selected>Q3 2026 (live) . 1 Jul - 30 Sep</option>
        <option value="Q2-2026">Q2 2026 (archived)</option>
        <option value="Q1-2026">Q1 2026 (archived)</option>
      </select>
    </div>
    <div class="refresh">
      <span class="stamp">
        <span class="dotlive"></span>
        <span class="lbl">Data as at</span>
        <span class="val" id="lastRefresh"></span>
        <span class="cad">rebuilt each weekday 08:00</span>
      </span>
    </div>
  </div>

  <div class="conn" id="conn"></div>

  <div class="ask">
    <div class="ttl">Query this data with Claude</div>
    <p>No numbers leave this page. The button copies this dashboard's full dataset to your clipboard and opens Claude. Paste it into the chat, then ask whatever you like.</p>
    <div class="row">
      <a class="agentbtn" id="agentLink" href="https://claude.ai/project/019a0656-1927-7642-abca-4885887fcf6a" target="_blank" rel="noopener" onclick="copyPayload()">
        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#4C1D95" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round">
          <path d="M12 2v2.5"/><circle cx="12" cy="2" r="1" fill="#4C1D95" stroke="none"/>
          <rect x="3.5" y="4.5" width="17" height="13" rx="3.5"/>
          <path d="M8 21l2.2-3.5h3.6L16 21"/>
          <circle cx="9" cy="10.5" r="1.35" fill="#4C1D95" stroke="none"/>
          <circle cx="15" cy="10.5" r="1.35" fill="#4C1D95" stroke="none"/>
          <path d="M9.5 14h5"/>
        </svg>
        Copy data &amp; open Claude
      </a>
    </div>
    <div class="askmsg" id="askmsg"></div>
  </div>

  <div id="chartWarn" style="display:none;margin:0 0 16px;padding:11px 15px;background:rgba(224,169,59,.13);
    border:1px solid #5c4a1f;border-radius:10px;color:#E0A93B;font-size:13px">
    Charts could not load, so the graphs on this page are blank. Every figure in the
    tables is unaffected and correct. The chart library is fetched from a CDN, which
    this network or this print did not reach.
  </div>

  <div class="tabs" id="tabs">
    <button data-t="momentum" class="on">Momentum</button>
    <button data-t="board">Leaderboard &amp; bonus</button>
  </div>
  <div class="ctxtitle" id="ctxTitle"></div>

  <div id="liveMomentum">
    <h2 style="margin-top:6px"><span class="bar"></span>Revenue against the Q3 target</h2>
    <div class="target" id="targetBanner"></div>

    <h2><span class="bar"></span>Closed won &amp; out for contract</h2>
    <p class="lead">Total, deal list and split by owner, across every owner. Quarter-level, so these do not change with the time filter.</p>
    <div class="two">
      <div class="revpanel">
        <div class="rlab">Closed won . Q3 to date . all owners</div>
        <div class="rbig g" id="cwTotal"></div>
        <div class="rsub" id="cwSub"></div>
        <canvas id="cwChart" height="150"></canvas>
        <table id="cwTable"><tbody></tbody></table>
      </div>
      <div class="revpanel">
        <div class="rlab">Out for contract . live pipeline . all owners</div>
        <div class="rbig a" id="ocTotal"></div>
        <div class="rsub" id="ocSub"></div>
        <canvas id="ocChart" height="150"></canvas>
        <table id="ocTable"><tbody></tbody></table>
      </div>
    </div>

    <div class="chartbox">
      <h3 id="acqTitle"></h3>
      <canvas id="acqChart" height="90"></canvas>
    </div>

    <div class="filterbar">
      <div class="toggle" id="toggle">
        <button data-v="today">Today</button>
        <button data-v="yesterday">Yesterday</button>
        <button data-v="week" class="on">This week</button>
        <button data-v="month">This month</button>
        <button data-v="quarter">This quarter</button>
      </div>
      <div class="range" id="rangeLabel"></div>
    </div>
    <div class="note" id="ctxNote"></div>

    <h2><span class="bar">1.</span> Metrics by person <span id="tblLabel" class="qbadge"></span> <span class="pill grey">summary</span></h2>
    <p class="lead">Sales meetings count external meetings that move a deal forward (see the definition in coverage notes). Emails are sent emails from Attio across all connected mailboxes. LI connects / LI msgs show LinkedIn connections and messages as <strong>all (deal-associated)</strong>. Progressed / shut off attributed by deal owner. Closed won and contract out are quarter-level and do not move with the filter.</p>
    <table id="summary">
      <thead><tr>
        <th>Person</th><th>Sales mtgs</th><th>Calls</th><th>Emails (deal)</th><th>LI sent</th><th>LI conn</th><th>LI msgs</th><th>Tasks</th><th>Deals</th><th>Progressed</th><th>Shut off</th><th>Contract out (£)</th><th>Closed won (£)</th>
      </tr></thead>
      <tbody id="summaryBody"></tbody>
    </table>

    <h2><span class="bar">2.</span> Scorecard <span id="scLabel" class="qbadge"></span> <span class="pill grey">per-person detail</span></h2>
    <div class="cards" id="cards"></div>

    <div class="chartbox">
      <h3 id="cmpTitle">Outreach comparison</h3>
      <canvas id="cmp" height="120"></canvas>
    </div>

    <div class="chartbox">
      <h3>Deals assigned per day (quarter to date)</h3>
      <canvas id="trend" height="120"></canvas>
    </div>

    <h2><span class="bar">3.</span> Coverage notes</h2>
    <div class="note warn" style="font-size:13px">
      <strong>What counts as a sales meeting.</strong> A scheduled conversation with at least one participant from outside Jigcar, at a prospect or customer organisation, whose purpose is to move an opportunity or account forward: discovery, intro, demo, commercials, tender, negotiation, rollout, go-live, or a recurring account or site review. Every attendee from the team is credited, since these are worked jointly.
      <br><br>
      <strong>Excluded:</strong> internal-only meetings (all attendees on a jigcar.com address), including dailies, weeklies, all-hands, one-to-ones, prep and deck reviews; advisers and the chairman; investors; media and press; suppliers and 3PL carriers; tooling and vendor demos; partner or channel exploration not attached to a deal; recruitment and personal appointments. <span id="mtgAudit"></span>
      <br><br>
      <strong>Contract out</strong> is the ARR of that person's deals sitting in Contracts now, a live pipeline figure, not period activity. <strong>Email</strong> is a de-duped multi-mailbox sent count, complete from <span id="emailFrom"></span> only; earlier days in the period carry no email coverage in this build and read as a floor of 0, not as inactivity. The routine accumulates a full day each run. The <strong>(live deal)</strong> figure beside each email count is the recipient join: the email went to a company with an open deal, New Lead through Contracts, with Closed Won accounts counted separately on the customer line. It is resolved by recipient domain to the Attio company and its strongest deal state, and is classified only for <span id="splitWindow"></span>; email totals outside that window carry no split and show 0 deal-associated, which means unclassified rather than unrelated. Join coverage: <span id="splitJoin"></span>. <strong>LinkedIn:</strong> messages are rep-attributed from Groovin chat-note titles and are complete from <span id="liFrom"></span>; invitations carry the rep in the note <em>body</em> rather than the title ("from Elliott Perks to David Farner", "James Griffin is now connected with …"), so requests sent and connections made are both attributed to a named person from Attio alone. An earlier build read only the title, found no rep, and fell back to counting cadence tasks, which credited the task assignee rather than the sender; that proxy has been removed. Each event writes a person-side and a company-side note, so events are deduped on date, rep, contact and kind. <strong>(deal)</strong> throughout means the contact's company has an open deal, New Lead through Contracts, the same test the email split uses. <strong>Connections made lag</strong> the invitation that earned them, often by weeks, so a high accepted count reflects earlier outreach rather than work done in the period. <strong>Tasks</strong> are dated by their actual completion timestamp from the Attio tasks endpoint. <strong>Progressed / shut off:</strong> measured by diffing this run's stage snapshot of all <span id="dealCount"></span> deals against the previous run's. <span id="moveNote"></span> Moves that happened before the routine existed are never backfilled, so these columns count only what the routine has actually observed between two runs.
    </div>

    <h2><span class="bar">4.</span> Read &amp; actions</h2>
    <div class="note" id="readOverall"></div>
    <ul id="readList"></ul>
  </div>

  <div id="liveBoard">
    <h2><span class="bar"></span>Closed won leaderboard</h2>
    <p class="lead">Ranked on the live quarter, with 2026 to date alongside so a quiet quarter does not hide a strong year. Both value and deal count, by close date, all owners.</p>
    <table class="lb" id="lbTable"><tbody></tbody></table>
    <div class="two">
      <div class="chartbox"><h3>Closed won value . Q3 and 2026 to date</h3><canvas id="lbValChart" height="170"></canvas></div>
      <div class="chartbox"><h3>Deals won . Q3 and 2026 to date</h3><canvas id="lbCntChart" height="170"></canvas></div>
    </div>

    <h2><span class="bar"></span>Outbound bonus <span class="pill amber">payout basis</span></h2>
    <div class="note warn" style="font-size:12.5px" id="bonusLimits"></div>
    <div id="bonusWarn"></div>
    <table id="bonusChanTable"><tbody></tbody></table>
    <h2 style="font-size:16px;margin-top:24px"><span class="bar"></span>Outbound bonus earned this quarter</h2>
    <table class="lb" id="bonusBonusTable"><tbody></tbody></table>
  </div>

  <div id="archMomentum">
    <div class="note warn" style="font-size:13px">
      <strong>Reconstructed archive, aligned to close-won date.</strong> Closed won is counted in the quarter the deal was won, the same logic as Q3. Attio has no won-date field and does not expose stage-entry timing through its API, so these close quarters were confirmed manually. From Q3 onward the routine stamps the real won date automatically. Leaderboard, owner split and acquisition channel all come from the real won records for those deals. Deals created is shown separately as context. Sales meetings, calls, emails, tasks and LinkedIn did not exist as tracked data pre-Q3, so they are not shown.
    </div>
    <div class="cards" id="archCards" style="grid-template-columns:repeat(3,1fr)"></div>

    <h2 style="font-size:16px"><span class="bar"></span>Closed won this quarter (by close date)</h2>
    <table id="archCwTable"><tbody></tbody></table>

    <h2 style="font-size:16px;margin-top:26px"><span class="bar"></span>Context: pipeline created this quarter <span class="pill grey">by creation date</span></h2>
    <table id="archOwnerTable"><tbody></tbody></table>
    <div class="two" style="margin-top:16px">
      <div class="chartbox"><h3>Deals created by owner</h3><canvas id="archOwnerChart" height="150"></canvas></div>
      <div class="chartbox"><h3>Current outcome of that quarter's created deals</h3><canvas id="archOutcomeChart" height="150"></canvas></div>
    </div>
  </div>

  <div id="archBoard">
    <h2 style="font-size:16px;margin-top:26px"><span class="bar"></span>Closed won leaderboard</h2>
    <p class="lead" style="font-size:12.5px">Ranked on the quarter, with 2026 cumulative to the end of that quarter alongside. Value and deal count, by close date, all owners.</p>
    <table class="lb" id="archLbTable"><tbody></tbody></table>
    <div class="two" style="margin-top:16px">
      <div class="chartbox"><h3>Closed won by owner . this quarter</h3><canvas id="archLbChart" height="150"></canvas></div>
      <div class="chartbox"><h3>Acquisition channel . this quarter's closed won</h3><canvas id="archAcqChart" height="150"></canvas></div>
    </div>

    <h2 style="font-size:16px;margin-top:26px"><span class="bar"></span>Outbound bonus <span class="pill amber">payout basis</span></h2>
    <div class="note warn" style="font-size:12.5px" id="archBonusLimits"></div>
    <div id="archBonusWarn"></div>
    <table id="archBonusChanTable"><tbody></tbody></table>
    <h2 style="font-size:16px;margin-top:24px"><span class="bar"></span>Outbound bonus earned this quarter</h2>
    <table class="lb" id="archBonusBonusTable"><tbody></tbody></table>
  </div>

  <div class="foot">
    Live quarter: Q3 2026 (1 Jul - 30 Sep). Target £400,000 (edit QUARTER_TARGET in the script). Sources: Granola (sales meetings), Allo (calls), Attio (emails, tasks, deals, stages), Groovin to Attio (LinkedIn). ARR = Attio deal value (GBP). Data as at the timestamp above. This page is rebuilt automatically each weekday at 08:00 and published to GitHub Pages. It does not update live in the browser, so the figures are those of the build stamped at the top. Ask Claude to rebuild if you need them sooner. Prepared for Elliott Perks.
  </div>
</div>

<script>
const reps=['Chris','Luke','James','Bianca','Elliott','Rupert'];
const roles=['Commercial Lead','Outbound / sales','Transport Director','Outbound / onboarding','Founder & CEO','Co-founder & CPO'];
const repColors=['#088E4D','#E0A93B','#A06AD9','#6AD98E','#4B9FE0','#d0d0d0'];
const green='#088E4D',bright='#6AD98E',amber='#E0A93B',red='#E05B5B',blue='#4B9FE0',grid='#2e2e2e',tick='#9a9a9a';
// Chart.js is loaded from a CDN. If it does not arrive - blocked network, offline,
// a corporate proxy, or a print that fires before the script resolves - every NUMBER
// on this page must still render. This was previously a bare Chart.defaults
// assignment here at the top of the script, which threw a ReferenceError before a
// single render function had even been defined: the scorecard, the metrics and the
// connector panel all came out empty. A missing chart library may cost the charts,
// never the data. Do not reintroduce an unguarded reference to Chart.
const CHART_OK = typeof Chart !== 'undefined';
if(CHART_OK){
  Chart.defaults.color=tick;Chart.defaults.font.family="Inter,-apple-system,sans-serif";Chart.defaults.font.size=12;
}else{
  // Stub that satisfies `new Chart(...)` and the `.destroy()` calls, so no render
  // function throws and only the canvases stay blank.
  window.Chart=function(){return {destroy(){},update(){},resize(){}};};
}

// ===== QUARTER REVENUE TARGET - update at the start of each quarter =====
const QUARTER_TARGET=__QT__; // Q3 2026
const RUN_STAMP=__RUN_STAMP__;
const RUN_DATE=__RUN_DATE__;
const STAGE_MOVES=__STAGEMOVES__;
const WON_BOOK_COUNT=__WONBOOK__;
const DEAL_COUNT=__DEALCOUNT__;
const COVERAGE=__COVERAGE__;

// ---- daily data: metric -> { 'YYYY-MM-DD': [Chris,Luke,James,Bianca,Elliott,Rupert] } ----
const daily=__DAILY__;

// ===== deal-level detail - ALL owners =====
const closedWonDeals=__CWDEALS__;
const BONUS_CHANNEL='Outbound - Direct';
const BONUS_BANDS=[
  {min:100000, pay:1000, label:'£100,000 and above'},
  {min:75000,  pay:750,  label:'£75,000 to £100,000'},
  {min:50000,  pay:500,  label:'£50,000 to £75,000'},
  {min:25000,  pay:250,  label:'£25,000 to £50,000'},
  {min:15000,  pay:200,  label:'£15,000 to £25,000'},
  {min:10000,  pay:150,  label:'£10,000 to £15,000'},
  {min:5000,   pay:100,  label:'£5,000 to £10,000'},
  {min:0,      pay:50,   label:'Up to £5,000'}
];
function bonusFor(arr){ const b=BONUS_BANDS.find(x=>arr>=x.min); return b?b.pay:0; }
function bandFor(arr){ const b=BONUS_BANDS.find(x=>arr>=x.min); return b?b.label:'-'; }
const contractDeals=__OCDEALS__;
const wonYTD=__WONYTD__;
const connectivity=__CONN__;
const offToday=__OFFTODAY__;
const attendance=__ATTENDANCE__;
const ranges=__RANGES__;
const rangeText=__RANGETEXT__;
const viewLabel={today:'Today',yesterday:'Yesterday',week:'This week',month:'This month',quarter:'This quarter'};
const acqChannels=__ACQ__;
const archives=__ARCHIVES__;

const BONUS_LIMITS='<strong>Two limits on this figure, stated every run.</strong> '+
 '1. The policy pays when the <strong>first invoice is sent within the quarter</strong>. Invoicing data is not available to this routine, so deals are placed by close date as a proxy. A deal closed late and invoiced next quarter belongs in the next payment. '+
 '2. The policy test is whether the person made the first move, which is broader than the Attio channel field. An intro they engineered qualifies; an intro that arrived unprompted does not. Where the field and the policy test disagree, the policy decides. '+
 'This table is therefore a basis for payment, not the final word.';

function agg(metric,view){
  const [s,e]=ranges[view]; const out=[0,0,0,0,0,0]; const m=daily[metric]||{};
  for(const d in m){ if(d>=s&&d<=e){ m[d].forEach((v,i)=>out[i]+=v); } }
  return out;
}
const fmtk=v=> v>=1000? '£'+(v/1000)+'k' : '£'+v;
function ownerAgg(list){ const m={}; list.forEach(d=>{m[d.owner]=(m[d.owner]||0)+d.arr}); return {labels:Object.keys(m),data:Object.values(m)}; }

let state={view:'week',tab:'momentum'};
let cmpChart,trendChart,cwChart,ocChart,lbValChart,lbCntChart,acqChart;

function render(){
  const v=state.view;
  document.getElementById('rangeLabel').textContent=rangeText[v];
  document.getElementById('scLabel').textContent=viewLabel[v];
  document.getElementById('tblLabel').textContent=viewLabel[v];

  const mtgs=agg('meetings',v),calls=agg('calls',v),emails=agg('emails',v),tasks=agg('tasks',v),deals=agg('deals',v),prog=agg('progressed',v),shut=agg('shutoff',v);
  const liCa=agg('liConnAll',v),liCd=agg('liConnDeal',v),liMa=agg('liMsgAll',v),liMd=agg('liMsgDeal',v);
  const emDeal=agg('emailsDeal',v),emCust=agg('emailsCust',v);
  const liAa=agg('liAccAll',v),liAd=agg('liAccDeal',v);
  const cwByRep=reps.map(r=>closedWonDeals.filter(d=>d.owner===r).reduce((a,d)=>a+d.arr,0));
  const ocByRep=reps.map(r=>contractDeals.filter(d=>d.owner===r).reduce((a,d)=>a+d.arr,0));

  const dailyView=(v==='today'||v==='yesterday');
  document.getElementById('ctxNote').innerHTML= dailyView
    ? '<strong>'+viewLabel[v]+' ('+rangeText[v]+').</strong> Single-day snapshot. Revenue, leaderboard and contract-out stay at quarter level.'
    : (v==='month'||v==='quarter'
        ? '<strong>'+viewLabel[v]+'.</strong> Sales meetings and deals cover the full month. Calls and tasks began 21-22 Jul (Allo and cadence switch-on) and email coverage starts '+COVERAGE.email_covered_from+', so those match the week for now.'
        : '<strong>This week ('+rangeText[v]+').</strong> The calendar week, Monday to Sunday, counted to date. On a Monday that is a single day, so the month and quarter views carry the fuller picture.');

  const cards=document.getElementById('cards'); cards.innerHTML='';
  reps.forEach((r,i)=>{
    cards.innerHTML+=`<div class="card">
      <div class="name">${r}${(function(){var o=offToday.filter(function(e){return e.person===r;})[0];
        return o?'<span class="leavetag">'+(o.half?'off '+o.half:'on leave')+'</span>':'';})()}</div>
      <div class="role">${roles[i]}</div>
      <div class="stat"><span>Sales meetings</span><span class="v ${mtgs[i]?'g':'m'}">${mtgs[i]}</span></div>
      <div class="stat"><span>Calls</span><span class="v ${calls[i]?'':'m'}">${(connectivity.seats[r]||[])[0]==='na'?'n/a':calls[i]}</span></div>
      <div class="stat"><span>Emails <span class="m" style="font-weight:600">(live deal)</span></span><span class="v ${emails[i]?'g':'m'}">${emails[i]} <span class="m" style="font-weight:600">(${emDeal[i]})</span></span></div>
      <div class="stat"><span>… to customers</span><span class="v ${emCust[i]?'g':'m'}">${emCust[i]}</span></div>
      <div class="stat"><span>LI requests sent <span class="m" style="font-weight:600">(deal)</span></span><span class="v ${liCa[i]?'g':'m'}">${liCa[i]} <span class="m" style="font-weight:600">(${liCd[i]})</span></span></div>
      <div class="stat"><span>LI connections made <span class="m" style="font-weight:600">(deal)</span></span><span class="v ${liAa[i]?'g':'m'}">${liAa[i]} <span class="m" style="font-weight:600">(${liAd[i]})</span></span></div>
      <div class="stat"><span>LI messages (deal)</span><span class="v ${liMa[i]?'g':'m'}">${liMa[i]} <span class="m" style="font-weight:600">(${liMd[i]})</span></span></div>
      <div class="stat"><span>Tasks done</span><span class="v ${tasks[i]?'g':'m'}">${tasks[i]}</span></div>
      <div class="stat"><span>Deals assigned</span><span class="v">${deals[i]}</span></div>
      <div class="stat"><span>Progressed</span><span class="v ${prog[i]?'g':'m'}">${prog[i]}</span></div>
      <div class="stat"><span>Shut off</span><span class="v ${shut[i]?'r':'m'}">${shut[i]}</span></div>
      <div class="stat"><span>Contract out <span class="m" style="font-weight:600">live</span></span><span class="v ${ocByRep[i]?'a':'m'}">${fmtk(ocByRep[i])}</span></div>
      <div class="stat"><span>Closed won <span class="m" style="font-weight:600">quarter</span></span><span class="v ${cwByRep[i]?'g':'m'}">${fmtk(cwByRep[i])}</span></div>
    </div>`;
  });

  const tb=document.getElementById('summaryBody'); tb.innerHTML='';
  const tot=[0,0,0,0,0,0,0,0,0,0,0,0];
  reps.forEach((r,i)=>{
    tb.innerHTML+=`<tr><td>${r}</td>
      <td class="${mtgs[i]?'g':'m'}">${mtgs[i]}</td>
      <td>${(connectivity.seats[r]||[])[0]==='na'?'<span class="m">n/a</span>':calls[i]}</td>
      <td class="${emails[i]?'g':'m'}">${emails[i]} <span class="m">(${emDeal[i]})</span></td>
      <td class="${liCa[i]?'':'m'}">${liCa[i]} <span class="m">(${liCd[i]})</span></td>
      <td class="${liAa[i]?'':'m'}">${liAa[i]} <span class="m">(${liAd[i]})</span></td>
      <td class="${liMa[i]?'':'m'}">${liMa[i]} <span class="m">(${liMd[i]})</span></td>
      <td>${tasks[i]}</td><td>${deals[i]}</td>
      <td class="${prog[i]?'g':'m'}">${prog[i]}</td><td class="${shut[i]?'r':'m'}">${shut[i]}</td>
      <td class="${ocByRep[i]?'a':'m'}">${ocByRep[i]?'£'+ocByRep[i].toLocaleString():'£0'}</td>
      <td class="${cwByRep[i]?'g':'m'}">${cwByRep[i]?'£'+cwByRep[i].toLocaleString():'£0'}</td></tr>`;
    tot[0]+=mtgs[i];tot[1]+=calls[i];tot[2]+=emails[i];tot[3]+=liCa[i];tot[11]+=liAa[i];tot[4]+=liMa[i];tot[5]+=tasks[i];tot[6]+=deals[i];tot[7]+=prog[i];tot[8]+=shut[i];tot[9]+=ocByRep[i];tot[10]+=cwByRep[i];
  });
  tb.innerHTML+=`<tr><td class="total">Team</td><td class="total">${tot[0]}</td><td class="total">${tot[1]}</td><td class="total">${tot[2]}</td><td class="total">${tot[3]}</td><td class="total">${tot[11]}</td><td class="total">${tot[4]}</td><td class="total">${tot[5]}</td><td class="total">${tot[6]}</td><td class="total">${tot[7]}</td><td class="total">${tot[8]}</td><td class="total">£${tot[9].toLocaleString()}</td><td class="total">£${tot[10].toLocaleString()}</td></tr>`;

  document.getElementById('cmpTitle').textContent='Outreach comparison ('+viewLabel[v]+')';
  if(cmpChart)cmpChart.destroy();
  cmpChart=new Chart(document.getElementById('cmp'),{type:'bar',data:{labels:reps,datasets:[
    {label:'Sales meetings',data:mtgs,backgroundColor:green},
    {label:'Calls',data:calls,backgroundColor:blue},
    {label:'Emails',data:emails,backgroundColor:bright},
    {label:'LI connects',data:liCa,backgroundColor:'#0a72c4'},
    {label:'LI messages',data:liMa,backgroundColor:'#7db8e8'},
    {label:'Progressed',data:prog,backgroundColor:amber}
  ]},options:{responsive:true,scales:{x:{grid:{color:grid}},y:{grid:{color:grid},beginAtZero:true}},plugins:{legend:{position:'top'}}}});
}

function renderBanner(){
  const cw=closedWonDeals.reduce((a,d)=>a+d.arr,0);
  const oc=contractDeals.reduce((a,d)=>a+d.arr,0);
  const wonPct=Math.round(cw/QUARTER_TARGET*1000)/10;
  const ocPct=Math.round(oc/QUARTER_TARGET*1000)/10;
  const gap=QUARTER_TARGET-cw;
  const gapIfLand=Math.max(0,QUARTER_TARGET-cw-oc);
  document.getElementById('targetBanner').innerHTML=`
    <div class="thead">
      <div><div class="tlabel">Q3 2026 revenue target</div>
      <div class="tbig">£${QUARTER_TARGET.toLocaleString()}</div></div>
      <div style="text-align:right">
        <div class="tbig g" style="font-size:26px">£${cw.toLocaleString()} <small>closed (${wonPct}%)</small></div>
        <div class="rsub" style="margin:4px 0 0">£${gap.toLocaleString()} to target . £${oc.toLocaleString()} out for contract</div>
      </div>
    </div>
    <div class="tbar">
      <div class="won" style="width:${Math.min(100,wonPct)}%"></div>
      <div class="oc" style="width:${Math.min(Math.max(0,100-wonPct),ocPct)}%"></div>
    </div>
    <div class="tlegend">
      <div class="k"><span class="sw" style="background:var(--green)"></span> Closed won <b>£${cw.toLocaleString()}</b></div>
      <div class="k"><span class="sw" style="background:#0e6b3a"></span> Out for contract <b>£${oc.toLocaleString()}</b></div>
      <div class="k"><span class="sw" style="background:#0c0c0c;border:1px solid #333"></span> Remaining <b>£${gapIfLand.toLocaleString()}</b> if contracts land</div>
    </div>`;
}

function renderRevenue(){
  const cwTot=closedWonDeals.reduce((a,d)=>a+d.arr,0), ocTot=contractDeals.reduce((a,d)=>a+d.arr,0);
  const cwn=closedWonDeals.length, ocn=contractDeals.length;
  document.getElementById('cwTotal').textContent='£'+cwTot.toLocaleString();
  document.getElementById('cwSub').textContent=cwn+' deal'+(cwn===1?'':'s')+' won this quarter';
  document.getElementById('ocTotal').textContent='£'+ocTot.toLocaleString();
  document.getElementById('ocSub').textContent=ocn+' deal'+(ocn===1?'':'s')+' in Contracts stage now';
  const cwHead='<thead><tr><th>Deal</th><th>ARR</th><th>Closed</th><th>Owner</th></tr></thead>';
  const ocHead='<thead><tr><th>Deal</th><th>ARR</th><th>Est. close</th><th>Owner</th></tr></thead>';
  const cwRows=closedWonDeals.map(d=>`<tr><td>${d.name}</td><td class="g">£${d.arr.toLocaleString()}</td><td class="m">${d.date}</td><td>${d.owner}</td></tr>`).join('');
  document.getElementById('cwTable').innerHTML=cwHead+'<tbody>'+cwRows+`<tr><td class="total">Total</td><td class="total">£${cwTot.toLocaleString()}</td><td class="total">${cwn} deal${cwn===1?'':'s'}</td><td></td></tr></tbody>`;
  const ocRows=contractDeals.map(d=>`<tr><td>${d.name}</td><td class="a">£${d.arr.toLocaleString()}</td><td class="m">${d.date}</td><td>${d.owner}</td></tr>`).join('');
  document.getElementById('ocTable').innerHTML=ocHead+'<tbody>'+ocRows+`<tr><td class="total">Total</td><td class="total">£${ocTot.toLocaleString()}</td><td class="total">${ocn} deal${ocn===1?'':'s'}</td><td></td></tr></tbody>`;
  const cwo=ownerAgg(closedWonDeals), oco=ownerAgg(contractDeals);
  if(cwChart)cwChart.destroy();
  cwChart=new Chart(document.getElementById('cwChart'),{type:'bar',data:{labels:cwo.labels,datasets:[{label:'Closed won',data:cwo.data,backgroundColor:green}]},options:{responsive:true,plugins:{legend:{display:false}},scales:{x:{grid:{color:grid}},y:{grid:{color:grid},beginAtZero:true,ticks:{callback:x=>'£'+(x/1000)+'k'}}}}});
  if(ocChart)ocChart.destroy();
  ocChart=new Chart(document.getElementById('ocChart'),{type:'bar',data:{labels:oco.labels,datasets:[{label:'Out for contract',data:oco.data,backgroundColor:amber}]},options:{responsive:true,plugins:{legend:{display:false}},scales:{x:{grid:{color:grid}},y:{grid:{color:grid},beginAtZero:true,ticks:{callback:x=>'£'+(x/1000)+'k'}}}}});
}

function renderLeaderboard(){
  const rows=reps.map(r=>{
    const q3=wonYTD.filter(d=>d.owner===r&&d.quarter==='Q3');
    const ytd=wonYTD.filter(d=>d.owner===r);
    return {name:r, q3v:q3.reduce((a,d)=>a+d.arr,0), q3n:q3.length,
            yv:ytd.reduce((a,d)=>a+d.arr,0), yn:ytd.length};
  }).sort((a,b)=> b.q3v-a.q3v || b.yv-a.yv);
  const medal=i=> i===0?'<span class="medal">1</span>':i===1?'<span class="medal">2</span>':i===2?'<span class="medal">3</span>':(i+1);
  const body=rows.map((o,i)=>`<tr>
    <td>${o.q3v||o.yv?medal(i):'-'}</td>
    <td>${o.name}</td>
    <td class="${o.q3v?'g':'m'}">${o.q3v?'£'+o.q3v.toLocaleString():'£0'}</td>
    <td class="${o.q3n?'':'m'}">${o.q3n}</td>
    <td class="${o.yv?'g':'m'}">${o.yv?'£'+o.yv.toLocaleString():'£0'}</td>
    <td class="${o.yn?'':'m'}">${o.yn}</td></tr>`).join('');
  const tQ3v=rows.reduce((a,o)=>a+o.q3v,0), tQ3n=rows.reduce((a,o)=>a+o.q3n,0);
  const tYv=rows.reduce((a,o)=>a+o.yv,0), tYn=rows.reduce((a,o)=>a+o.yn,0);
  document.getElementById('lbTable').innerHTML=
    '<thead><tr><th></th><th>Person</th><th>Q3 closed won</th><th>Q3 deals</th><th>2026 closed won</th><th>2026 deals</th></tr></thead><tbody>'
    +body+`<tr><td></td><td class="total">Team</td><td class="total">£${tQ3v.toLocaleString()}</td><td class="total">${tQ3n}</td><td class="total">£${tYv.toLocaleString()}</td><td class="total">${tYn}</td></tr></tbody>`;
  const labels=rows.map(o=>o.name);
  if(lbValChart)lbValChart.destroy();
  lbValChart=new Chart(document.getElementById('lbValChart'),{type:'bar',data:{labels,datasets:[
    {label:'Q3',data:rows.map(o=>o.q3v),backgroundColor:green},
    {label:'2026 to date',data:rows.map(o=>o.yv),backgroundColor:'#1f5c3a'}
  ]},options:{indexAxis:'y',responsive:true,plugins:{legend:{position:'top'}},scales:{x:{grid:{color:grid},beginAtZero:true,ticks:{callback:x=>'£'+(x/1000)+'k'}},y:{grid:{display:false}}}}});
  if(lbCntChart)lbCntChart.destroy();
  lbCntChart=new Chart(document.getElementById('lbCntChart'),{type:'bar',data:{labels,datasets:[
    {label:'Q3',data:rows.map(o=>o.q3n),backgroundColor:bright},
    {label:'2026 to date',data:rows.map(o=>o.yn),backgroundColor:'#2f7d54'}
  ]},options:{indexAxis:'y',responsive:true,plugins:{legend:{position:'top'}},scales:{x:{grid:{color:grid},beginAtZero:true,ticks:{stepSize:1}},y:{grid:{display:false}}}}});
}

// ===== channel detail + direct outbound bonus basis (shared by live and archive) =====
function renderChannels(deals,prefix){
  const el=id=>document.getElementById(id);
  if(!el(prefix+'ChanTable')||!el(prefix+'BonusTable')){
    console.warn('renderChannels: missing target for prefix '+prefix); return;
  }
  if(el(prefix+'Limits')) el(prefix+'Limits').innerHTML=BONUS_LIMITS;
  const q=d=>d.channel===BONUS_CHANNEL;
  const isUnset=d=>!d.channel||d.channel==='Unassigned';
  const unassigned=deals.filter(isUnset);
  if(el(prefix+'Warn')){
    el(prefix+'Warn').innerHTML = unassigned.length
      ? '<div class="note flag" style="font-size:13px"><strong>Do not pay yet.</strong> '+unassigned.length+
        ' closed won deal'+(unassigned.length===1?'':'s')+' in this quarter has no acquisition channel set in Attio, so '+
        (unassigned.length===1?'it is':'they are')+' excluded from the qualifying total rather than assumed outbound: '+
        unassigned.map(d=>d.name+' (£'+d.arr.toLocaleString()+', '+d.owner+')').join('; ')+
        '. Set the channel in Attio, then re-read this table before authorising payment.</div>'
      : '<div class="note" style="font-size:13px"><strong>Every closed won deal in this quarter has an acquisition channel set.</strong> Nothing is excluded for a missing channel, so the qualifying total below is complete on the field test.</div>';
  }
  const rows=deals.map(d=>{
    const pay=bonusFor(d.arr);
    const bonusCell = q(d) ? `<span class="g" style="font-weight:700">£${pay}</span>`
      : isUnset(d) ? `<span class="r" style="font-weight:600">not set</span> <span class="m">(£${pay} if outbound)</span>`
      : '<span class="m">-</span>';
    const chanCls = q(d)?'g':(isUnset(d)?'r':'m');
    return `<tr><td>${d.name}</td><td>£${d.arr.toLocaleString()}</td><td>${d.owner}</td><td class="m">${d.date}</td><td class="${chanCls}">${d.channel||'Unassigned'}</td><td class="m" style="font-size:12.5px">${bandFor(d.arr)}</td><td>${bonusCell}</td></tr>`;
  }).join('');
  const qual=deals.filter(q);
  const qTot=qual.reduce((a,d)=>a+d.arr,0);
  const payTot=qual.reduce((a,d)=>a+bonusFor(d.arr),0);
  document.getElementById(prefix+'ChanTable').innerHTML=
    '<thead><tr><th>Deal</th><th>ARR</th><th>Owner</th><th>Closed</th><th>Acquisition channel</th><th>Band</th><th>Bonus</th></tr></thead><tbody>'
    +(rows||'<tr><td class="m" style="text-align:left">No closed won deals in this quarter.</td></tr>')
    +`<tr><td class="total">Qualifying</td><td class="total">£${qTot.toLocaleString()}</td><td class="total">${qual.length} deal${qual.length===1?'':'s'}</td><td></td><td></td><td></td><td class="total">£${payTot.toLocaleString()}</td></tr></tbody>`;

  const owners=[...new Set(deals.map(d=>d.owner))];
  const brows=owners.map(o=>{
    const mine=deals.filter(d=>d.owner===o);
    const qd=mine.filter(q);
    const ud=mine.filter(isUnset);
    return {o, qn:qd.length, qv:qd.reduce((a,d)=>a+d.arr,0),
            pay:qd.reduce((a,d)=>a+bonusFor(d.arr),0),
            detail:qd.map(d=>d.name+' £'+bonusFor(d.arr)).join(', ')||'-',
            un:ud.length, upay:ud.reduce((a,d)=>a+bonusFor(d.arr),0)};
  }).sort((a,b)=>b.pay-a.pay || b.qv-a.qv);
  const body=brows.map((r,i)=>`<tr>
    <td>${r.pay?i+1:'-'}</td><td>${r.o}</td>
    <td class="${r.pay?'g':'m'}" style="font-weight:700">£${r.pay.toLocaleString()}</td>
    <td class="${r.qn?'':'m'}">${r.qn}</td>
    <td class="${r.qv?'g':'m'}">£${r.qv.toLocaleString()}</td>
    <td class="m" style="text-align:left;font-size:12.5px">${r.detail}</td>
    <td class="${r.un?'r':'m'}">${r.un?r.un+' / £'+r.upay.toLocaleString():'-'}</td></tr>`).join('');
  const tp=brows.reduce((a,r)=>a+r.pay,0), tn=brows.reduce((a,r)=>a+r.qn,0), tv=brows.reduce((a,r)=>a+r.qv,0);
  const tu=brows.reduce((a,r)=>a+r.un,0), tup=brows.reduce((a,r)=>a+r.upay,0);
  document.getElementById(prefix+'BonusTable').innerHTML=
    '<thead><tr><th></th><th>Person</th><th>Bonus earned</th><th>Deals</th><th>Qualifying ARR</th><th>Breakdown</th><th>Pending channel</th></tr></thead><tbody>'
    +(body||'<tr><td class="m" style="text-align:left">Nothing to pay this quarter.</td></tr>')
    +`<tr><td></td><td class="total">Total</td><td class="total">£${tp.toLocaleString()}</td><td class="total">${tn}</td><td class="total">£${tv.toLocaleString()}</td><td></td><td class="total">${tu?tu+' / £'+tup.toLocaleString():'-'}</td></tr></tbody>`;
}

function statusLabel(s){ return s==='ok'?'connected':s==='partial'?'partial':s==='down'?'down':s==='na'?'n/a':'unknown'; }
function renderConn(){
  const ws=connectivity.workspace.map(t=>`<span class="chip"><span class="cdot ${t.status}"></span><b>${t.name}</b> <small>${t.note}</small></span>`).join('');
  const cols=['Allo','Email','Groovin'];
  let head='<tr><th>Person</th>'+cols.map(c=>`<th>${c}</th>`).join('')+'</tr>';
  let rows=reps.map(r=>{ const s=(Array.isArray(connectivity.seats[r])?connectivity.seats[r]:['unknown','unknown','unknown']);
    return `<tr><td>${r}</td>`+s.map(x=>`<td><span class="cdot ${x}" title="${statusLabel(x)}"></span></td>`).join('')+'</tr>';
  }).join('');
  document.getElementById('conn').innerHTML=`
    <div class="ttl">Connectivity . data as at ${connectivity.updated} . rebuilt each weekday 08:00</div>
    <div class="ws">${ws}</div>
    <table class="cmatrix"><thead>${head}</thead><tbody>${rows}</tbody></table>
    ${offToday.length?'<div class="offrow"><span class="k">Off today</span>'+offToday.map(function(e){
        return '<span class="offpill">'+e.person+(e.half?' <small>'+e.half+' only</small>':'')+'</span>';}).join('')
      +'<span class="m" style="font-size:11px">from the Zelt absence calendar</span></div>'
      :'<div class="offrow"><span class="k">Off today</span><span class="m" style="font-size:12px">nobody</span></div>'}
    <div class="legend">
      <span><span class="cdot ok"></span> connected</span>
      <span><span class="cdot partial"></span> partial</span>
      <span><span class="cdot unknown"></span> unknown</span>
      <span><span class="cdot down"></span> down</span>
      <span><span class="cdot na"></span> no account</span>
    </div>`;
  document.getElementById('lastRefresh').textContent=RUN_STAMP;
}

function renderCoverage(){
  document.getElementById('emailFrom').textContent=COVERAGE.email_covered_from;
  document.getElementById('liFrom').textContent=COVERAGE.linkedin_notes_covered_from;
  document.getElementById('splitWindow').textContent=(COVERAGE.email_split_from===COVERAGE.email_split_to)
    ? COVERAGE.email_split_from : COVERAGE.email_split_from+' to '+COVERAGE.email_split_to;
  document.getElementById('splitJoin').textContent=COVERAGE.email_split_join;
  document.getElementById('dealCount').textContent=DEAL_COUNT;
  // Built from the observed moves, never written into the template. A hardcoded
  // sentence about "today's diff" reads as fact and is wrong by the next morning.
  (function(){
    const today=(STAGE_MOVES||[]).filter(m=>m.date===RUN_DATE);
    const fwd=today.filter(m=>m.kind==='progressed'), off=today.filter(m=>m.kind==='shutoff');
    const N=['no','one','two','three','four','five','six','seven','eight','nine','ten'];
    const num=n=>N[n]!==undefined?N[n]:String(n);
    const named=ms=>ms.map(m=>m.name+' ('+m.owner+')').join(', ');
    let s;
    if(!today.length){ s='This run observed no stage change against the previous snapshot.'; }
    else{
      const bits=[];
      if(fwd.length){
        const hops=[...new Set(fwd.map(m=>m.from+' to '+m.to))];
        bits.push('found '+num(fwd.length)+' forward move'+(fwd.length===1?'':'s')+
          (hops.length===1?', all '+hops[0]:'')+': '+named(fwd)+'.');
      }
      if(off.length) bits.push(num(off.length)+' shut off: '+named(off)+'.');
      else if(fwd.length) bits.push('Nothing was shut off.');
      s="Today's diff "+bits.join(' ');
    }
    document.getElementById('moveNote').textContent=s;
  })();
  document.getElementById('mtgAudit').innerHTML='This run read '+COVERAGE.mtg_notes+
    ' Granola notes for the quarter to date, which dedupe to '+COVERAGE.mtg_total+
    ' distinct meetings: '+COVERAGE.mtg_internal+' internal-only, '+
    COVERAGE.mtg_excluded+' external but excluded by the rules above, and '+COVERAGE.mtg_included+
    ' counted as sales meetings, each credited to every Jigcar attendee.';
  document.getElementById('acqTitle').textContent='Acquisition channel . all '+WON_BOOK_COUNT+' closed won deals (full won book, not just Q3)';
}

function renderRead(){
  document.getElementById('readOverall').innerHTML=__READ_OVERALL__;
  document.getElementById('readList').innerHTML=__READ_LIST__;
}

// ---- Query this data with Claude ----
// Serialises the whole build to JSON so it can be pasted into a chat. The known
// gaps come from the run's own coverage record, so this never claims a limit the
// routine has since closed.
function buildPayload(){
  const cwTot=closedWonDeals.reduce((a,d)=>a+d.arr,0);
  const ocTot=contractDeals.reduce((a,d)=>a+d.arr,0);
  const perPeriod={};
  ['today','yesterday','week','month','quarter'].forEach(v=>{
    perPeriod[v]={range:rangeText[v]};
    ['meetings','calls','emails','tasks','deals','progressed','shutoff','liConnAll','liConnDeal','liMsgAll','liMsgDeal']
      .forEach(m=>{ perPeriod[v][m]=Object.fromEntries(reps.map((r,i)=>[r,agg(m,v)[i]])); });
  });
  return {
    what_this_is:"Jigcar Team Momentum dashboard data. All figures in GBP. Answer only from this data; if something is not here, say so rather than estimating.",
    data_as_at:connectivity.updated,
    live_quarter:{name:"Q3 2026",runs:"1 Jul - 30 Sep",target:QUARTER_TARGET,
      closed_won:cwTot,percent_of_target:Math.round(cwTot/QUARTER_TARGET*1000)/10,
      out_for_contract:ocTot,short_if_all_contracts_land:Math.max(0,QUARTER_TARGET-cwTot-ocTot)},
    people:reps.map((r,i)=>({name:r,role:roles[i]})),
    closed_won_this_quarter:closedWonDeals,
    out_for_contract_now:contractDeals,
    closed_won_2026_by_close_date:wonYTD,
    outbound_bonus:{
      rule:"Only acquisition channel 'Outbound - Direct' qualifies. Bands are inclusive lower bounds; on a boundary the higher band applies.",
      bands:BONUS_BANDS.map(b=>({from:b.min,pays:b.pay,label:b.label})),
      caveats:["Policy pays when the first invoice is sent within the quarter; invoicing data is not available here, so deals are placed by close date.",
               "The policy test is whether the person made the first move, which is broader than the Attio channel. An engineered intro qualifies; an unprompted one does not."],
      earned_by_quarter:Object.fromEntries(['Q1','Q2','Q3'].map(q=>{
        const qual=wonYTD.filter(d=>d.quarter===q&&d.channel===BONUS_CHANNEL);
        return [q,{total:qual.reduce((a,d)=>a+bonusFor(d.arr),0),
          deals:qual.map(d=>({deal:d.name,owner:d.owner,arr:d.arr,bonus:bonusFor(d.arr)}))}];
      }))
    },
    acquisition_channel_full_won_book:acqChannels,
    metrics_by_person_by_period:perPeriod,
    daily_metrics_raw:{note:"arrays are ordered "+reps.join(', '),data:daily},
    connectivity:{workspace:connectivity.workspace,per_seat_allo_email_groovin:connectivity.seats},
    archive_quarters:archives,
    definitions:{
      sales_meeting:"A scheduled conversation with at least one participant from outside Jigcar, at a prospect or customer, to move an opportunity or account forward. Every Jigcar attendee is credited. Excludes internal-only meetings, advisers, investors, media, suppliers, vendor demos, partner exploration not tied to a deal, recruitment and personal appointments.",
      progressed:"Deals owned by that person that moved forward a stage in the period, attributed by deal owner rather than by who made the change.",
      shut_off:"Deals owned by that person moved to Nurture, Closed Lost, Churn or Non-ICP.",
      contract_out:"ARR of that person's deals currently in Contracts. A live snapshot, not period activity.",
      known_gaps:COVERAGE.known_gaps
    }
  };
}

function copyPayload(){
  // The anchor handles opening Claude, so this only copies. Opening a window from inside
  // the clipboard promise gets popup-blocked, which is why navigation is left to the link.
  const text = "Here is my sales team dashboard data. Answer questions using only these figures.\n\n"
    + "```json\n"+JSON.stringify(buildPayload(),null,2)+"\n```";
  const msg=document.getElementById('askmsg');
  const done=()=>{
    msg.textContent='Copied. Paste it into the chat, then ask your question.';
    setTimeout(()=>{msg.textContent='';},8000);
  };
  if(navigator.clipboard&&window.isSecureContext){
    navigator.clipboard.writeText(text).then(done).catch(()=>fallback(text,done,msg));
  } else { fallback(text,done,msg); }
  return true; // let the link navigate
}
function fallback(text,done,msg){
  try{
    const ta=document.createElement('textarea');
    ta.value=text; ta.style.position='fixed'; ta.style.left='-9999px';
    document.body.appendChild(ta); ta.select(); document.execCommand('copy');
    document.body.removeChild(ta); done();
  }catch(e){ msg.textContent='Could not copy automatically. Try again, or use a browser that allows clipboard access.'; }
}


function buildTrend(){
  const days=__TREND_DAYS__;
  const labels=__TREND_LABELS__;
  function series(i){ return days.map(d=>{ return daily.deals[d]?daily.deals[d][i]:0; }); }
  if(trendChart)trendChart.destroy();
  trendChart=new Chart(document.getElementById('trend'),{type:'line',data:{labels,datasets:[
    {label:'Chris',data:series(0),borderColor:repColors[0],backgroundColor:repColors[0],tension:.3,pointRadius:2},
    {label:'Luke',data:series(1),borderColor:repColors[1],backgroundColor:repColors[1],tension:.3,pointRadius:2},
    {label:'Elliott',data:series(4),borderColor:repColors[4],backgroundColor:repColors[4],tension:.3,pointRadius:2}
  ]},options:{responsive:true,scales:{x:{grid:{color:grid}},y:{grid:{color:grid},beginAtZero:true}},plugins:{legend:{position:'top'}}}});
}

function buildAcq(){
  if(acqChart)acqChart.destroy();
  acqChart=new Chart(document.getElementById('acqChart'),{type:'bar',
    data:{labels:Object.keys(acqChannels),datasets:[{label:'Closed won deals',data:Object.values(acqChannels),
      backgroundColor:['#088E4D','#6AD98E','#4B9FE0','#7db8e8','#0a72c4','#666']}]},
    options:{indexAxis:'y',responsive:true,plugins:{legend:{display:false}},
      scales:{x:{grid:{color:grid},beginAtZero:true,ticks:{stepSize:1}},y:{grid:{display:false}}}}});
}

// ===== ARCHIVE =====
let archOwnerChart,archOutcomeChart,archLbChart,archAcqChart;
const QORDER=['Q1','Q2','Q3'];
function renderArchive(q){
  const a=archives[q]; if(!a) return;
  const cwVal=a.closedWon.reduce((s,d)=>s+d.arr,0), cwN=a.closedWon.length;
  document.getElementById('archCards').innerHTML=`
    <div class="card"><div class="role">Closed won this quarter (by close date)</div><div class="rbig ${cwN?'g':'m'}" style="font-size:30px;font-weight:800">${cwN} <span class="m" style="font-size:14px;font-weight:600">/ £${cwVal.toLocaleString()}</span></div></div>
    <div class="card"><div class="role">Deals created (context)</div><div class="rbig" style="font-size:30px;font-weight:800">${a.createdCount}</div></div>
    <div class="card"><div class="role">Pipeline value created (context)</div><div class="rbig g" style="font-size:30px;font-weight:800">£${(a.createdPipeline/1000).toLocaleString()}k</div></div>`;
  const cw=document.getElementById('archCwTable');
  if(cwN){
    const rows=a.closedWon.map(d=>`<tr><td>${d.name}</td><td class="g">£${d.arr.toLocaleString()}</td><td class="m">${d.date}</td><td>${d.owner}</td></tr>`).join('');
    cw.innerHTML='<thead><tr><th>Deal</th><th>ARR</th><th>Closed</th><th>Owner</th></tr></thead><tbody>'+rows+
      `<tr><td class="total">Total</td><td class="total">£${cwVal.toLocaleString()}</td><td class="total">${cwN} deal${cwN===1?'':'s'}</td><td></td></tr></tbody>`;
  } else { cw.innerHTML='<tbody><tr><td class="m" style="text-align:left;padding:12px 8px">No deals closed won in this quarter.</td></tr></tbody>'; }
  renderChannels(a.closedWon,'archBonus');
  const qKey=q.split('-')[0];
  const qIdx=QORDER.indexOf(qKey);
  const lbRows=reps.map(r=>{
    const inQ=wonYTD.filter(d=>d.owner===r&&d.quarter===qKey);
    const cum=wonYTD.filter(d=>d.owner===r&&QORDER.indexOf(d.quarter)<=qIdx);
    return {name:r, qv:inQ.reduce((x,d)=>x+d.arr,0), qn:inQ.length,
            cv:cum.reduce((x,d)=>x+d.arr,0), cn:cum.length};
  }).sort((x,y)=> y.qv-x.qv || y.cv-x.cv);
  const rank=i=> i+1;
  const lbBody=lbRows.map((o,i)=>`<tr>
    <td>${o.qv||o.cv?rank(i):'-'}</td><td>${o.name}</td>
    <td class="${o.qv?'g':'m'}">${o.qv?'£'+o.qv.toLocaleString():'£0'}</td>
    <td class="${o.qn?'':'m'}">${o.qn}</td>
    <td class="${o.cv?'g':'m'}">${o.cv?'£'+o.cv.toLocaleString():'£0'}</td>
    <td class="${o.cn?'':'m'}">${o.cn}</td></tr>`).join('');
  const tqv=lbRows.reduce((x,o)=>x+o.qv,0), tqn=lbRows.reduce((x,o)=>x+o.qn,0);
  const tcv=lbRows.reduce((x,o)=>x+o.cv,0), tcn=lbRows.reduce((x,o)=>x+o.cn,0);
  document.getElementById('archLbTable').innerHTML=
    `<thead><tr><th></th><th>Person</th><th>${qKey} closed won</th><th>${qKey} deals</th><th>2026 to end ${qKey}</th><th>Deals</th></tr></thead><tbody>`
    +lbBody+`<tr><td></td><td class="total">Team</td><td class="total">£${tqv.toLocaleString()}</td><td class="total">${tqn}</td><td class="total">£${tcv.toLocaleString()}</td><td class="total">${tcn}</td></tr></tbody>`;

  const wonOwners=lbRows.filter(o=>o.qv>0);
  if(archLbChart)archLbChart.destroy();
  archLbChart=new Chart(document.getElementById('archLbChart'),{type:'bar',
    data:{labels:wonOwners.length?wonOwners.map(o=>o.name):['none'],
      datasets:[{label:'Closed won',data:wonOwners.length?wonOwners.map(o=>o.qv):[0],backgroundColor:green}]},
    options:{indexAxis:'y',responsive:true,plugins:{legend:{display:false}},
      scales:{x:{grid:{color:grid},beginAtZero:true,ticks:{callback:x=>'£'+(x/1000)+'k'}},y:{grid:{display:false}}}}});

  const acq=a.acquisition||{};
  const acqKeys=Object.keys(acq);
  if(archAcqChart)archAcqChart.destroy();
  archAcqChart=new Chart(document.getElementById('archAcqChart'),{type:'bar',
    data:{labels:acqKeys.length?acqKeys:['none'],
      datasets:[{label:'Deals',data:acqKeys.length?Object.values(acq):[0],
        backgroundColor:['#088E4D','#6AD98E','#4B9FE0','#7db8e8','#0a72c4','#666']}]},
    options:{indexAxis:'y',responsive:true,plugins:{legend:{display:false}},
      scales:{x:{grid:{color:grid},beginAtZero:true,ticks:{stepSize:1}},y:{grid:{display:false}}}}});

  const rows=a.byOwner.map(o=>`<tr><td>${o.name}</td><td>${o.created}</td><td class="g">£${o.value.toLocaleString()}</td></tr>`).join('');
  const tot=a.byOwner.reduce((s,o)=>({c:s.c+o.created,v:s.v+o.value}),{c:0,v:0});
  document.getElementById('archOwnerTable').innerHTML='<thead><tr><th>Owner</th><th>Deals created</th><th>Pipeline value</th></tr></thead><tbody>'+rows+
    `<tr><td class="total">Total</td><td class="total">${tot.c}</td><td class="total">£${tot.v.toLocaleString()}</td></tr></tbody>`;
  if(archOwnerChart)archOwnerChart.destroy();
  archOwnerChart=new Chart(document.getElementById('archOwnerChart'),{type:'bar',data:{labels:a.byOwner.map(o=>o.name),datasets:[{label:'Deals created',data:a.byOwner.map(o=>o.created),backgroundColor:green}]},options:{responsive:true,plugins:{legend:{display:false}},scales:{x:{grid:{color:grid}},y:{grid:{color:grid},beginAtZero:true}}}});
  if(archOutcomeChart)archOutcomeChart.destroy();
  const oc=a.outcomes;
  archOutcomeChart=new Chart(document.getElementById('archOutcomeChart'),{type:'doughnut',data:{labels:Object.keys(oc),datasets:[{data:Object.values(oc),backgroundColor:[bright,blue,amber,'#666']}]},options:{responsive:true,plugins:{legend:{position:'right'}}}});
}

document.querySelectorAll('#toggle button').forEach(b=>{
  b.onclick=()=>{ document.querySelectorAll('#toggle button').forEach(x=>x.classList.remove('on')); b.classList.add('on'); state.view=b.dataset.v;
    try{ render(); }catch(e){ console.error('render failed: scorecard',e); } };
});

function onQuarterChange(){ applyView(); }
function applyView(){
  const q=document.getElementById('quarter').value;
  const live=(q==='Q3-2026');
  const key=(live?'live':'arch')+(state.tab==='momentum'?'Momentum':'Board');
  ['liveMomentum','liveBoard','archMomentum','archBoard'].forEach(id=>{
    document.getElementById(id).style.display = (id===key)?'block':'none';
  });
  const label = live ? 'Q3 2026 <b>live</b> . 1 Jul - 30 Sep'
    : (archives[q]? archives[q].label.replace(' . ',' . <b>')+'</b>' : q.replace('-',' '));
  const tabName = state.tab==='momentum' ? 'Momentum' : 'Leaderboard &amp; bonus';
  document.getElementById('ctxTitle').innerHTML=tabName+' &nbsp;.&nbsp; '+label;
  // A chart drawn inside a hidden tab renders at zero height, so every chart in the
  // now-visible container is (re)built here rather than once at load.
  const steps = live
    ? (state.tab==='momentum'
        ? [['banner',renderBanner],['revenue',renderRevenue],['acquisition',buildAcq],
           ['scorecard',render],['trend',buildTrend],['coverage',renderCoverage],['read',renderRead]]
        : [['leaderboard',renderLeaderboard],['bonus',()=>renderChannels(closedWonDeals,'bonus')]])
    : [['archive',()=>renderArchive(q)]];
  steps.forEach(([name,fn])=>{ try{ fn(); }catch(e){ console.error('render failed: '+name,e); } });
}
document.querySelectorAll('#tabs button').forEach(b=>{
  b.onclick=()=>{ document.querySelectorAll('#tabs button').forEach(x=>x.classList.remove('on'));
    b.classList.add('on'); state.tab=b.dataset.t; applyView(); };
});

if(!CHART_OK){ try{ document.getElementById('chartWarn').style.display='block'; }catch(e){} }
[['connectivity',renderConn]].forEach(([name,fn])=>{ try{ fn(); }catch(e){ console.error('render failed: '+name,e); } });
try{ applyView(); }catch(e){ console.error('applyView failed',e); }
</script>
</body>
</html>
'''

# ---- trend axis: quarter to date ----
import datetime
d1=datetime.date(2026,7,1); d2=datetime.date(2026,7,27)
days=[]; labels=[]
MON=["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"]
cur=d1
while cur<=d2:
    days.append(str(cur)); labels.append(f"{cur.day} {MON[cur.month-1]}")
    cur+=datetime.timedelta(days=1)

cov=dict(p["coverage"])
st=json.load(open(f"{SP}/build/dashboard_state.json"))
mc=st["meeting_classification"]
_gran=json.load(open(f"{SP}/raw/granola.json"))
cov.update({"mtg_included":mc["included_count"],"mtg_excluded":mc["excluded_count"],
            "mtg_internal":mc["internal_only_count"],
            "mtg_total":mc["included_count"]+mc["excluded_count"]+mc["internal_only_count"],
            "mtg_notes":len(_gran)})
# Stated limits for the Claude payload, built from this run's coverage rather than
# hardcoded, so the export never claims a gap the routine has since closed.
cov["known_gaps"]=[
    f"Calls began 21 Jul and completed cadence tasks 22 Jul, so month and quarter figures "
    f"match the week for those two metrics. Source: {cov['calls_source']}.",
    f"Email coverage starts {cov['email_covered_from']}: {cov['email_note']}.",
    cov["email_rupert"].capitalize() + ".",
    f"LinkedIn connections are not attributable per seat from Attio. {cov['li_connect_gap']}.",
    f"LinkedIn note coverage starts {cov['linkedin_notes_covered_from']}.",
    f"Progressed and shut off are {cov['progressed_shutoff']}, so nothing before the "
    f"routine existed is backfilled.",
    "Rupert has no Allo account, so his calls are always 0.",
]

# ---------------- Read & actions ----------------
# Every figure and every name in this narrative is computed from the payload at
# render time. Prose that asserts a number is data wearing markup's clothes: write
# one in by hand and it still reads as authoritative the morning after it goes
# stale. Nothing below may be hardcoded except the wording that joins the facts.
REPS = ["Chris", "Luke", "James", "Bianca", "Elliott", "Rupert"]
OUTBOUND_SEATS = ["Chris", "Luke", "Elliott"]      # roles carrying outbound; see spec
_QA, _QB = p["ranges"]["quarter"]
_TA, _TB = p["ranges"]["trailing7"]


def _sum(metric, a=_QA, b=_QB):
    """Per-person totals for a metric over a date range. Nothing else counts."""
    tot = [0] * 6
    for d, row in (p["daily"].get(metric) or {}).items():
        if a <= d <= b:
            for i in range(6):
                tot[i] += row[i]
    return tot


def _money(v):
    return "\u00a3" + format(int(round(v)), ",")


def _plural(n, one, many=None):
    return one if n == 1 else (many or one + "s")


def _join(items):
    items = [x for x in items if x]
    if not items:
        return ""
    if len(items) == 1:
        return items[0]
    return ", ".join(items[:-1]) + " and " + items[-1]


def _top(vals, n=3):
    """Top n people on a per-person vector, zeroes dropped, ties in scorecard order."""
    order = sorted(range(6), key=lambda i: (-vals[i], i))
    return [(REPS[i], vals[i]) for i in order if vals[i]][:n]


_mtg = _sum("meetings")
_tasks = _sum("tasks")
_deals = _sum("deals")
_lisent = _sum("liConnAll")
_target = p["QUARTER_TARGET"]
_won_q3 = sum(d["arr"] for d in p["closedWonDeals"])
_oc_total = sum(d["arr"] for d in p["contractDeals"])
_gap = max(0.0, _target - _won_q3 - _oc_total)
_pct = (_won_q3 / _target * 100) if _target else 0.0
_credits = sum(_mtg)

_won_by, _oc_by = {}, {}
for _d in p["closedWonDeals"]:
    _won_by[_d["owner"]] = _won_by.get(_d["owner"], 0) + _d["arr"]
for _d in p["contractDeals"]:
    _oc_by[_d["owner"]] = _oc_by.get(_d["owner"], 0) + _d["arr"]

_nwon, _noc = len(p["closedWonDeals"]), len(p["contractDeals"])
_won_owners = _join(sorted({d["owner"] for d in p["closedWonDeals"] if d["owner"]}))

# --- overall read: a conclusion, then the figures that support it ---
if _nwon and _noc:
    _lead = ("Q3 rests on %d small %s and %d %s that have not landed."
             % (_nwon, _plural(_nwon, "close"), _noc, _plural(_noc, "contract")))
elif _noc:
    _lead = "Nothing has closed in Q3 yet; the quarter sits entirely in %d %s." % (_noc, _plural(_noc, "contract"))
elif _nwon:
    _lead = "Q3 rests on %d %s with nothing behind it out for contract." % (_nwon, _plural(_nwon, "close"))
else:
    _lead = "Q3 has neither a close nor a contract out yet."

_ov = ["<strong>%s</strong> %s is won, %.1f%% of the %s target"
       % (_lead, _money(_won_q3), _pct, _money(_target))]
_ov.append((", all of it %s. " % _won_owners) if _won_owners else ". ")
if _noc:
    _ov.append("%s sits in Contracts, which still leaves %s to find if all %s sign. "
               % (_money(_oc_total), _money(_gap),
                  {1: "one", 2: "two", 3: "three"}.get(_noc, str(_noc))))
_ov.append("Sales meetings are where the quarter is being worked: %d external %s counted this quarter, "
           "%d attendee-%s across the six. "
           % (cov["mtg_included"], _plural(cov["mtg_included"], "meeting"),
              _credits, _plural(_credits, "credit")))
if _top(_mtg):
    _ov.append("%s. " % _join(["%s carries %d" % (n, v) for n, v in _top(_mtg)]))
if _won_by:
    _bigwin = max(_won_by, key=lambda k: _won_by[k])
    _ov.append("%s converts what he touches: %s of the Q3 book"
               % (_bigwin, _money(_won_by[_bigwin])))
    if _oc_by.get(_bigwin):
        _ov.append(", plus %s of the %s out for contract" % (_money(_oc_by[_bigwin]), _money(_oc_total)))
    _ov.append(", on %d meeting %s." % (_mtg[REPS.index(_bigwin)],
                                        _plural(_mtg[REPS.index(_bigwin)], "credit")))
READ_OVERALL = J("".join(_ov))

# --- the itemised read ---
_li = []

_aged = [d for d in p["contractDeals"] if d.get("passed")]
if _aged:
    _v = sum(d["arr"] for d in _aged)
    _rd = _dt.date(*[int(x) for x in p["RUN_DATE"].split("-")])
    _days = max((_rd - _dt.date(*[int(x) for x in d["est_iso"].split("-")])).days for d in _aged)
    _share = (", %.0f%% of the contract book" % (_v / _oc_total * 100)) if _oc_total else ""
    _li.append('<li><span class="pill red">Flag</span> %s %s the estimated close and %s still in Contracts, '
               'up to %d %s past. That is %s%s, with no stage movement logged. Owned by %s.</li>'
               % (_join(["<strong>%s %s</strong>" % (d["name"], _money(d["arr"])) for d in _aged]),
                  _plural(len(_aged), "passed", "passed"), _plural(len(_aged), "is", "are"),
                  _days, _plural(_days, "day"), _money(_v), _share,
                  _join(sorted({d["owner"] for d in _aged}))))

_moves = [m for m in p["stageMoves"] if m["date"] == p["RUN_DATE"]]
if _moves:
    _li.append('<li><span class="pill green">Measured move</span> %d %s changed stage today, each seen by the '
               'stage diff rather than inferred: %s.</li>'
               % (len(_moves), _plural(len(_moves), "deal"),
                  _join(["<strong>%s</strong> (%s) %s to %s" % (m["name"], m["owner"], m["from"], m["to"])
                         for m in _moves])))
else:
    _li.append('<li><span class="pill grey">Measured move</span> No stage change was recorded today. '
               'Progressed and shut off read 0 because nothing moved, not because nothing was measured.</li>')

if _top(_tasks, 1):
    _n, _v = _top(_tasks, 1)[0]
    _i = REPS.index(_n)
    _li.append('<li><span class="pill green">Working it</span> <strong>%s</strong> leads on completed tasks: '
               '%d this quarter, %d LinkedIn %s sent, %d %s created.</li>'
               % (_n, _v, _lisent[_i], _plural(_lisent[_i], "request"),
                  _deals[_i], _plural(_deals[_i], "deal")))

# Attendance-aware caution. This states the working days behind a quiet row and
# never converts a short week into a judgement about the person.
_short = [r for r in OUTBOUND_SEATS if p["attendance"][r]["trailing7"] < 4]
for _r in _short:
    _i = REPS.index(_r)
    _days7 = p["attendance"][_r]["trailing7"]
    _li.append('<li><span class="pill amber">Read with care</span> <strong>%s</strong> shows %d sales meeting %s '
               'this quarter, but the last seven days hold only %d working %s for %s after booked leave. '
               'That row is short because of the leave, not despite it, and it carries no performance read.</li>'
               % (_r, _mtg[_i], _plural(_mtg[_i], "credit"), _days7, _plural(_days7, "day"), _r))

if _top(_mtg, 3):
    _li.append('<li><span class="pill amber">Heavy load</span> Meeting time is concentrated: %s. '
               'Worth asking which of that a rep could carry.</li>'
               % _join(["<strong>%s</strong> on %d" % (n, v) for n, v in _top(_mtg, 3)]))

_year = {}
for _d in p["wonYTD"]:
    _e = _year.setdefault(_d["owner"], {"v": 0.0, "n": 0})
    _e["v"] += _d["arr"]
    _e["n"] += 1
if _year:
    _ranked = sorted(_year.items(), key=lambda kv: -kv[1]["v"])
    _li.append('<li><span class="pill green">Year view</span> The 2026 leaderboard reads differently from the '
               'quarter: %s. %d %s won across the year, spread across %d %s.</li>'
               % (_join(["%s %s" % (k, _money(v["v"])) for k, v in _ranked]),
                  len(p["wonYTD"]), _plural(len(p["wonYTD"]), "deal"),
                  len(_year), _plural(len(_year), "person", "people")))

_BONUS = [(100000, 1000), (75000, 750), (50000, 500), (25000, 250),
          (15000, 200), (10000, 150), (5000, 100), (0, 50)]
_qual = [d for d in p["closedWonDeals"] if d["channel"] == "Outbound - Direct"]
_unassigned = [d for d in p["closedWonDeals"] if d["channel"] == "Unassigned"]
_earned = sum(next(pay for lo, pay in _BONUS if d["arr"] >= lo) for d in _qual)
_bonus = ("%d Q3 %s %s on channel Outbound - Direct, so the earned total is %s."
          % (len(_qual), _plural(len(_qual), "close"), _plural(len(_qual), "qualifies", "qualify"),
             _money(_earned))
          if _qual else
          "Nothing qualifies for the direct outbound bonus in Q3. %s, so the earned total is %s."
          % (("Every close is on another channel: "
              + _join(sorted({d["channel"] for d in p["closedWonDeals"]}))) if p["closedWonDeals"]
             else "No deal has closed won this quarter", _money(0)))
if _unassigned:
    _bonus += (" Do not pay yet on %s: %s with no channel set, owned by %s."
               % (_join(["<strong>%s %s</strong>" % (d["name"], _money(d["arr"])) for d in _unassigned]),
                  _money(sum(d["arr"] for d in _unassigned)),
                  _join(sorted({d["owner"] for d in _unassigned}))))
else:
    _bonus += " No deal is pending a channel."
_li.append('<li><span class="pill grey">Bonus</span> %s</li>' % _bonus)

READ_LIST = J("".join(_li))

out=HEAD
subs={
 "__QT__":str(p["QUARTER_TARGET"]),
 "__RUN_STAMP__":J(p["RUN_STAMP"]),
 "__RUN_DATE__":J(p["RUN_DATE"]),
 "__STAGEMOVES__":J(p["stageMoves"]),
 "__WONBOOK__":str(p["wonBookCount"]),
 "__DEALCOUNT__":str(len(st["stage_snapshot"])),
 "__COVERAGE__":J(cov),
 "__DAILY__":J(p["daily"]),
 "__CWDEALS__":J(p["closedWonDeals"]),
 "__OCDEALS__":J(p["contractDeals"]),
 "__WONYTD__":J(p["wonYTD"]),
 "__CONN__":J(p["connectivity"]),
 "__OFFTODAY__":J(p["offToday"]),
 "__ATTENDANCE__":J(p["attendance"]),
 "__RANGES__":J(p["ranges"]),
 "__RANGETEXT__":J(p["rangeText"]),
 "__ACQ__":J(p["acqChannels"]),
 "__ARCHIVES__":J(p["archives"]),
 "__TREND_DAYS__":J(days),
 "__TREND_LABELS__":J(labels),
 "__READ_OVERALL__":READ_OVERALL,
 "__READ_LIST__":READ_LIST,
}
for k,v in subs.items(): out=out.replace(k,v)
assert "__" not in out.replace("__proto__",""), [l for l in out.split("\n") if "__" in l][:3]
open(f"{SP}/build/index-18.html","w",encoding="utf-8").write(out)
print("written bytes:",len(out.encode()))
