#!/usr/bin/env node
/*
 Loads a .script file with the REAL Genesys Cloud script editor code (the public scripter
 web-app bundles from apps.mypurecloud.com) in headless Chromium and builds the script,
 page, variable and custom-action models exactly like "open script" does in the UI.
 If the editor would show "Failed to load script", this prints the underlying error.

 Usage:  node validate-in-editor.js path/to/file.script [on|off]
         (on|off = value used for every scripter feature toggle; default off)
 Needs:  node >= 18, playwright (npm i playwright) and its chromium, and outbound HTTPS
         to apps.mypurecloud.com (bundles are downloaded once into ./cache).
 Nothing is sent to Genesys except GET requests for the public JS bundles.
*/
const { chromium } = require('playwright');
const fs = require('fs'); const path = require('path');
const HOST = 'apps.mypurecloud.com';
const CACHE = path.join(__dirname, 'cache');
const TOGGLES = ["CC-5915_Sort-Order-Fix","scripter.cacheHawkReconnectData","scripterDataActionDefaultValues","scripterVerboseConsoleLogs","scripterCreateEmail","scripter.deferUpdates","scripter.upgradeMathJS","PURE-6796_Script_A11y","PURE-6965_Scripter_GUXv4_Migration","PURE-7016_scripter-schema-variables","PURE-7728_scriptingExperienceEnhancements","WEM-118_snippet-recording","PURE-6726"];

function fetchText(urlPath) {
  // curl honours HTTPS_PROXY / corporate CA settings; Node's https client does not.
  const { execFileSync } = require('child_process');
  return Promise.resolve(execFileSync('curl', ['-sS', '-L', '--fail', '-m', '180', 'https://' + HOST + urlPath], { maxBuffer: 64 * 1024 * 1024 }));
}
async function cached(urlPath) {
  const local = path.join(CACHE, (urlPath.endsWith('/') ? urlPath + 'index.html' : urlPath).replace(/^\//, ''));
  if (fs.existsSync(local)) return fs.readFileSync(local);
  const body = await fetchText(urlPath);
  fs.mkdirSync(path.dirname(local), { recursive: true }); fs.writeFileSync(local, body); return body;
}

(async () => {
  const file = process.argv[2]; const toggles = (process.argv[3] || 'off') === 'on';
  if (!file) { console.error('usage: node validate-in-editor.js file.script [on|off]'); process.exit(2); }
  const scriptJson = fs.readFileSync(file, 'utf8'); JSON.parse(scriptJson);
  const index = (await cached('/scripter/')).toString('utf8');
  const m = index.match(/\/scripter\/build-assets\/([^/"']+)\/bundle\.js/);
  if (!m) throw new Error('could not find build-assets path in /scripter/ index');
  const assets = '/scripter/build-assets/' + m[1] + '/';
  const harness = index.replace(/<script\b[^>]*>[\s\S]*?<\/script>/gi, '').replace(/<link[^>]*modulepreload[^>]*>/gi, '')
    .replace('</body>', `<script type="module">
window.__done=false; window.__result={};
window.__toggles={}; for (const n of ${JSON.stringify(TOGGLES)}) window.__toggles[n]=${toggles};
try {
  const app = await import('${assets}app.bundle.js'); await app.Y.loadLocale('en-US');
  const m = await import('${assets}scripterService.bundle.js');
  const script = await (await fetch('/__test__/script.json')).json();
  const out = {}; const t = (label, fn) => { try { fn(); out[label] = 'ok'; } catch (e) { out[label] = 'ERROR ' + (e && e.stack || e); } };
  t('script', () => m.z.create(script));
  for (const p of script.pages) t('page:' + p.name, () => m.P.create(p));
  for (const v of script.variables) t('variable:' + v.name, () => m.V.create(v));
  for (const a of script.customActions) t('customAction:' + a.name, () => (m.ab.fromJSON ? m.ab.fromJSON(a.action) : m.ab.create(a.action)));
  out.__componentTypes = Object.keys(m.J.types).join(', ');
  window.__result = out;
} catch (e) { window.__result = { bootstrap: 'ERROR ' + (e && e.stack || e) }; }
window.__done = true;</script></body>`);

  const browser = await chromium.launch(); const page = await browser.newPage();
  await page.route('**/*', async route => {
    const u = new URL(route.request().url()); const p = u.pathname;
    if (u.hostname !== HOST || p.startsWith('/api/') || p.startsWith('/uploads/')) return route.fulfill({ status: 200, contentType: 'application/json', body: '{}' });
    if (p === '/scripter/__harness__.html') return route.fulfill({ status: 200, contentType: 'text/html', body: harness });
    if (p === '/__test__/script.json') return route.fulfill({ status: 200, contentType: 'application/json', body: scriptJson });
    if (p.startsWith(assets)) {
      try {
        let body = await cached(p);
        if (p.endsWith('/app.bundle.js')) body = Buffer.from(body.toString('utf8').replace('let gv;const qR=', 'let gv=(window.__toggles||{});const qR='), 'utf8');
        return route.fulfill({ status: 200, contentType: p.endsWith('.css') ? 'text/css' : 'text/javascript', body });
      } catch (e) { return route.fulfill({ status: 404, body: '' }); }
    }
    return route.fulfill({ status: 404, body: '' });
  });
  await page.goto('https://' + HOST + '/scripter/__harness__.html');
  await page.waitForFunction(() => window.__done === true, null, { timeout: 180000 });
  const result = await page.evaluate(() => window.__result); await browser.close();
  let failed = 0;
  for (const [k, v] of Object.entries(result)) { if (k === '__componentTypes') continue; if (String(v).startsWith('ERROR')) failed++; console.log((String(v).startsWith('ERROR') ? 'FAIL ' : 'ok   ') + k + (String(v).startsWith('ERROR') ? '\n      ' + String(v).split('\n').slice(0, 3).join('\n      ') : '')); }
  console.log('editor component types: ' + result.__componentTypes);
  console.log(failed ? `\n${failed} item(s) would make the editor show "Failed to load script".` : '\nAll items build in the editor.');
  process.exit(failed ? 1 : 0);
})().catch(e => { console.error(e); process.exit(1); });
