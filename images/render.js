// Render images/diagrams.html to the three PNGs beside it, at 2x.
// Needs playwright-core and a local Google Chrome:
//   npx -y -p playwright-core@1.47.2 node images/render.js
const { chromium } = require('playwright-core');
const path = require('path');
const FIGURES = {
  gateway: 'gateway-response-interceptor.png',
  filter: 'list-response-filter.png',
  contract: 'catalog-tags-to-policy.png',
};
(async () => {
  const b = await chromium.launch({ channel: 'chrome' });
  const p = await b.newPage({ viewport: { width: 1500, height: 900 }, deviceScaleFactor: 2 });
  const console_ = [];
  p.on('console', m => console_.push(m.text()));
  await p.goto('file://' + path.resolve(__dirname, 'diagrams.html'));
  await p.waitForTimeout(500);
  const warnings = await p.evaluate(() => window.__diagramWarnings || []);
  for (const [id, file] of Object.entries(FIGURES)) {
    await p.locator(`#${id}`).screenshot({ path: path.join(__dirname, file) });
    console.log('wrote', file);
  }
  await b.close();
  console.log('WARNINGS:', JSON.stringify(warnings, null, 1));
  const other = console_.filter(m => !m.startsWith('[diagram]'));
  if (other.length) console.log('CONSOLE:', other.join('\n'));
})().catch(e => { console.error('FAIL:', e.message); process.exit(1); });
