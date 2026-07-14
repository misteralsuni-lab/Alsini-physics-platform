import { defineConfig, devices } from '@playwright/test';

const ROOT = '/home/alsuni/Alsini-physics-platform';
const BACKEND_URL = 'http://localhost:8000';
const FRONTEND_URL = 'http://localhost:5173';

export default defineConfig({
  testDir: './tests',
  timeout: 90_000,
  expect: { timeout: 20_000 },
  fullyParallel: false,
  workers: 1,
  retries: process.env.CI ? 1 : 0,
  reporter: [['list']],

  use: {
    baseURL: FRONTEND_URL,
    trace: 'off',
    screenshot: 'only-on-failure',
    video: 'off',
    // The bundled chrome-headless-shell is missing system libs in this
    // environment; the full Chromium build has all its deps satisfied,
    // so launch that binary directly (applies to every project).
    launchOptions: {
      executablePath:
        '/home/alsuni/.cache/ms-playwright/chromium-1217/chrome-linux64/chrome',
      args: [
        '--no-sandbox',
        '--disable-dev-shm-usage',
        '--disable-gpu',
        '--disable-software-rasterizer',
        '--disable-background-mode',
      ],
    },
  },

  projects: [
    // 1) Authenticate once and persist the session to disk.
    { name: 'setup', testMatch: /auth\.setup\.js/ },

    // 2) Every regression check reuses the authenticated session.
    {
      name: 'chromium',
      use: {
        ...devices['Desktop Chrome'],
        storageState: './playwright/.auth/user.json',
      },
      dependencies: ['setup'],
    },
  ],

  // Reuse already-running dev servers when present (the QA harness usually
  // starts them); otherwise boot them automatically.
  webServer: [
    {
      name: 'backend',
      command: `cd ${ROOT}/backend && .venv/bin/python -m uvicorn main:app --port 8000`,
      url: `${BACKEND_URL}/health`,
      reuseExistingServer: true,
      timeout: 60_000,
      stdout: 'ignore',
      stderr: 'pipe',
    },
    {
      name: 'frontend',
      command: `cd ${ROOT}/frontend && npm run dev`,
      url: FRONTEND_URL,
      reuseExistingServer: true,
      timeout: 120_000,
      stdout: 'ignore',
      stderr: 'pipe',
    },
  ],
});
