import { defineConfig } from '@playwright/test';

// Runs e2e-real/** against a real running keyless web+API stack — no route mocking, no managed
// webServer. Default REAL_WEB_URL (45850) is a `next build && next start` of this checkout
// pointed at the shared keyless API (34747), because the given pre-built instance on 45849
// serves whatever code was live when it was started and won't pick up local edits without a
// rebuild/restart. Override REAL_WEB_URL/REAL_API_URL to point at any other keyless stack.
// workers: 1 because these tests mutate shared workspace state on that stack.
export default defineConfig({
  testDir: './e2e/real-api',
  workers: 1,
  use: { baseURL: process.env.REAL_WEB_URL || 'http://127.0.0.1:45850' },
});
