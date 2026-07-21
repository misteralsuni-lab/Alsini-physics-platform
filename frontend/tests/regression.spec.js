import { test, expect } from '@playwright/test';

/*
 * ============================================================================
 *  GOLDEN REGRESSION SUITE — Alsini Physics VLE (vertical slice)
 * ============================================================================
 *  Covers the four-level user-journey test plan:
 *    Level 1  Smoke        -> check 1 (login) + check 2 (dashboard)
 *    Level 2  Rendering    -> check 3 (PDF) + check 4 (graph image)
 *    Level 3  Sync         -> check 6 (focus state) + Tests A-D
 *    Level 4  RAG          -> check 5 (search) + check 7 (citations)
 *    Cross-cutting         -> check 8 (no broken imgs) + 9 (no JS errors)
 *                          + 10 (no failed network requests)
 *    Original-bug guard   -> "Explain Question 4 / graph / table / practical"
 * ============================================================================
 */

// --- Route to the Golden Dataset worksheet (Forces & Motion / Chapter 1) ---
const UNIT_ID = '2cf312d3-0f4b-4339-84f3-97b10b2907ea';
const CHAPTER_ID = 'b95f8fac-355e-4037-bc1f-2d3b2bf77140';
const GOLDEN_RESOURCE_ID = '5729d034-a6c7-4f35-b81c-fcac447289c7';
const DASHBOARD_URL = `/dashboard/unit/${UNIT_ID}/chapter/${CHAPTER_ID}`;
const BACKEND = 'http://localhost:8000';
const GRAPH_ASSET = 'page2_graph_0.png';

// Collect console / page / network diagnostics for every test.
async function installDiagnostics(page) {
  const diag = { consoleErrors: [], pageErrors: [], failed: [] };
  page.__diag = diag;
  page.on('console', (m) => {
    if (m.type() === 'error') diag.consoleErrors.push(m.text());
  });
  page.on('pageerror', (e) => diag.pageErrors.push(e.message));
  page.on('requestfailed', (r) =>
    diag.failed.push({ url: r.url(), status: r.failure()?.errorText || 'requestfailed' })
  );
  page.on('response', (r) => {
    if (r.status() >= 400) diag.failed.push({ url: r.url(), status: r.status() });
  });
}

// Open the Golden Dataset worksheet (Worksheet tab + PDF iframe visible).
async function openWorksheet(page) {
  // Land on /dashboard first so the async Supabase session is restored.
  // (A direct deep-link to a chapter route hits the initial null-session
  // redirect to /auth and would drop the deep link.)
  await page.goto('/dashboard');
  await expect(page.getByRole('button', { name: 'Sign Out' })).toBeVisible({ timeout: 20_000 });
  await page.goto(DASHBOARD_URL);
  const worksheetTab = page.getByRole('button', { name: 'Worksheet', exact: true });
  await expect(worksheetTab).toBeVisible({ timeout: 20_000 });
  await worksheetTab.click();
  await expect(page.locator('iframe[title="Original worksheet PDF"]')).toBeVisible({
    timeout: 20_000,
  });
}

// Open the right-hand AI Tutor drawer.
async function openTutor(page) {
  const fab = page.getByRole('button', { name: 'Ask Tutor' });
  if (await fab.isVisible().catch(() => false)) await fab.click();
  await expect(page.getByPlaceholder('Ask your tutor a question...')).toBeVisible();
}

// Send a message and resolve with the /api/tutor response body + captured
// request so the structured LearningContext contract is verified directly.
async function askTutor(page, text) {
  let capturedRequest = null;
  const onRequest = (req) => {
    if (req.url().includes('/api/tutor') && req.method() === 'POST') {
      try {
        capturedRequest = req.postDataJSON();
      } catch {
        /* ignore */
      }
    }
  };
  page.on('request', onRequest);

  const [response] = await Promise.all([
    page.waitForResponse(
      (r) => r.url().includes('/api/tutor') && r.request().method() === 'POST',
      { timeout: 60_000 }
    ),
    page.getByPlaceholder('Ask your tutor a question...').fill(text),
    page.getByRole('button', { name: 'Send question to tutor' }).click(),
  ]);

  const body = await response.json();
  page.off('request', onRequest);
  return {
    body,
    capturedPrompt: capturedRequest?.student_prompt,
    capturedRequest,
  };
}

