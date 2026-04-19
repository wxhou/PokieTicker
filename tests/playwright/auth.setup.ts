// Auth setup for Playwright Test Agents
// This file authenticates once and saves the session state to .auth/user.json
// All subsequent tests reuse this state — no repeated logins needed.
//
// Setup:
//   1. Set credentials: export E2E_USERNAME=xxx E2E_PASSWORD=yyy
//   2. Run: npx playwright test --project=setup
//      (if UI login: browser opens — log in manually once)
//   3. Credentials are saved — tests auto-use the saved session
//
// To switch users, update credentials and re-run step 2.
//
// For multi-user testing, add more setup blocks with different storageState paths.

import { test as setup } from '@playwright/test';
import { existsSync } from 'fs';

// ─── API Login (preferred) ───────────────────────────────────────────────────
// If your app has a login API, configure it in tests/playwright/credentials.yaml:
//   api: /api/auth/login
// Then this block runs automatically.

setup('authenticate via API', async ({ page }) => {
  const baseUrl = process.env.BASE_URL || 'http://localhost:7777/PokieTicker';
  const username = process.env.E2E_USERNAME;
  const password = process.env.E2E_PASSWORD;

  if (!username || !password) {
    throw new Error(
      'E2E_USERNAME and E2E_PASSWORD environment variables are required.\n' +
      'Set them with: export E2E_USERNAME=xxx E2E_PASSWORD=yyy'
    );
  }

  const res = await page.request.post(`${baseUrl}/api/auth/login`, {
    data: { email: username, password },
  });

  if (!res.ok()) {
    throw new Error(`API login failed (${res.status()}). Check credentials.`);
  }

  await page.context().storageState({ path: './playwright/.auth/user.json' });

  if (!existsSync('./playwright/.auth/user.json')) {
    throw new Error('Auth setup failed: storageState file was not created');
  }
});

// ─── UI Login ──────────────────────────────────────────────────────────────
// This app uses API-based login only. No UI login page exists.
