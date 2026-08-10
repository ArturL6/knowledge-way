import { defineConfig } from 'vitest/config';

// Tooling caveat: the Playwright MCP server can't launch here — @playwright/mcp hard-codes the
// `chrome` channel path `/opt/google/chrome/chrome`. Bundled Chromium works via explicit executablePath.
export default defineConfig({
  test: {
    environment: 'node',
  },
});
