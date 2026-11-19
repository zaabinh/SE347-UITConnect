const assert = require('node:assert/strict');
const { test } = require('node:test');
const fs = require('node:fs');
const path = require('node:path');
const Module = require('node:module');
const ts = require('typescript');
const axios = require('axios');

const root = path.resolve(__dirname, '..');
const contract = JSON.parse(fs.readFileSync(path.resolve(root, '../backend/tests/api_v1_contract.json'), 'utf8'));
process.env.NEXT_PUBLIC_API_URL = 'https://api.example.test/ignored-path';
global.window = {};
global.localStorage = new class {
  values = new Map();
  getItem(key) { return this.values.get(key) ?? null; }
  setItem(key, value) { this.values.set(key, String(value)); }
  removeItem(key) { this.values.delete(key); }
  clear() { this.values.clear(); }
}();

// Compile the production clients in memory, retaining their real Axios interceptors.
function loader(mocks = {}) {
  const cache = new Map();
  function load(file) {
    if (cache.has(file)) return cache.get(file).exports;
    const mod = { exports: {} };
    cache.set(file, mod);
    const compiled = ts.transpileModule(fs.readFileSync(file, 'utf8'), {
      compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2020, jsx: ts.JsxEmit.ReactJSX, esModuleInterop: true },
      fileName: file,
    }).outputText;
    const nativeRequire = Module.createRequire(file);
    function requireSource(name) {
      if (name in mocks) return mocks[name];
      if (mocks.__components && name.startsWith('@/components/')) return { __esModule: true, default: () => null };
      if (name.startsWith('@/')) {
        const target = path.resolve(root, name.slice(2));
        return load(fs.existsSync(`${target}.ts`) ? `${target}.ts` : `${target}.tsx`);
      }
      return nativeRequire(name);
    }
    new Function('require', 'module', 'exports', compiled)(requireSource, mod, mod.exports);
    return mod.exports;
  }
  return (file) => load(path.resolve(root, file));
}

const load = loader();
const auth = load('lib/axios.ts');
const forum = load('lib/forumApi.ts');
const profile = load('lib/profileApi.ts');
const admin = load('lib/adminApi.ts');
const media = load('lib/mediaApi.ts');
const tokens = { access_token: 'access-old', refresh_token: 'refresh-token', token_type: 'bearer', expires_in: 3600 };
const identity = { id: 'user-id', username: 'student', email: 'student@example.test', profile_completed: true };
const requests = [];
let reply;

function endpoint(config) {
  const fullPath = `/api/v1${config.url}`;
  const entry = contract.endpoints.find((entry) => entry.method === config.method.toUpperCase()
    && new RegExp(`^${entry.path.replace(/\{[^}]+\}/g, '[^/]+')}$`).test(fullPath));
  assert.ok(entry, `Request is absent from frozen contract: ${config.method} ${fullPath}`);
  assert.equal(config.baseURL, 'https://api.example.test/api/v1');
  assert.ok(!config.url.endsWith('/'), 'No trailing slash redirects');
  return entry;
}

function reset() {
  localStorage.clear();
  auth.saveAuthSession(tokens, identity);
  requests.length = 0;
  reply = undefined;
  auth.api.defaults.adapter = async (config) => {
    const entry = endpoint(config);
    requests.push(config);
    const result = reply ? await reply(config, entry) : { data: entry.status === 204 ? '' : identity };
    return { status: entry.status, statusText: '', headers: {}, config, ...result };
  };
}

function body(request = requests.at(-1)) {
  return request.data === undefined ? undefined : JSON.parse(request.data);
}

function problem(config, status = 401) {
  const data = { type: 'about:blank', title: 'Unauthorized', status, detail: 'Session expired.', instance: config.url, code: 'unauthorized', request_id: 'request-1' };
  return new axios.AxiosError(data.detail, 'ERR_BAD_REQUEST', config, undefined,
    { status, data, headers: { 'content-type': 'application/problem+json' }, config });
}

