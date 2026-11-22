'use client';

import { useEffect, useRef, useState } from 'react';
import { fetchTagSuggestions } from './suggestionsApi';
import { createDebouncedRequestController } from './requestController';
import {
  isSuggestionReady,
  rankExistingTags,
  TAG_DEBOUNCE_MS,
} from './tagLogic';

type SuggestionStatus = 'idle' | 'waiting' | 'loading' | 'ready' | 'empty' | 'fallback' | 'error';
type SuggestionState = { status: SuggestionStatus; tags: string[]; message: string };
const initial: SuggestionState = { status: 'idle', tags: [], message: '' };

/**
 * Keeps selection changes out of request scheduling. The UI filters chosen tags
 * separately so selecting a tag does not trigger another network request.
 */
export function useSmartTagSuggestions(
  title: string,
  content: string,
  catalog: readonly string[],
  interestTags: readonly string[],
) {
  const [state, setState] = useState<SuggestionState>(initial);
  const [retryCount, setRetryCount] = useState(0);
  const knownRef = useRef(catalog);
  const interestsRef = useRef(interestTags);
  knownRef.current = catalog;
  interestsRef.current = interestTags;

  const managerRef = useRef<ReturnType<typeof createDebouncedRequestController<string[]>> | null>(null);
  if (!managerRef.current) {
    managerRef.current = createDebouncedRequestController(fetchTagSuggestions, {
      waiting: () => setState({ status: 'waiting', tags: [], message: '' }),
      loading: () => setState({ status: 'loading', tags: [], message: '' }),
      result: (_query, tags) => setState({
        status: tags.length ? 'ready' : 'empty',
        tags,
        message: '',
      }),
      error: (query) => {
        const local = rankExistingTags(query.title, query.content, knownRef.current, interestsRef.current);
        setState(local.length
          ? { status: 'fallback', tags: local, message: 'The suggestion service is unavailable. Showing matches from existing tags.' }
          : { status: 'error', tags: [], message: 'Suggestions are unavailable. You can still search or enter a tag manually.' });
      },
    }, TAG_DEBOUNCE_MS);
  }

  useEffect(() => {
    const manager = managerRef.current;
    if (!manager) return;
    if (!isSuggestionReady(title, content)) {
      manager.cancel();
      setState(initial);
    } else {
      manager.schedule({ title: title.trim(), content: content.trim() });
    }
    return () => manager.cancel();
  }, [title, content, retryCount]);

  // The scheduling effect cancels on unmount. Avoid disposing this ref here:
  // React StrictMode replays effects during development without recreating refs.

  // The catalog can finish loading after an API error; recover to client
  // fallback without requiring another keystroke or an explicit retry.
  useEffect(() => {
    if (state.status !== 'error' || !isSuggestionReady(title, content)) return;
    const local = rankExistingTags(title, content, catalog, interestTags);
    if (local.length) {
      setState({
        status: 'fallback', tags: local,
        message: 'The suggestion service is unavailable. Showing matches from existing tags.',
      });
    }
  }, [catalog, interestTags, state.status, title, content]);

  return {
    ...state,
    retry: () => setRetryCount((count) => count + 1),
  };
}
