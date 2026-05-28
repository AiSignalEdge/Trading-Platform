const PLAYWRIGHT = '/home/ubuntu/.hermes/hermes-agent/node_modules/playwright';
const { chromium } = require(PLAYWRIGHT);

const BASE = 'http://127.0.0.1:3002';
const API = 'http://127.0.0.1:8086';
const EMAIL = 'hermes_test@test.com';
const PASSWORD = 'Test123456';

(async () => {
  const browser = await chromium.launch({ headless: true, args: ['--no-sandbox', '--disable-dev-shm-usage'] });
  const ctx = await browser.newContext({ viewport: { width: 1920, height: 1080 } });
  const page = await ctx.newPage();

  const consoleErrors = [];
  page.on('console', msg => {
    if (msg.type() === 'error') consoleErrors.push({ url: page.url(), text: msg.text() });
  });
  page.on('pageerror', err => consoleErrors.push({ url: page.url(), text: err.message }));

  // 1. Register
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

  // 2. Test all pages
  console.log('\n--- Step 2: All Pages ---');
  const pages = ['/', '/strategies', '/backtest', '/portfolio', '/risk', '/automation', '/compare', '/settings', '/export'];
  for (const p of pages) {
    const res = await page.goto(`${BASE}${p}`, { waitUntil: 'domcontentloaded', timeout: 20000 });
    await page.waitForTimeout(2000);
    const status = res ? res.status() : 'no-response';
    const errors = consoleErrors.filter(e => e.url.includes(p));
    console.log(`${status}  ${p}${errors.length ? '  ⚠ ERRORS' : '  OK'}`);
  }

  // 3. Test Run History click
  console.log('\n--- Step 3: Automation Run History ---');
  await page.goto(`${BASE}/automation`, { waitUntil: 'domcontentloaded', timeout: 20000 });
  await page.waitForTimeout(3000);

  const runHistoryBtn = page.locator('text=Run History').first();
  const hasRunHistory = await runHistoryBtn.count() > 0;
  if (hasRunHistory) {
    console.log('Found Run History button, clicking...');
    await runHistoryBtn.click();
    await page.waitForTimeout(4000);
    const content = await page.textContent('body');
    if (content.includes('NameError') || content.includes('Traceback')) {
      console.log('  ⚠ NameError/Traceback in Run History page!');
      const lines = content.split('\n').filter(l => l.includes('NameError') || l.includes('Traceback') || l.includes('Error'));
      lines.slice(0, 5).forEach(l => console.log('   ' + l.trim()));
    } else {
      console.log('  Run History loaded OK');
    }
  } else {
    console.log('Run History button not found');
  }

  // 4. Dashboard mode toggle
  console.log('\n--- Step 4: Dashboard Mode Toggle ---');
  await page.goto(`${BASE}/`, { waitUntil: 'domcontentloaded', timeout: 20000 });
  await page.waitForTimeout(3000);
  const liveBtn = page.locator('text=Live / Demo').first();
  if (await liveBtn.count() > 0) {
    await liveBtn.click();
    await page.waitForTimeout(2000);
    const content = await page.textContent('body');
    const hasError = content.includes('NameError') || content.includes('undefined') || content.includes('is not defined');
    console.log(`  Live mode click: ${hasError ? '⚠ errors' : 'OK'}`);
  } else {
    console.log('  Live/Demo toggle not found');
  }

  // 5. Error summary
  if (consoleErrors.length > 0) {
    console.log('\n--- All Console Errors ---');
    consoleErrors.forEach(e => console.log(`[${e.url}] ${e.text.substring(0, 300)}`));
  } else {
    console.log('\nNo console errors detected');
  }

  await browser.close();
  console.log('\nDone.');
  process.exit(0);
})();