test('forum clients send frozen paths, methods, bodies and preserve share IDs', async () => {
  reset();
  const cases = [
    [() => forum.getFeed({ page: 2, pageSize: 7, mode: 'following' }), 'get', '/feed'],
    [() => forum.getPost(42), 'get', '/posts/42'],
    [() => forum.createPost({ title: 'Title', content: 'Body', tags: ['api'] }), 'post', '/posts', { title: 'Title', content: 'Body', tags: ['api'] }],
    [() => forum.updatePost(42, { cover_image: null }), 'patch', '/posts/42', { cover_image: null }],
    [() => forum.deletePost(42), 'delete', '/posts/42'],
    [() => forum.getComments(42), 'get', '/posts/42/comments'],
    [() => forum.createComment(42, { content: 'Reply', parent_id: 3 }), 'post', '/posts/42/comments', { content: 'Reply', parent_id: 3 }],
    [() => forum.reportPost(42, { reason: 'spam' }), 'post', '/posts/42/reports', { reason: 'spam', details: null }],
    [() => forum.reportComment(42, 3, { reason: 'other', details: 'Explanation' }), 'post', '/posts/42/comments/3/reports', { reason: 'other', details: 'Explanation' }],
    [() => forum.getTags(), 'get', '/tags'],
    [() => forum.getSimilarPosts(42), 'get', '/recommendations/posts/42/similar'],
    [() => forum.getCollaborativeRecommendations(), 'get', '/recommendations/collaborative'],
    [() => forum.getProfileBasedRecommendations(), 'get', '/recommendations/profile'],
    [() => forum.getUserProfileSummary(), 'get', '/recommendations/profile-summary'],
    [() => forum.getProfileAnalysis(), 'get', '/recommendations/profile-analysis'],
  ];
  for (const [call, method, url, payload] of cases) {
    const count = requests.length;
    await call();
    assert.equal(requests.length, count + 1, 'Reads have no implicit view event');
    assert.equal(requests.at(-1).method, method);
    assert.equal(requests.at(-1).url, url);
    assert.equal(requests.at(-1).headers.get('Authorization'), 'Bearer access-old');
    if (payload) assert.deepEqual(body(), payload);
  }
  assert.deepEqual(requests[0].params, { page: 2, page_size: 7, search: undefined, tag: undefined, mode: 'following', sort: 'latest' });
  await forum.recordPostView(42);
  assert.equal(requests.at(-1).url, '/posts/42/views');
  assert.equal(requests.at(-1).method, 'post');
  reply = () => ({ data: { post_id: 99, original_post_id: 42 } });
  assert.deepEqual(await forum.sharePost(42), { post_id: 99, original_post_id: 42 });
  assert.deepEqual(await forum.sharePostWithEdit(42, { caption: 'Caption' }), { post_id: 99, original_post_id: 42 });
  assert.equal(requests.at(-1).url, '/posts/42/shares');
  assert.deepEqual(body(), { caption: 'Caption' });
});

test('memberships send desired state idempotently and accept empty 204 responses', async () => {
  reset();
  for (const [call, resource] of [[forum.togglePostLike, 'likes'], [forum.toggleBookmark, 'bookmarks']]) {
    for (const desired of [true, true, false, false]) {
      assert.equal(await call(42, desired), undefined);
      assert.equal(requests.at(-1).method, desired ? 'put' : 'delete');
      assert.equal(requests.at(-1).url, `/posts/42/${resource}/me`);
    }
  }
  await profile.followUser('user-id');
  assert.equal(requests.at(-1).method, 'put');
  assert.equal(requests.at(-1).url, '/users/user-id/followers/me');
  assert.equal(await profile.unfollowUser('user-id'), undefined);
  assert.equal(requests.at(-1).method, 'delete');
  assert.equal(requests.at(-1).url, '/users/user-id/followers/me');
  assert.equal(await profile.deleteReadNotification(7), undefined);
  assert.equal(await forum.deletePost(42), undefined);
  await auth.logout();
  assert.equal(requests.at(-1).url, '/auth/logout');
  assert.equal(localStorage.getItem('access_token'), null);
});

