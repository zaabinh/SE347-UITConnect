import { NextRequest, NextResponse } from 'next/server';
import {
  isSuggestionReady,
  parseTagSuggestions,
  rankExistingTags,
  TAG_SUGGESTION_LIMIT,
} from '@/features/smart-tags/tagLogic';

export const dynamic = 'force-dynamic';

const headers = { 'Cache-Control': 'no-store' };

function backendUrl(path: string) {
  const base = process.env.NEXT_PUBLIC_API_URL;
  if (!base) throw new Error('NEXT_PUBLIC_API_URL is not configured');
  const url = new URL(base);
  if (!['http:', 'https:'].includes(url.protocol)) throw new Error('Invalid backend URL');
  return new URL(path, url.origin).toString();
}

/**
 * New POST /api/fe/tag-suggestions endpoint. Requires the caller's bearer token.
 * By default it provides deterministic suggestions from the existing tags API.
 * If TAG_SUGGESTIONS_UPSTREAM_PATH is defined, it forwards the payload to the
 * team's new backend endpoint; frontend still falls back on failures.
 */
export async function POST(request: NextRequest) {
  let input: unknown;
  try {
    input = await request.json();
  } catch {
    return NextResponse.json({ error: 'Invalid JSON' }, { status: 400, headers });
  }

  if (!input || typeof input !== 'object') {
    return NextResponse.json({ error: 'Invalid payload' }, { status: 400, headers });
  }
  const { title, content } = input as { title?: unknown; content?: unknown };
  if (typeof title !== 'string' || typeof content !== 'string' ||
      title.length > 255 || content.length > 15000 || !isSuggestionReady(title, content)) {
    return NextResponse.json({ error: 'Title or content is missing, too short or too long' }, { status: 400, headers });
  }

  const bearer = request.headers.get('authorization');
  if (!bearer || !/^Bearer \S+$/.test(bearer)) {
    return NextResponse.json({ error: 'Authentication required' }, { status: 401, headers });
  }

  const upstreamPath = process.env.TAG_SUGGESTIONS_UPSTREAM_PATH;
  if (upstreamPath && !/^\/api\/posts\/[a-zA-Z0-9_/-]+$/.test(upstreamPath)) {
    return NextResponse.json({ error: 'Invalid upstream configuration' }, { status: 503, headers });
  }

  try {
    const requestHeaders = { Authorization: bearer, 'Content-Type': 'application/json' };
    if (upstreamPath) {
      const response = await fetch(backendUrl(upstreamPath), {
        method: 'POST',
        headers: requestHeaders,
        body: JSON.stringify({ title: title.trim(), content: content.trim(), limit: TAG_SUGGESTION_LIMIT }),
        signal: AbortSignal.timeout(4500),
        cache: 'no-store',
      });
      if (!response.ok) throw new Error('Upstream suggestions not available');
      const tags = parseTagSuggestions(await response.json());
      return NextResponse.json({ tags: tags.slice(0, TAG_SUGGESTION_LIMIT), source: 'backend' }, { headers });
    }

    const response = await fetch(backendUrl('/api/posts/tags'), {
      headers: { Authorization: bearer },
      signal: AbortSignal.timeout(4500),
      cache: 'no-store',
    });
    if (!response.ok) throw new Error('Existing tags unavailable');
    const tags = parseTagSuggestions(await response.json());
    return NextResponse.json({
      tags: rankExistingTags(title, content, tags, [], TAG_SUGGESTION_LIMIT),
      source: 'existing-tags',
    }, { headers });
  } catch {
    // Do not include auth tokens, backend URLs or internal error messages in responses.
    return NextResponse.json({ error: 'Tag suggestions temporarily unavailable' }, { status: 503, headers });
  }
}
