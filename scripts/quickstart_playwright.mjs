import { createRequire } from 'node:module';
const require = createRequire(import.meta.url);
const { chromium } = require('../apps/web/node_modules/playwright');

const [webBase, apiBase, revision] = process.argv.slice(2);
if (!webBase || !apiBase || !revision) {
  throw new Error('usage: node scripts/quickstart_playwright.mjs <web-base> <api-base> <fastapi-revision>');
}

const timeoutAt = Date.now() + 20 * 60 * 1000;
const browser = await chromium.launch({ headless: true });
try {
  const page = await browser.newPage();
  await page.goto(webBase, { waitUntil: 'networkidle' });
  await page.getByLabel('Repository name').fill('fastapi-stack');
  await page.getByLabel('Clone URL').fill('https://github.com/fastapi/fastapi.git');
  await page.getByRole('button', { name: 'Add repository' }).click();
  await page.getByText('fastapi-stack', { exact: true }).waitFor({ timeout: 30_000 });

  let repository;
  while (Date.now() < timeoutAt) {
    const response = await fetch(`${apiBase}/repositories`);
    if (!response.ok) throw new Error(`repository listing returned ${response.status}`);
    repository = (await response.json()).find((item) => item.name === 'fastapi-stack');
    if (repository) break;
    await new Promise((resolve) => setTimeout(resolve, 250));
  }
  if (!repository) throw new Error('browser-added fastapi-stack was not created');
  // The dashboard intentionally has no revision field. Pin the smoke fixture immediately through
  // the public reindex contract so the successful snapshot is deterministic.
  const pin = await fetch(`${apiBase}/repositories/${repository.id}/reindex`, {
    method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ requested_revision: revision }),
  });
  if (!pin.ok) throw new Error(`could not pin fastapi-stack: ${pin.status} ${await pin.text()}`);
  while (Date.now() < timeoutAt) {
    const response = await fetch(`${apiBase}/repositories`);
    if (!response.ok) throw new Error(`repository listing returned ${response.status}`);
    repository = (await response.json()).find((item) => item.name === 'fastapi-stack');
    if (repository?.indexing_status === 'ready' && repository.indexed_commit_sha === revision) break;
    if (repository?.indexing_status === 'failed') throw new Error(`indexing failed: ${repository.error_message}`);
    await new Promise((resolve) => setTimeout(resolve, 2_000));
  }
  if (!repository || repository.indexing_status !== 'ready') throw new Error('timed out waiting for fastapi-stack indexing');

  await page.goto(`${webBase}/search`, { waitUntil: 'networkidle' });
  await page.locator('#search-query').fill('FastAPI');
  await page.getByRole('button', { name: 'Search' }).click();
  const result = page.locator('.result').first();
  await result.waitFor({ timeout: 30_000 });
  await result.getByRole('link', { name: 'Open source →' }).click();
  await page.getByRole('heading', { name: 'Source' }).waitFor({ timeout: 30_000 });
  console.log(`PASS browser add/index/search/evidence: ${repository.id} @ ${repository.indexed_commit_sha}`);
} finally {
  await browser.close();
}
