import { defineConfig } from '@playwright/test';

export default defineConfig({
  testDir: './e2e',
  // real-api/** runs against a real live stack via playwright.real-api.config.ts, not this
  // mocked-webServer config.
  testIgnore: '**/real-api/**',
  use: { baseURL: 'http://127.0.0.1:3001' },
  webServer: {
    command: 'npm run start -- --port 3001',
    url: 'http://127.0.0.1:3001',
    reuseExistingServer: true,
  },
});
