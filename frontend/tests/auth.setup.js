import { test as setup, expect } from '@playwright/test';

// One-time authentication for the golden regression suite. Credentials must
// be supplied by the runner; never commit or silently use a reusable account.
const EMAIL = process.env.E2E_EMAIL;
const PASSWORD = process.env.E2E_PASSWORD;
if (!EMAIL || !PASSWORD) {
  throw new Error('E2E_EMAIL and E2E_PASSWORD must be provided to run Playwright tests.');
}
const AUTH_FILE = 'playwright/.auth/user.json';

setup('authenticate test account', async ({ page }) => {
  await page.goto('/auth');

  await expect(page.getByPlaceholder('Email Address')).toBeVisible();
  await page.getByPlaceholder('Email Address').fill(EMAIL);
  await page.getByPlaceholder('Password').fill(PASSWORD);
  await page.getByRole('button', { name: 'Login', exact: true }).click();

  // Successful login redirects to the dashboard.
  await page.waitForURL('**/dashboard**', { timeout: 20_000 });
  await expect(page).toHaveURL(/\/dashboard/);

  await page.context().storageState({ path: AUTH_FILE });
});