test('profile, notification and moderation clients preserve omitted PATCH fields', async () => {
  reset();
  for (const [call, method, url] of [
    [() => profile.getMyProfile(), 'get', '/users/me'],
    [() => profile.getUserProfile('student name'), 'get', '/users/by-username/student%20name'],
    [() => profile.getUserPosts('student'), 'get', '/users/by-username/student/posts'],
    [() => profile.getUserComments('student'), 'get', '/users/by-username/student/comments'],
    [() => profile.getUserBookmarks(), 'get', '/users/me/bookmarks'],
    [() => profile.getMyNotifications(true), 'get', '/notifications'],
    [() => profile.markNotificationRead(7), 'put', '/notifications/7/read'],
    [() => admin.getAdminOverview(), 'get', '/admin/analytics/overview'],
    [() => admin.getAdminUsers({}), 'get', '/admin/users'],
    [() => admin.getAdminReports({}), 'get', '/admin/reports'],
    [() => admin.getPendingPosts({}), 'get', '/admin/posts/pending'],
  ]) {
    await call();
    assert.equal(requests.at(-1).method, method);
    assert.equal(requests.at(-1).url, url);
  }
  await profile.updateMyProfile({ bio: null });
  assert.equal(requests.at(-2).method, 'patch');
  assert.equal(requests.at(-2).url, '/users/me');
  assert.deepEqual(body(requests.at(-2)), { bio: null });
  assert.equal(requests.at(-1).url, '/auth/me', 'Identity stays separate from rich profile');
  await admin.banUser('user-id', 'spam');
  assert.equal(requests.at(-1).method, 'put');
  assert.deepEqual(body(), { reason: 'spam' });
  await admin.unbanUser('user-id', 'appeal');
  assert.equal(requests.at(-1).method, 'delete');
  assert.equal(requests.at(-1).url, '/admin/users/user-id/ban');
  assert.deepEqual(requests.at(-1).params, { reason: 'appeal' });
  await admin.approvePost(42);
  assert.equal(requests.at(-1).method, 'put');
  assert.equal(requests.at(-1).url, '/admin/posts/42/moderation');
  assert.deepEqual(body(), { status: 'active' });
  await admin.rejectPost(42);
  assert.deepEqual(body(), { status: 'rejected' });
  await admin.moderateReport(3, { status: 'resolved', action: 'hide_post', notes: 'spam' });
  assert.equal(requests.at(-1).method, 'put');
  assert.equal(requests.at(-1).url, '/admin/reports/3/moderation');
  assert.deepEqual(body(), { status: 'resolved', action: 'hide_post', notes: 'spam' });
});

test('anonymous auth requests carry no bearer and never trigger token refresh', async () => {
  reset();
  for (const name of ['login', 'register', 'refresh', 'logout', 'forgot-password', 'reset-password', 'verify-email', 'resend-verification']) {
    reply = (config) => { throw problem(config); };
    const before = requests.length;
    await assert.rejects(auth.api.post(`/auth/${name}`, { token: 'invalid' }));
    assert.equal(requests.length, before + 1);
    assert.equal(requests.at(-1).headers.get('Authorization'), undefined);
    assert.equal(auth.getAccessToken(), 'access-old', 'Invalid login does not destroy an existing session');
  }
  reply = undefined;
  assert.equal((await auth.api.post('/auth/forgot-password', { email: identity.email })).status, 202);
  await auth.api.put('/users/me/profile-completion', { username: 'student', full_name: 'Student' });
  assert.equal(requests.at(-1).headers.get('Authorization'), 'Bearer access-old');
});

test('private 401 retries once with rotated tokens; failed refresh clears session', async () => {
  reset();
  reply = (config) => {
    if (config.url === '/auth/refresh') {
      assert.equal(config.headers.get('Authorization'), undefined);
      assert.deepEqual(body(config), { refresh_token: 'refresh-token' });
      return { data: { ...tokens, access_token: 'access-new' } };
    }
    if (config.headers.get('Authorization') === 'Bearer access-old') throw problem(config);
    return { data: identity };
  };
  assert.deepEqual(await auth.fetchCurrentUser(), identity);
  assert.deepEqual(requests.map((r) => r.url), ['/auth/me', '/auth/refresh', '/auth/me']);
  assert.equal(requests.at(-1).headers.get('Authorization'), 'Bearer access-new');
  reset();
  reply = (config) => { throw problem(config); };
  await assert.rejects(auth.fetchCurrentUser());
  assert.deepEqual(requests.map((r) => r.url), ['/auth/me', '/auth/refresh']);
  assert.equal(auth.getAccessToken(), null);
});

test('RFC 9457 errors retain detail and validation extension', async () => {
  reset();
  const errors = [{ loc: ['body', 'title'], msg: 'Too short', type: 'string_too_short' }];
  reply = (config) => {
    const error = problem(config, 422);
    error.response.data.errors = errors;
    error.response.data.detail = 'Request validation failed.';
    throw error;
  };
  await assert.rejects(forum.createPost({ title: '', content: '', tags: [] }), (error) => {
    assert.equal(auth.getErrorDetail(error, 'fallback'), 'Request validation failed.');
    assert.deepEqual(error.response.data.errors, errors);
    assert.equal(error.response.headers['content-type'], 'application/problem+json');
    return true;
  });
  assert.equal(requests.length, 1);
});

