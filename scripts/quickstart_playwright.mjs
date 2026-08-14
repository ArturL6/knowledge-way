import { createRequire } from 'node:module';
const require = createRequire(import.meta.url);
const { chromium } = require('../apps/web/node_modules/playwright');

const [webBase, apiBase] = process.argv.slice(2);
if (!webBase || !apiBase) {
  throw new Error('usage: node scripts/quickstart_playwright.mjs <web-base> <api-base>');
}

const fixtures = [
  { name: 'fastapi-stack', cloneUrl: 'https://github.com/fastapi/fastapi.git', revision: '40e33e492dbf4af6172997f4e3238a32e56cbe26' },
  { name: 'starlette-stack', cloneUrl: 'https://github.com/encode/starlette.git', revision: '8d0cff820f89b5d5b19677246293513a9d1c952c' },
  { name: 'pydantic-stack', cloneUrl: 'https://github.com/pydantic/pydantic.git', revision: '7cedbfb03df82ac55c844c97e6f975359cb51bb9' },
];
const timeoutAt = Date.now() + 100 * 60 * 1000;
const sleep = (milliseconds) => new Promise((resolve) => setTimeout(resolve, milliseconds));

async function api(path, options) {
  const response = await fetch(`${apiBase}${path}`, options);
  if (!response.ok) throw new Error(`${path} returned ${response.status}: ${await response.text()}`);
  return response.status === 204 ? undefined : response.json();
}

async function waitForReady(name, revision) {
  while (Date.now() < timeoutAt) {
    const repository = (await api('/repositories')).find((item) => item.name === name);
    if (repository?.indexing_status === 'ready' && repository.indexed_commit_sha === revision) return repository;
    if (repository?.indexing_status === 'failed') throw new Error(`${name} indexing failed: ${repository.error_message}`);
    await sleep(2_000);
  }
  throw new Error(`timed out waiting for ${name} @ ${revision}`);
}

const browser = await chromium.launch({ headless: true });
try {
  const page = await browser.newPage();
  await page.goto(webBase, { waitUntil: 'networkidle' });
  // The UI must remain usable in the quickstart. Add the selected workspace's first repository
  // through the dashboard, then use the same public repository contract for the remaining pins.
  const first = fixtures[0];
  await page.getByLabel('Repository name').fill(first.name);
  await page.getByLabel('Clone URL').fill(first.cloneUrl);
  await page.getByRole('button', { name: 'Add repository' }).click();
  await page.getByText(first.name, { exact: true }).waitFor({ timeout: 30_000 });

  for (const fixture of fixtures.slice(1)) {
    await api('/repositories', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ name: fixture.name, clone_url: fixture.cloneUrl }) });
  }
  const repositories = await api('/repositories');
  for (const fixture of fixtures) {
    const repository = repositories.find((item) => item.name === fixture.name);
    if (!repository) throw new Error(`${fixture.name} was not created`);
    await api(`/repositories/${repository.id}/reindex`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ requested_revision: fixture.revision }) });
  }
  const ready = [];
  for (const fixture of fixtures) ready.push(await waitForReady(fixture.name, fixture.revision));

  const workspace = await api('/workspaces', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ name: 'fastapi-stack', description: 'Permanent Stage 0 selected FastAPI, Starlette, and Pydantic workspace.' }) });
  for (const repository of ready) await api(`/workspaces/${workspace.id}/repositories/${repository.id}`, { method: 'PUT' });
  const fastapi = ready.find((repository) => repository.name === 'fastapi-stack');
  for (const target of ready.filter((repository) => repository.id !== fastapi.id)) {
    await api(`/workspaces/${workspace.id}/dependencies`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ source_repository_id: fastapi.id, target_repository_id: target.id, reason: 'FastAPI provider dependency declared for selected fastapi-stack fixture.' }) });
  }
  const dependencies = await api(`/workspaces/${workspace.id}/dependencies`);
  if (dependencies.length !== 2 || !dependencies.every((dependency) => dependency.source_repository_id === fastapi.id)) throw new Error('fastapi-stack dependency declarations were not recorded');

  await page.goto(`${webBase}/search`, { waitUntil: 'networkidle' });
  await page.locator('#search-query').fill('FastAPI');
  await page.getByRole('button', { name: 'Search' }).click();
  const result = page.locator('.result').first();
  await result.waitFor({ timeout: 30_000 });
  await result.getByRole('link', { name: 'Open source →' }).click();
  await page.getByRole('heading', { name: 'Source' }).waitFor({ timeout: 30_000 });
  console.log(`PASS browser selected-workspace add/index/search/evidence: ${ready.map((repository) => `${repository.name} @ ${repository.indexed_commit_sha}`).join(', ')}; dependencies=${dependencies.length}`);
} finally {
  await browser.close();
}
