/**
 * Optional live HTTP smoke checks; start Next dev server before running.
 * Does not log in; use the manual authenticated checklist in the new run guide
 * to validate submitting and saving against SQL Server.
 */
import assert from 'node:assert/strict';

const base = (process.env.SMOKE_FRONTEND_URL || 'http://127.0.0.1:3000').replace(/\/$/, '');

async function checkPage(path) {
  const response = await fetch(`${base}${path}`, { redirect: 'manual' });
  assert.equal(response.status, 200, `${path}: expected HTTP 200, got ${response.status}`);
  const type = response.headers.get('content-type') || '';
  assert.ok(type.includes('text/html'), `${path}: expected HTML, got ${type}`);
  console.log(`PASS GET ${path}`);
}

try {
  await checkPage('/create');
  await checkPage('/post/create');
  await checkPage('/edit/1');
  const response = await fetch(`${base}/api/fe/tag-suggestions`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ title: 'Learning Python', content: 'Learn Python for processing and analysing data.' }),
  });
  assert.equal(response.status, 401, 'Suggestion API should reject unauthenticated requests');
  console.log('PASS POST /api/fe/tag-suggestions rejects anonymous request');
} catch (error) {
  console.error('HTTP smoke failed. Start Next.js with npm run dev and check the README.');
  console.error(error);
  process.exitCode = 1;
}