test('image upload sends authenticated multipart file and returns server URL', async () => {
  reset();
  reply = () => ({ data: { url: 'https://api.example.test/uploads/image.png' } });
  const file = new File(['png'], 'image.png', { type: 'image/png' });
  assert.equal(await media.uploadImage(file), 'https://api.example.test/uploads/image.png');
  const request = requests.at(-1);
  assert.equal(request.method, 'post');
  assert.equal(request.url, '/media/images');
  assert.equal(request.headers.get('Authorization'), 'Bearer access-old');
  assert.ok(request.data instanceof FormData);
  assert.equal(request.data.get('file').name, 'image.png');
  assert.notEqual(request.headers.get('Content-Type'), 'application/json');
  await assert.rejects(media.uploadImage(new File(['gif'], 'image.gif', { type: 'image/gif' })), /JPEG or PNG/);
  await assert.rejects(media.uploadImage(new File([new Uint8Array(5 * 1024 * 1024 + 1)], 'large.png', { type: 'image/png' })), /5 MiB/);
  assert.equal(requests.length, 1);
});

function componentHarness(file, initialState, additionalMocks = {}) {
  const states = [...initialState];
  let index = 0;
  let effects = [];
  const hooks = {
    useState(value) {
      const slot = index++;
      if (!(slot in states)) states[slot] = typeof value === 'function' ? value() : value;
      return [states[slot], (next) => { states[slot] = typeof next === 'function' ? next(states[slot]) : next; }];
    },
    useRef(value) {
      const slot = index++;
      return states[slot] ??= { current: value };
    },
    useMemo: (fn) => fn(),
    useCallback: (fn) => fn,
    useEffect: (fn) => effects.push(fn),
    startTransition: (fn) => fn(),
  };
  const component = loader({
    __components: true,
    react: hooks,
    'next/link': { __esModule: true, default: () => null },
    'next/navigation': { useRouter: () => ({}), useParams: () => ({ id: '42' }) },
    '@/lib/axios': auth,
    '@/lib/forumApi': forum,
    '@/lib/profileApi': profile,
    '@/lib/i18n': { useI18n: () => ({ t: (key) => key }) },
    '@/lib/useAuthGuard': { useAuthGuard: () => ({ isCheckingAuth: false }) },
    '@/lib/useResponsiveSidebar': { useResponsiveSidebar: () => ({}) },
    '@/components/ui/Toast': { useToast: () => ({ pushToast() {} }) },
    ...additionalMocks,
  })(file).default;
  return {
    render(props = {}) {
      index = 0;
      effects = [];
      return component(props);
    },
    get effects() { return effects; },
  };
}

function findProps(node, predicate) {
  if (!node || typeof node !== 'object') return;
  if (node.props && predicate(node.props)) return node.props;
  const children = Array.isArray(node) ? node : node.props?.children;
  for (const child of [children].flat(Infinity)) {
    const found = findProps(child, predicate);
    if (found) return found;
  }
}

const postFixture = { id: 42, authorId: 'author', title: 'Title', content: 'Body', tags: [], image: '', createdAt: '2026-01-01T00:00:00Z', likes: 1, comments: 0, shares: 0, views: 0, trendingScore: 0 };
const authorFixture = { id: 'author', username: 'author', name: 'Author' };

test('feed optimistic callbacks send the new liked and bookmarked states', async () => {
  reset();
  for (const initiallySelected of [false, true]) {
    const state = [ [postFixture], { author: authorFixture }, [], false, '', 'for-you', null, 'latest', 4, false,
      initiallySelected ? [42] : [], initiallySelected ? [42] : [] ];
    const harness = componentHarness('components/post/PostList.tsx', state);
    let actions = findProps(harness.render(), (props) => props.post?.id === 42 && props.onLikeToggle);
    assert.equal(actions.onLikeToggle(42), !initiallySelected);
    assert.equal(actions.onBookmarkToggle(42), !initiallySelected);
    await new Promise(setImmediate);
    assert.deepEqual(requests.slice(-2).map((r) => [r.method, r.url]), [
      [initiallySelected ? 'delete' : 'put', '/posts/42/likes/me'],
      [initiallySelected ? 'delete' : 'put', '/posts/42/bookmarks/me'],
    ]);
    actions = findProps(harness.render(), (props) => props.post?.id === 42 && props.onLikeToggle);
    assert.equal(actions.liked, !initiallySelected);
    assert.equal(actions.bookmarked, !initiallySelected);
  }
});

