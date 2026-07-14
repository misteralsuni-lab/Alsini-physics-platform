import { test as setup, expect } from '@playwright/test';

// One-time authentication for the golden regression suite.
// Credentials resolve from env vars (CI) and fall back to the dedicated
// E2E test account that is provisioned in the Supabase project.
const EMAIL = process.env.E2E_EMAIL || 'e2e_test@alsini.dev';
const PASSWORD = process.env.E2E_PASSWORD || 'E2Etest1234!';
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
