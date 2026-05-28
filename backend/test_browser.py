const PLAYWRIGHT = '/home/ubuntu/.hermes/hermes-agent/node_modules/playwright';
const { chromium } = require(PLAYWRIGHT);

const BASE = 'http://127.0.0.1:3002';
const API = 'http://127.0.0.1:8086';
const EMAIL = 'hermes_test@test.com';
const PASSWORD = 'Test123456';

(async () => {
  const browser = await chromium.launch({ headless: true, args: ['--no-sandbox'] });
  const ctx = await browser.newContext({ viewport: { width: 1920, height: 1080 } });
  const page = await ctx.newPage();

  const consoleErrors = [];
  page.on('console', msg => {
    if (msg.type() === 'error') consoleErrors.push({ url: page.url(), text: msg.text() });
  });
  page.on('pageerror', err => consoleErrors.push({ url: page.url(), text: err.message }));

  // 1. Register + Login to get token
  console.log('--- Step 1: Register + Login ---');
  const regRes = await fetch(`${API}/api/v1/auth/register`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', 'X-API-Key': 'hermes-secret-api-key-2025' },
    body: JSON.stringify({ email: EMAIL, username: EMAIL.split('@')[0], password: PASSWORD })
  });
  console.log(`Register: ${regRes.status}`);
  const loginRes = await fetch(`${API}/api/v1/auth/login`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
    body: `username=${EMAIL}&password=${PASSWORD}`
  });
  const loginData = await loginRes.json();
  const token = loginRes.headers.get('Set-Cookie') || '';
  console.log(`Login: ${loginRes.status}, token present: ${!!loginData.access_token}`);
  const bearer = loginData.access_token;

  // 2. Test all pages
  const pages = ['/', '/strategies', '/backtest', '/portfolio', '/risk', '/automation', '/compare', '/settings', '/export'];
  for (const p of pages) {
    console.log(`\n--- Page: ${p} ---`);
    const res = await page.goto(`${BASE}${p}`, { waitUntil: 'networkidle', timeout: 20000 });
    await page.waitForTimeout(2000);
    console.log(`HTTP ${res.status()}, URL ${page.url()}`);

    // Check for visible errors in DOM
    const bodyText = await page.textContent('body');
    if (bodyText.includes('Error') || bodyText.includes('error') || bodyText.includes('undefined') || bodyText.includes('null')) {
      console.log('  ⚠ Contains error keywords in body');
    }
  }

  // 3. Test automation flow: find "Run History" and click it
  console.log('\n--- Step 3: Automation Run History ---');
  await page.goto(`${BASE}/automation`, { waitUntil: 'networkidle', timeout: 20000 });
  await page.waitForTimeout(2000);

  // Look for run history button or link
  const historyLink = await page.$('text=Run History');
  if (historyLink) {
    console.log('Found Run History, clicking...');
    await historyLink.click();
    await page.waitForTimeout(3000);
    console.log(`After click: URL=${page.url()}`);
    // Check if history loaded
    const content = await page.textContent('body');
    if (content.includes('NameError') || content.includes('Traceback')) {
      console.log('  ⚠ NameError or Traceback found in history page');
    }
  } else {
    console.log('Run History link not found on page');
  }

  // 4. Test dashboard toggle
  console.log('\n--- Step 4: Dashboard Mode Toggle ---');
  await page.goto(`${BASE}/`, { waitUntil: 'networkidle', timeout: 20000 });
  await page.waitForTimeout(3000);
  const liveBtn = await page.$('text=Live / Demo');
  if (liveBtn) {
    console.log('Found Live/Demo toggle');
    await liveBtn.click();
    await page.waitForTimeout(2000);
    console.log('Live mode activated OK');
  } else {
    console.log('Live/Demo toggle not found');
  }

  // 5. Console errors summary
  console.log('\n--- Console Errors ---');
  if (consoleErrors.length === 0) {
    console.log('No console errors detected');
  } else {
    consoleErrors.forEach(e => console.log(`ERROR [${e.url}]: ${e.text.substring(0, 200)}`));
  }

  await browser.close();
  console.log('\nDone.');
})();
