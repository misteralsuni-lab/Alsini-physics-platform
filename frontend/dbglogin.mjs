import { chromium } from 'playwright';

const ROOT = '/home/alsuni/Alsini-physics-platform';
const LIBS = '/tmp/chromelibs/usr/lib/x86_64-linux-gnu';
const EXEC = '/home/alsuni/.cache/ms-playwright/chromium-1217/chrome-linux64/chrome';
const EMAIL = process.env.E2E_EMAIL;
const PASSWORD = process.env.E2E_PASSWORD;
if (!EMAIL || !PASSWORD) {
  throw new Error('E2E_EMAIL and E2E_PASSWORD must be provided.');
}

const browser = await chromium.launch({
  executablePath: EXEC,
  args: ['--no-sandbox', '--disable-dev-shm-usage', '--disable-gpu', '--disable-software-rasterizer', '--disable-background-mode'],
  env: { ...process.env, LD_LIBRARY_PATH: LIBS },
});

const ctx = await browser.newContext({ storageState: `${ROOT}/frontend/playwright/.auth/user.json`, baseURL: 'http://localhost:5173' });
const page = await ctx.newPage();

page.on('response', async (r) => {
  if (r.url().includes('/auth/v1/token')) {
    const body = await r.text().catch(() => '');
    console.log('TOKEN', r.status(), 'grant=', (r.url().match(/grant_type=([^&]+)/) || [])[1], 'body=', body.slice(0, 120));
  }
});

await page.goto('/');
await page.evaluate(() => localStorage.clear());
await page.goto('/auth');
await page.getByPlaceholder('Email Address').waitFor({ state: 'visible', timeout: 20_000 });
await page.getByPlaceholder('Email Address').fill(EMAIL);
await page.getByPlaceholder('Password').fill(PASSWORD);
await page.getByRole('button', { name: 'Login', exact: true }).click();
await page.waitForTimeout(6000);
console.log('FINAL URL', page.url());
const err = await page.getByText(/Invalid login credentials/i).isVisible().catch(() => false);
console.log('invalid creds?', err);

await browser.close();
console.log('DONE');
