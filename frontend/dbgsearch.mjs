import { chromium } from 'playwright';

const ROOT = '/home/alsuni/Alsini-physics-platform';
const LIBS = '/tmp/chromelibs/usr/lib/x86_64-linux-gnu';
const EXEC = '/home/alsuni/.cache/ms-playwright/chromium-1217/chrome-linux64/chrome';
const UNIT = '2cf312d3-0f4b-4339-84f3-97b10b2907ea';
const CHAPTER = 'b95f8fac-355e-4037-bc1f-2d3b2bf77140';
const DASH = `/dashboard/unit/${UNIT}/chapter/${CHAPTER}`;

const browser = await chromium.launch({
  executablePath: EXEC,
  args: ['--no-sandbox', '--disable-dev-shm-usage', '--disable-gpu', '--disable-software-rasterizer', '--disable-background-mode'],
  env: { ...process.env, LD_LIBRARY_PATH: LIBS },
});
const ctx = await browser.newContext({ storageState: `${ROOT}/frontend/playwright/.auth/user.json`, baseURL: 'http://localhost:5173' });
const page = await ctx.newPage();

page.on('request', (r) => {
  if (r.url().includes('/api/search/hybrid')) {
    try { console.log('SEARCH REQ', JSON.stringify(r.postDataJSON())); } catch {}
  }
});
page.on('response', (r) => {
  if (r.url().includes('/api/search/hybrid')) {
    console.log('SEARCH RESP', r.status());
  }
});

await page.goto('/dashboard');
await page.getByRole('button', { name: 'Sign Out' }).waitFor({ state: 'visible', timeout: 20_000 });
await page.goto(DASH);
const wt = page.getByRole('button', { name: 'Worksheet', exact: true });
await wt.waitFor({ state: 'visible', timeout: 20_000 });
await wt.click();
await page.locator('iframe[title="Original worksheet PDF"]').waitFor({ state: 'visible', timeout: 20_000 });
console.log('WORKSHEET OPEN');

// Find the Search button
const searchBtn = page.getByRole('button', { name: 'Search', exact: true });
console.log('search btn visible?', await searchBtn.isVisible().catch(() => false));
await searchBtn.click();
await page.waitForTimeout(1000);

const input = page.getByPlaceholder('Search concepts, formulas...');
console.log('input visible?', await input.isVisible().catch(() => false));
await input.fill('velocity');
await page.keyboard.press('Enter');
await page.waitForTimeout(5000);
console.log('FINAL URL', page.url());

// count result buttons with %
const btns = await page.locator('button', { hasText: /%/ }).count();
console.log('result buttons with %:', btns);

await browser.close();
console.log('DONE');
