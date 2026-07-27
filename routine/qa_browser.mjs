// Load the built page in a real browser and assert the DATA renders.
//
// This exists because the static QA passed on a page that came out completely
// blank. qa.py checked that every render call sat in its own try/catch, which was
// true and useless: the script died on an unguarded `Chart.defaults` reference at
// the top, before a single render function had been defined, so there was nothing
// for the try/catch to protect.
//
// The CDN is blocked deliberately on the first pass. That is the failure mode that
// reached the team - a print with no chart library - and the numbers must survive it.
//
// Usage: node qa_browser.mjs <path-to-index-18.html>
import { chromium } from 'playwright';

const file = process.argv[2];
if (!file) { console.error('usage: node qa_browser.mjs <index-18.html>'); process.exit(2); }

const EXPECT_ROWS = 7;            // six people plus the team totals row
const fails = [];

// A stand-in for Chart.js, so the "library present" branch can be exercised even
// where the real CDN is unreachable. It only has to be constructible and expose
// defaults and a version, which is all the page touches.
const CHART_STUB = `window.Chart=class{constructor(){}destroy(){}update(){}resize(){}};
Chart.version='stub';Chart.defaults={color:'',font:{family:'',size:12}};`;

async function run(blockCdn) {
  const browser = await chromium.launch({ executablePath: '/opt/pw-browsers/chromium' });
  const page = await browser.newPage();
  const pageErrors = [];
  page.on('pageerror', e => pageErrors.push(e.message));
  // The CDN is unreachable from some sandboxes, so "with-CDN" is simulated rather
  // than left to the network. Otherwise this check silently never runs.
  await page.route('**cdnjs.cloudflare.com**', r =>
    blockCdn ? r.abort() : r.fulfill({ status: 200, contentType: 'application/javascript', body: CHART_STUB }));
  await page.goto('file://' + file, { waitUntil: 'load' });
  await page.waitForTimeout(1500);

  const probe = await page.evaluate(() => {
    const txt = id => { const e = document.getElementById(id); return e ? (e.textContent || '').trim() : null; };
    const rows = [...document.querySelectorAll('#summaryBody tr')];
    return {
      summaryRows: rows.length,
      // A row of dashes or empty cells is "rendered" but carries no data.
      firstRowCells: rows.length ? [...rows[0].children].map(c => c.textContent.trim()) : [],
      teamRow: rows.length ? rows[rows.length - 1].textContent.replace(/\s+/g, ' ').trim() : '',
      lastRefresh: txt('lastRefresh'),
      moveNote: txt('moveNote'),
      emailFrom: txt('emailFrom'),
      // connectivity panel: whatever container renderConn fills
      connText: (document.querySelector('.conn') || {}).textContent?.replace(/\s+/g, ' ').trim() || '',
      chartWarnShown: (document.getElementById('chartWarn') || {}).style?.display === 'block',
      chartLoaded: typeof Chart !== 'undefined' && !!Chart.version,
      canvases: document.querySelectorAll('canvas').length,
    };
  });
  await browser.close();

  const tag = blockCdn ? 'no-CDN' : 'with-CDN';
  if (pageErrors.length) fails.push(`[${tag}] uncaught page error: ${pageErrors.join(' | ')}`);
  if (probe.summaryRows !== EXPECT_ROWS)
    fails.push(`[${tag}] scorecard has ${probe.summaryRows} rows, expected ${EXPECT_ROWS}`);
  if (!probe.firstRowCells.length || !probe.firstRowCells[0])
    fails.push(`[${tag}] scorecard first row is empty`);
  if (!/Team/.test(probe.teamRow)) fails.push(`[${tag}] team totals row missing`);
  if (!probe.lastRefresh) fails.push(`[${tag}] run stamp did not render`);
  if (!probe.emailFrom) fails.push(`[${tag}] coverage panel did not render`);
  if (!probe.moveNote) fails.push(`[${tag}] stage-move note did not render`);
  if (probe.connText.length < 40) fails.push(`[${tag}] connector panel looks empty`);
  if (blockCdn && !probe.chartWarnShown)
    fails.push(`[${tag}] charts absent but no notice shown, so a blank graph reads as zero data`);
  if (!blockCdn && probe.chartWarnShown)
    fails.push(`[${tag}] chart notice shown even though the library loaded`);

  console.log(`--- ${tag} ---`);
  console.log(`  rows=${probe.summaryRows} canvases=${probe.canvases} ` +
              `stamp=${JSON.stringify(probe.lastRefresh)} chartNotice=${probe.chartWarnShown}`);
  console.log(`  first row: ${probe.firstRowCells.slice(0, 6).join(' | ')}`);
  console.log(`  totals   : ${probe.teamRow.slice(0, 90)}`);
  console.log(`  connector: ${probe.connText.slice(0, 90)}`);
  return probe;
}

// Both passes matter. Without the library the numbers must still be there; with it
// the notice must stay hidden.
await run(true);
await run(false);

if (fails.length) {
  console.log('\nBROWSER QA FAILED');
  for (const f of fails) console.log('  -', f);
  process.exit(1);
}
console.log('\nBROWSER QA PASSED: the data renders with and without the chart library.');
