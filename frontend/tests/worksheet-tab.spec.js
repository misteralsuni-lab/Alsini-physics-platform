import { test, expect } from '@playwright/test';

test.describe('VLE Dashboard - Worksheet Tab', () => {
  test('should fetch and display worksheet content successfully', async ({ page }) => {
    // 1. Navigate to the local server
    await page.goto('http://localhost:5173');

    // 2. Authenticate the user
    await page.getByRole('textbox', { name: 'Email Address' }).fill('student@example.com'); // Replace with your test email
    await page.getByRole('textbox', { name: 'Password' }).fill('your-password'); // Replace with your test password
    await page.getByRole('button', { name: 'Login' }).click();

    // Wait for the login to complete and navigate to the dashboard
    await page.waitForURL('**/dashboard**');

    // 3. Navigate to the specific chapter route (if not automatically redirected)
    await page.goto('http://localhost:5173/dashboard/unit/1/chapter/1');

    // 4. Wait for the InteractiveTutor component to mount
    const worksheetTab = page.locator('button', { hasText: /^Worksheet$/ }).first();
    await expect(worksheetTab).toBeVisible({ timeout: 15000 });

    // 5. Locate and click the 'Worksheet' tab in the UI
    const responsePromise = page.waitForResponse(response =>
      response.url().includes('supabase.co/rest/v1/resources') && response.status() === 200
    );

    await worksheetTab.click();
    await responsePromise;

    // 6. Assert that the <ReactMarkdown> container is successfully mounted and visible
    const markdownContainer = page.locator('.prose.prose-invert');
    await expect(markdownContainer).toBeVisible({ timeout: 10000 });

    // 7. Assert that the empty state ("No Worksheet Found") is NOT visible
    const emptyStateHeading = page.getByRole('heading', { name: 'No Worksheet Found' });
    await expect(emptyStateHeading).not.toBeVisible();
  });
});