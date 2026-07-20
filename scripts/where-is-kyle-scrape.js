#!/usr/bin/env node
// where-is-kyle-scrape.js — fetch Kyle's most recent Strava activity + location.
//
// Reads the tracking account's session cookie (env STRAVA_SESSION_COOKIE, or the
// vault), renders Kyle's profile to find his latest activity (others' activity
// lists only render client-side), then pulls that activity's detail page for the
// start location and coordinates. Emits JSON.
//
// Usage:
//   STRAVA_SESSION_COOKIE=… node where-is-kyle-scrape.js [--athlete 1709737] [--out path.json]
//
// Exit: 0 ok, 2 no cookie, 1 error/no activity.
const fs = require('fs');
const { execSync } = require('child_process');
const { chromium } = require(require('path').join(process.env.HOME, 'goprojects/test-agent/node_modules/playwright'));

const arg = (k, d) => { const i = process.argv.indexOf(k); return i > -1 ? process.argv[i + 1] : d; };
const ATHLETE = arg('--athlete', '1709737');
const OUT = arg('--out', null);
const UA = 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36';

function cookie() {
  if (process.env.STRAVA_SESSION_COOKIE) return process.env.STRAVA_SESSION_COOKIE.trim();
  try {
    return execSync(`${process.env.HOME}/goprojects/infrastructure/vault.sh get STRAVA_SESSION_COOKIE`,
      { encoding: 'utf8' }).trim();
  } catch { return null; }
}

(async () => {
  const sess = cookie();
  if (!sess) { console.error('no STRAVA_SESSION_COOKIE (env or vault)'); process.exit(2); }

  const browser = await chromium.launch({ headless: true });
  const ctx = await browser.newContext({ userAgent: UA, viewport: { width: 1280, height: 1200 } });
  await ctx.addCookies([{ name: '_strava4_session', value: sess, domain: '.strava.com', path: '/', httpOnly: true, secure: true, sameSite: 'Lax' }]);
  const page = await ctx.newPage();

  // Render the profile; his recent activities only appear after JS runs.
  await page.goto(`https://www.strava.com/athletes/${ATHLETE}`, { waitUntil: 'networkidle', timeout: 25000 }).catch(() => {});
  await page.waitForTimeout(2000);

  if (/\/login/.test(page.url())) { console.error('session expired — re-grab cookie (skill: grab-cookie)'); await browser.close(); process.exit(1); }

  // Latest activity = first non-"best-efforts" activity link in DOM order (newest first).
  const latestId = await page.locator('a[href*="/activities/"]').evaluateAll(els => {
    for (const e of els) {
      const m = (e.getAttribute('href') || '').match(/\/activities\/(\d+)(?:$|[/?#])/);
      if (m && !/best-efforts|segments|laps/.test(e.getAttribute('href'))) return m[1];
    }
    return null;
  });

  const athleteName = (await page.locator('h1').first().innerText().catch(() => '') || '').trim();

  if (!latestId) {
    const out = { athlete_id: ATHLETE, athlete_name: athleteName, latest: null, note: 'no visible activities', scraped_at_iso: null };
    emit(out); await browser.close(); return;
  }

  // Pull the activity detail page (curl-equivalent via the same authed context).
  const detail = await page.goto(`https://www.strava.com/activities/${latestId}`, { waitUntil: 'domcontentloaded', timeout: 20000 }).then(r => r.text());

  const grab = (re) => { const m = detail.match(re); return m ? m[1].trim() : null; };
  const title = grab(/<title>([^<]*)<\/title>/);
  const date = grab(/<time[^>]*>([^<]+)<\/time>/);
  // Location words + first coordinate pair (start point).
  const loc = (grab(/"city"\s*:\s*"([^"]*)"/) || '') ;
  const coordsAll = [...detail.matchAll(/\[(-?\d{1,3}\.\d{3,}),\s*(-?\d{1,3}\.\d{3,})\]/g)].map(m => [parseFloat(m[1]), parseFloat(m[2])]);
  const start = coordsAll[0] || null;
  // Human location often in og/desc or a "location" line; fall back to title region text.
  const region = grab(/<div class="location"[^>]*>\s*([^<]+)</) || locFromText(detail);

  const out = {
    athlete_id: ATHLETE,
    athlete_name: athleteName,
    latest: {
      id: latestId,
      url: `https://www.strava.com/activities/${latestId}`,
      name: cleanTitle(title),
      type: typeFromTitle(title),
      date_text: date,
      location_text: region,
      start_lat: start ? start[0] : null,
      start_lng: start ? start[1] : null,
    },
    scraped_at_iso: null, // stamped by caller (Date unavailable in some harnesses)
  };
  emit(out);
  await browser.close();

  function emit(o) {
    const json = JSON.stringify(o, null, 2);
    if (OUT) { fs.writeFileSync(OUT, json); console.error(`wrote ${OUT}`); }
    console.log(json);
  }
})().catch(e => { console.error('ERR', e); process.exit(1); });

function cleanTitle(t) { return t ? t.replace(/\s*\|\s*Strava.*$/, '').replace(/\s*\|\s*(Ride|Run|Walk|Hike)\s*$/, '').trim() : null; }
function typeFromTitle(t) { const m = t && t.match(/\|\s*(Ride|Run|Walk|Hike|Swim|Workout|Gravel Ride|Mountain Bike Ride|Virtual Ride)\s*\|/); return m ? m[1] : null; }
function locFromText(html) {
  // crude: a "City, ST, Country" or "City, Country" near the map
  const m = html.match(/>([A-Z][a-zA-Z.\- ]+,\s*[A-Z][a-zA-Z.\- ]+(?:,\s*[A-Za-z.\- ]+)?)<\/(?:span|div|a)>/);
  return m ? m[1].trim() : null;
}