test('detail callbacks send desired state and record one view per mount', async () => {
  reset();
  for (const initiallySelected of [false, true]) {
    const state = ['', false, '', postFixture, authorFixture, [], initiallySelected, initiallySelected, { id: 'viewer' }];
    const harness = componentHarness('app/post/[id]/page.tsx', state);
    const actions = findProps(harness.render(), (props) => props.post?.id === 42 && props.onLikeToggle);
    harness.effects[0]();
    harness.render();
    harness.effects[0]();
    await new Promise(setImmediate);
    assert.equal(requests.filter((r) => r.url.endsWith('/views')).length, initiallySelected ? 2 : 1);
    actions.onLikeToggle(42);
    actions.onBookmarkToggle(42);
    await new Promise(setImmediate);
    assert.deepEqual(requests.slice(-2).map((r) => [r.method, r.url]), [
      [initiallySelected ? 'delete' : 'put', '/posts/42/likes/me'],
      [initiallySelected ? 'delete' : 'put', '/posts/42/bookmarks/me'],
    ]);
  }
});

test('follow button accepts unfollow 204 and passes intended state to parent', async () => {
  reset();
  for (const isFollowing of [false, true]) {
    let changed;
    const harness = componentHarness('components/profile/FollowButton.tsx', []);
    const button = findProps(harness.render({ userId: 'author', isFollowing, onToggle: (value) => { changed = value; } }), (props) => props.onClick);
    await button.onClick();
    assert.equal(changed, !isFollowing);
    assert.equal(requests.at(-1).method, isFollowing ? 'delete' : 'put');
    assert.equal(requests.at(-1).url, '/users/author/followers/me');
  }
});

test('public author type contains exactly the frozen fields and permits null username', () => {
  const source = ts.createSourceFile('forumApi.ts', fs.readFileSync(path.resolve(root, 'lib/forumApi.ts'), 'utf8'), ts.ScriptTarget.Latest, true);
  const author = source.statements.find((node) => ts.isTypeAliasDeclaration(node) && node.name.text === 'ApiAuthor');
  assert.deepEqual(author.type.members.map((member) => member.name.text).sort(), [...contract.conventions.public_author_fields].sort());
  const username = author.type.members.find((member) => member.name.text === 'username');
  assert.equal(username.type.getText(source), 'string | null');
});

test('every direct API call uses a frozen method and relative v1 resource path', () => {
  let checked = 0;
  for (const folder of ['app', 'components', 'lib']) {
    for (const file of fs.readdirSync(path.resolve(root, folder), { recursive: true })) {
      if (!/\.tsx?$/.test(file)) continue;
      const source = ts.createSourceFile(file, fs.readFileSync(path.resolve(root, folder, file), 'utf8'), ts.ScriptTarget.Latest, true);
      function visit(node) {
        if (ts.isCallExpression(node) && ts.isPropertyAccessExpression(node.expression)
            && node.expression.expression.getText(source) === 'api'
            && ['get', 'post', 'put', 'patch', 'delete'].includes(node.expression.name.text)) {
          const argument = node.arguments[0];
          const url = ts.isTemplateExpression(argument)
            ? argument.head.text + argument.templateSpans.map((span) => `{value}${span.literal.text}`).join('')
            : argument.text;
          assert.ok(typeof url === 'string' && url.startsWith('/') && !url.startsWith('/api/'), `${file}: relative resource URL required`);
          const method = node.expression.name.text.toUpperCase();
          assert.ok(contract.endpoints.some((entry) => entry.method === method
            && new RegExp(`^${entry.path.replace(/\{[^}]+\}/g, '[^/]+')}$`).test(`/api/v1${url}`)), `${file}: ${method} ${url} absent from frozen contract`);
          checked++;
        }
        ts.forEachChild(node, visit);
      }
      visit(source);
    }
  }
  assert.ok(checked >= 50, 'Sweep covers clients and direct auth consumers');
});

test('OAuth next target permits local paths and rejects external navigation', () => {
  const { getLocalRedirectPath } = load('lib/authRedirect.ts');
  for (const target of ['/feed', '/post/42?tab=comments#reply']) assert.equal(getLocalRedirectPath(target), target);
  for (const target of [null, '', '//evil.test', 'https://evil.test', 'javascript:alert(1)', '/\\evil.test', '\\evil.test', '/%2fevil.test', '/%5cevil.test', '/\nevil.test', '/%']) {
    assert.equal(getLocalRedirectPath(target), '/feed');
  }
});
