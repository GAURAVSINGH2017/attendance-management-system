const fs = require('fs');
const path = require('path');
const { chromium } = require('playwright');

const dir = path.join(__dirname, 'screens');
const edge = 'C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe';
(async () => {
  const browser = await chromium.launch({ headless: true, executablePath: edge });
  const page = await browser.newPage({ viewport: { width: 1366, height: 900 }, deviceScaleFactor: 1 });
  for (const name of fs.readdirSync(dir).filter(name => name.endsWith('.html')).sort()) {
    const html = fs.readFileSync(path.join(dir, name), 'utf8');
    await page.setContent(html, { waitUntil: 'domcontentloaded' });
    await page.screenshot({ path: path.join(dir, name.replace(/\.html$/, '.png')), fullPage: true });
  }
  await browser.close();
  console.log('Captured illustrative UI screenshots.');
})().catch(error => { console.error(error); process.exit(1); });
