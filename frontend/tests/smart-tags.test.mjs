/**
 * Run on Node 22.16+ without editing package.json:
 *   node --experimental-strip-types --test tests/smart-tags.test.mjs
 */
import test from 'node:test';
import assert from 'node:assert/strict';
import {
  filterSuggestedTags, isSuggestionReady, parseTagSuggestions,
  rankExistingTags, uniqueTags, TAG_SUGGESTION_LIMIT,
} from '../features/smart-tags/tagLogic.ts';
import { createDebouncedRequestController } from '../features/smart-tags/requestController.ts';
import { toEditDraft, toPostWritePayload } from '../features/smart-tags/postFlow.ts';

const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

test('title and content threshold prevents premature suggestions', () => {
  assert.equal(isSuggestionReady('test', 'A long enough description'), false);
  assert.equal(isSuggestionReady('Valid title', 'short'), false);
  assert.equal(isSuggestionReady('Valid title', 'This content is long enough to trigger.'), true);
});

test('API shapes, deduplication and selected tags are filtered', () => {
  assert.deepEqual(parseTagSuggestions({ suggestions: [{ name: ' Next.js ' }, { tag: 'Python' }, 'PYTHON'] }), ['next.js', 'python']);
  assert.deepEqual(parseTagSuggestions({ tags: ['fastapi', 'FastAPI'] }), ['fastapi']);
  assert.deepEqual(filterSuggestedTags(['React', 'PYTHON', 'python', 'next'], ['react']), ['python', 'next']);
  assert.deepEqual(uniqueTags(['React', 'react', ' ', '#React']), ['react']);
  assert.throws(() => parseTagSuggestions({ bad: true }));
});

test('lexical ranking is from existing tags only and capped', () => {
  const tags = ['python', 'docker', 'react', 'machine learning', 'database', 'fastapi', 'AI', 'typescript', 'nlp', 'sql'];
  const actual = rankExistingTags('Docker FastAPI', 'Deploy a Docker container with FastAPI and Python on the server', tags);
  assert.equal(actual[0], 'docker');
  assert.equal(actual[1], 'fastapi');
  assert.ok(actual.every((tag) => tags.map((value) => value.toLowerCase()).includes(tag)));
  assert.ok(actual.length <= TAG_SUGGESTION_LIMIT);
  assert.deepEqual(rankExistingTags('Title', 'Completely unrelated text here', ['react']), []);
});

test('debounce sends only once after the user stops typing', async () => {
  const seen = [];
  const received = [];
  const runner = createDebouncedRequestController(
    async (query) => { seen.push(query.title); return [query.title]; },
    {
      waiting() {}, loading() {}, result(_q, data) { received.push(data); },
      error(_q, error) { throw error; },
    },
    45,
  );
  runner.schedule({ title: 'one', content: 'text' });
  await sleep(12);
  runner.schedule({ title: 'two', content: 'text' });
  await sleep(12);
  runner.schedule({ title: 'three', content: 'text' });
  await sleep(75);
  assert.deepEqual(seen, ['three']);
  assert.deepEqual(received, [['three']]);
  runner.dispose();
});

test('stale response is ignored even when upstream ignores AbortSignal', async () => {
  let resolveOld;
  const results = [];
  const errors = [];
  const abortedSignals = [];
  const runner = createDebouncedRequestController(
    (query, signal) => {
      if (query.title === 'old') {
        abortedSignals.push(signal);
        return new Promise((resolve) => { resolveOld = resolve; });
      }
      return Promise.resolve(['new-tag']);
    },
    {
      waiting() {}, loading() {},
      result(query, data) { results.push({ query: query.title, data }); },
      error(_query, error) { errors.push(error); },
    },
    10,
  );
  runner.schedule({ title: 'old', content: 'text' });
  await sleep(25); // old request has started
  runner.schedule({ title: 'new', content: 'text' });
  assert.equal(abortedSignals[0].aborted, true);
  await sleep(35);
  resolveOld(['stale-tag']);
  await sleep(8);
  assert.deepEqual(results, [{ query: 'new', data: ['new-tag'] }]);
  assert.deepEqual(errors, []);
  runner.dispose();
});

test('request errors from an obsolete query are also ignored', async () => {
  let rejectOld;
  const errors = [];
  const results = [];
  const runner = createDebouncedRequestController(
    (query) => query.title === 'old'
      ? new Promise((_resolve, reject) => { rejectOld = reject; })
      : Promise.resolve(['latest']),
    {
      waiting() {}, loading() {},
      result(_query, data) { results.push(data); },
      error(_query, error) { errors.push(error); },
    },
    10,
  );
  runner.schedule({ title: 'old', content: 'text' });
  await sleep(25);
  runner.schedule({ title: 'latest', content: 'text' });
  rejectOld(new Error('old request failed'));
  await sleep(35);
  assert.deepEqual(results, [['latest']]);
  assert.deepEqual(errors, []);
  runner.dispose();
});

test('cancel prevents pending debounce from starting', async () => {
  let calls = 0;
  const runner = createDebouncedRequestController(
    async () => { calls++; return []; },
    { waiting() {}, loading() {}, result() {}, error() {} },
    35,
  );
  runner.schedule({ title: 'cancelled', content: 'text' });
  runner.cancel();
  await sleep(60);
  assert.equal(calls, 0);
  runner.dispose();
});


test('Create Post preserves original backend payload semantics', () => {
  const draft = { title: 'Python learning', content: 'Learning data processing', image: 'data:image/png;base64,AA==', tags: ['python', 'data'] };
  assert.deepEqual(toPostWritePayload(draft), {
    title: draft.title, content: draft.content,
    cover_image: draft.image, tags: ['python', 'data'],
  });
  assert.deepEqual(draft.tags, ['python', 'data']); // helper must not mutate selection
});

test('Edit Post restores pending moderation requests and preserves them on save', () => {
  const source = {
    title: 'Python learning', content: 'My article', cover_image: null,
    tags: ['python', ' Docker '], requested_new_tags: ['new-tag', 'PYTHON'],
  };
  const draft = toEditDraft(source);
  assert.deepEqual(draft.tags, ['python', 'docker', 'new-tag']);
  assert.equal(draft.image, '');
  assert.deepEqual(toPostWritePayload(draft).tags, ['python', 'docker', 'new-tag']);
});
