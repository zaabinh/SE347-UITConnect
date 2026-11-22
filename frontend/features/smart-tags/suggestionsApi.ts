'use client';

import { getAccessToken } from '@/lib/axios';
import { parseTagSuggestions } from './tagLogic';
import type { SuggestionQuery } from './requestController';

const REQUEST_TIMEOUT_MS = 5000;

/** Calls the new same-origin suggestion endpoint without changing existing api client. */
export async function fetchTagSuggestions(query: SuggestionQuery, signal: AbortSignal): Promise<string[]> {
  const controller = new AbortController();
  const cancel = () => controller.abort();
  signal.addEventListener('abort', cancel, { once: true });
  const timeout = setTimeout(() => controller.abort(new Error('Tag suggestion timeout')), REQUEST_TIMEOUT_MS);
  try {
    if (signal.aborted) throw new Error('Request cancelled');
    const token = getAccessToken();
    if (!token) throw new Error('Not authenticated');
    const response = await fetch('/api/fe/tag-suggestions', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
      body: JSON.stringify(query),
      signal: controller.signal,
      cache: 'no-store',
    });
    if (!response.ok) throw new Error(`Suggestion service returned ${response.status}`);
    return parseTagSuggestions(await response.json());
  } finally {
    clearTimeout(timeout);
    signal.removeEventListener('abort', cancel);
  }
}