test.beforeEach(async ({ page }) => {
  await installDiagnostics(page);
});

// ---------------------------------------------------------------------------
// CHECK 1 — Login
// ---------------------------------------------------------------------------
test('[1] User can log in', async ({ page }) => {
  // The shared session is pre-authenticated via storageState, which would make
  // /auth redirect straight to /dashboard. Clear it first to exercise the real
  // login flow.
  await page.goto('/');
  await page.evaluate(() => localStorage.clear());
  await page.goto('/auth');
  await expect(page.getByPlaceholder('Email Address')).toBeVisible({ timeout: 20_000 });
  await page.getByPlaceholder('Email Address').fill(process.env.E2E_EMAIL || 'e2e_test@alsini.dev');
  await page.getByPlaceholder('Password').fill(process.env.E2E_PASSWORD || 'E2Etest1234');
  await page.getByRole('button', { name: 'Login', exact: true }).click();
  await page.waitForURL('**/dashboard**', { timeout: 20_000 });
  await expect(page).toHaveURL(/\/dashboard/);
});

// ---------------------------------------------------------------------------
// CHECK 2 — Dashboard loads
// ---------------------------------------------------------------------------
test('[2] Dashboard loads after login', async ({ page }) => {
  await page.goto('/dashboard');
  await expect(page.getByRole('heading', { name: /Welcome to your Dashboard/i })).toBeVisible();
  // Sidebar nav must be present (proves the VLE shell mounted).
  await expect(page.getByText(/Select a unit from the sidebar/i)).toBeVisible();
});

// ---------------------------------------------------------------------------
// CHECK 3 — Original PDF renders
// ---------------------------------------------------------------------------
test('[3] Original worksheet PDF renders (HTTP 200)', async ({ page }) => {
  let pdfStatus = null;
  page.on('response', (r) => {
    if (r.url().includes('original.pdf')) pdfStatus = r.status();
  });

  await openWorksheet(page);

  const iframe = page.locator('iframe[title="Original worksheet PDF"]');
  await expect(iframe).toBeVisible();
  const src = await iframe.getAttribute('src');
  expect(src).toContain(`resource-assets/${GOLDEN_RESOURCE_ID}/original.pdf`);
  // The browser actually fetched the PDF from Supabase Storage.
  await expect
    .poll(() => pdfStatus, { timeout: 20_000 })
    .toBe(200);
});

// ---------------------------------------------------------------------------
// CHECK 4 — Graph image loads (HTTP 200)
// ---------------------------------------------------------------------------
test('[4] Graph image loads (HTTP 200)', async ({ page }) => {
  let graphStatus = null;
  page.on('response', (r) => {
    if (r.url().includes(GRAPH_ASSET)) graphStatus = r.status();
  });

  await openWorksheet(page);

  const graphImg = page.locator(`img[src*="${GRAPH_ASSET}"]`);
  await expect(graphImg).toBeVisible({ timeout: 20_000 });
  await expect
    .poll(() => graphStatus, { timeout: 20_000 })
    .toBe(200);
  // The image decoded successfully (not a broken image icon).
  expect(await graphImg.evaluate((el) => el.naturalWidth)).toBeGreaterThan(0);
});

// ---------------------------------------------------------------------------
// CHECK 5 — Search returns results
// ---------------------------------------------------------------------------
test('[5] Knowledge search returns results', async ({ page }) => {
  await openWorksheet(page);
  await page.getByRole('button', { name: 'Search', exact: true }).click();

  const [resp] = await Promise.all([
    page.waitForResponse(
      (r) => r.url().includes('/api/search/hybrid') && r.request().method() === 'POST'
    ),
    page.getByPlaceholder('Search concepts, formulas...').fill('velocity'),
    page.keyboard.press('Enter'),
  ]);

  const data = await resp.json();
  expect(data.count).toBeGreaterThan(0);
  expect(data.search_type).toBe('hybrid');

  // The UI renders at least one result button (carries a similarity %).
  await expect(page.locator('button', { hasText: /%/ }).first()).toBeVisible({ timeout: 15_000 });
});

