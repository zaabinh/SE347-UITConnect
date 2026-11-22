/**
 * Testable cancellation/debounce primitive, with no React dependency.
 * On every edit, a pending timer and the in-flight request are invalidated.
 * Late responses are ignored even when an upstream ignores AbortSignal.
 */
export type SuggestionQuery = { title: string; content: string };
export type SuggestionLoader<T> = (query: SuggestionQuery, signal: AbortSignal) => Promise<T>;
export type SuggestionCallbacks<T> = {
  waiting: (query: SuggestionQuery) => void;
  loading: (query: SuggestionQuery) => void;
  result: (query: SuggestionQuery, data: T) => void;
  error: (query: SuggestionQuery, reason: unknown) => void;
};

export function createDebouncedRequestController<T>(
  loader: SuggestionLoader<T>,
  callbacks: SuggestionCallbacks<T>,
  delayMs = 700,
) {
  let generation = 0;
  let timer: ReturnType<typeof setTimeout> | null = null;
  let controller: AbortController | null = null;
  let disposed = false;

  const cancel = () => {
    generation += 1;
    if (timer !== null) clearTimeout(timer);
    timer = null;
    controller?.abort();
    controller = null;
  };

  const schedule = (query: SuggestionQuery) => {
    cancel();
    if (disposed) return;
    const version = generation;
    callbacks.waiting(query);
    timer = setTimeout(async () => {
      timer = null;
      if (disposed || version !== generation) return;
      const current = new AbortController();
      controller = current;
      callbacks.loading(query);
      try {
        const output = await loader(query, current.signal);
        if (!disposed && version === generation && !current.signal.aborted) {
          callbacks.result(query, output);
        }
      } catch (reason) {
        if (!disposed && version === generation && !current.signal.aborted) {
          callbacks.error(query, reason);
        }
      } finally {
        if (controller === current) controller = null;
      }
    }, delayMs);
  };

  const dispose = () => {
    disposed = true;
    cancel();
  };

  return { schedule, cancel, dispose };
}