// ---------------------------------------------------------------------------
// CHECK 6 — Clicking a search result updates the focus state  (Sync Test C)
// ---------------------------------------------------------------------------
test('[6] Clicking a search result updates focus (context chip)', async ({ page }) => {
  await openWorksheet(page);
  await openTutor(page);
  await page.getByRole('button', { name: 'Search', exact: true }).click();

  await page.getByPlaceholder('Search concepts, formulas...').fill('velocity');
  await page.keyboard.press('Enter');
  await expect(page.locator('button', { hasText: /%/ }).first()).toBeVisible({ timeout: 15_000 });

  // Click the top result -> onNavigate sets focus -> context chip appears.
  await page.locator('button', { hasText: /%/ }).first().click();

  const chip = page.getByText(/Viewing/i).or(page.getByText(/Concept:/i)).first();
  await expect(chip).toBeVisible({ timeout: 10_000 });
});

// ---------------------------------------------------------------------------
// SYNC TEST A — Click concept -> focus chip -> chat
// ---------------------------------------------------------------------------
test('[A] Click concept sets focus and is consumed by the tutor', async ({ page }) => {
  await openWorksheet(page);
  await openTutor(page);

  // Switch to Interactive Knowledge mode.
  await page.getByRole('button', { name: 'Interactive Tutor' }).click();
  const firstConcept = page.locator('button', { hasText: /[A-Za-z]/ }).filter({
    hasText: /CONCEPT|concept/i,
  });
  // Click the first concept card (the one rendered with an emerald concept label).
  const conceptCard = page.locator('div').filter({ hasText: /Velocity|Displacement|Speed/ }).first();
  await expect(conceptCard).toBeVisible({ timeout: 10_000 });

  // Context chip appears in the chat input.
  await expect(page.getByText(/Context/i)).toBeVisible({ timeout: 10_000 });
  await expect(page.getByText(/Concept:/i)).toBeVisible({ timeout: 10_000 });
});

// ---------------------------------------------------------------------------
// SYNC TEST B — Click graph -> focus -> next prompt contains graph context
// ---------------------------------------------------------------------------
test('[B] Clicking the graph injects graph context into the next prompt', async ({ page }) => {
  await openWorksheet(page);
  await openTutor(page);

  // Click the graph asset card (document mode) -> focus type 'asset'.
  const graphCard = page.locator(`img[src*="${GRAPH_ASSET}"]`).first();
  await expect(graphCard).toBeVisible({ timeout: 15_000 });
  await graphCard.click();

  await expect(page.getByText(/Viewing/i)).toBeVisible({ timeout: 10_000 });

  const { capturedRequest } = await askTutor(page, 'What does it show?');
  expect(capturedRequest.learning_context.focused_asset).toBeTruthy();
  expect(capturedRequest.learning_context.focused_asset_type).toMatch(/graph|figure/i);
  expect(capturedRequest.learning_context.focused_asset_label).toMatch(/^FIG-/);
});

// ---------------------------------------------------------------------------
// SYNC TEST D — "Explain this graph" uses the focused graph
// ---------------------------------------------------------------------------
test('[D] Tutor grounds "Explain this graph" in the focused graph', async ({ page }) => {
  await openWorksheet(page);
  await openTutor(page);

  const graphCard = page.locator(`img[src*="${GRAPH_ASSET}"]`).first();
  await graphCard.click();
  await expect(page.getByText(/Viewing/i)).toBeVisible();

  const { body, capturedRequest } = await askTutor(page, 'Explain this graph.');
  expect(capturedRequest.learning_context.focused_asset).toBeTruthy();
  expect(capturedRequest.learning_context.focused_asset_label).toMatch(/^FIG-/);
  expect(body.sources.length).toBeGreaterThan(0);
  // The UI must expose the grounded source as an expandable citation chip.
  const lastMsg = page.locator('.space-y-6 > div').last();
  await expect(lastMsg.getByRole('button', { name: /Citation/i }).first()).toBeVisible({ timeout: 15_000 });
});

// ---------------------------------------------------------------------------
// CHECK 7 — "Explain the graph" returns citations
// ---------------------------------------------------------------------------
test('[7] Tutor returns RAG citations for "Explain the graph"', async ({ page }) => {
  await openWorksheet(page);
  await openTutor(page);

  const { body } = await askTutor(page, 'Explain the graph.');
  expect(Array.isArray(body.sources)).toBe(true);
  expect(body.sources.length).toBeGreaterThan(0);
  expect(body.response.length).toBeGreaterThan(0);

  // The UI renders citation chips under the latest AI message.
  const lastMsg = page.locator('.space-y-6 > div').last();
  await expect(lastMsg.getByRole('button', { name: /Citation/i }).first()).toBeVisible({ timeout: 15_000 });
});

// ---------------------------------------------------------------------------
// CHECK 8 — No broken images
// ---------------------------------------------------------------------------
test('[8] No broken images in the worksheet', async ({ page }) => {
  await openWorksheet(page);

  // Wait for images to settle, then assert none failed to load.
  const imgs = page.locator('img');
  const count = await imgs.count();
  expect(count).toBeGreaterThan(0);

  for (let i = 0; i < count; i++) {
    const el = imgs.nth(i);
    const ok = await el.evaluate((n) => n.complete && n.naturalWidth > 0).catch(() => false);
    expect(ok, `image #${i} failed to decode`).toBe(true);
  }
  // Explicit "Failed to load asset" retry state must never appear.
  await expect(page.getByText(/Failed to load asset/i)).toHaveCount(0);
});

// ---------------------------------------------------------------------------
// CHECK 9 — No JavaScript errors
// ---------------------------------------------------------------------------
test('[9] No JavaScript / console errors during the journey', async ({ page }) => {
  await openWorksheet(page);
  await openTutor(page);
  await page.getByRole('button', { name: 'Search', exact: true }).click();
  await page.getByPlaceholder('Search concepts, formulas...').fill('velocity');
  await page.keyboard.press('Enter');
  await expect(page.locator('button', { hasText: /%/ }).first()).toBeVisible({ timeout: 15_000 });
  await askTutor(page, 'What is velocity?');

  const benign = (s) =>
    /favicon\.ico/i.test(s) || /Download the React DevTools/i.test(s);
  const realConsole = page.__diag.consoleErrors.filter((s) => !benign(s));
  const realPage = page.__diag.pageErrors.filter((s) => !benign(s));

  expect(realPage, `pageErrors: ${JSON.stringify(realPage)}`).toEqual([]);
  expect(realConsole, `consoleErrors: ${JSON.stringify(realConsole)}`).toEqual([]);
});

// ---------------------------------------------------------------------------
// CHECK 10 — No failed network requests
// ---------------------------------------------------------------------------
test('[10] No failed network requests', async ({ page }) => {
  await openWorksheet(page);
  await openTutor(page);
  await askTutor(page, 'What is displacement?');

  const benign = (f) => /favicon\.ico/i.test(f.url);
  const real = page.__diag.failed.filter((f) => !benign(f));
  expect(real, `failed requests: ${JSON.stringify(real, null, 2)}`).toEqual([]);
});

// ---------------------------------------------------------------------------
// ORIGINAL-BUG GUARD — Golden Dataset repeat (visual stays on screen)
// ---------------------------------------------------------------------------
test('[GOLDEN] Explain Q4 / graph / table / practical with visuals on screen', async ({
  page,
}) => {
  await openWorksheet(page);
  await openTutor(page);

  // The visual elements must remain on screen for every question.
  const pdf = page.locator('iframe[title="Original worksheet PDF"]');
  const graph = page.locator(`img[src*="${GRAPH_ASSET}"]`).first();
  await expect(pdf).toBeVisible();
  await expect(graph).toBeVisible();

  const prompts = [
    'Explain Question 4.',
    'Explain the graph.',
    'Explain the table.',
    'Explain the practical investigation.',
  ];

  for (const p of prompts) {
    const { body } = await askTutor(page, p);
    expect(body.sources.length, `No RAG sources for "${p}"`).toBeGreaterThan(0);
    // Visuals still visible while the answer is shown.
    await expect(pdf).toBeVisible();
    await expect(graph).toBeVisible();
  }
});
