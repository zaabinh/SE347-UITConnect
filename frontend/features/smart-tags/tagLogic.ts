/** Pure tag utilities shared by the client fallback and the Next.js BFF. */
export const TAG_SUGGESTION_LIMIT = 8;
export const MIN_TITLE_LENGTH = 5;
export const MIN_CONTENT_LENGTH = 20;
export const TAG_DEBOUNCE_MS = 700;

export function normalizeTag(tag: string): string {
  return tag.trim().replace(/^#+/, '').trim().toLocaleLowerCase();
}

export function uniqueTags(tags: readonly string[]): string[] {
  const result: string[] = [];
  const seen = new Set<string>();
  for (const tag of tags) {
    if (typeof tag !== 'string') continue;
    const normalized = normalizeTag(tag);
    if (!normalized || seen.has(normalized)) continue;
    seen.add(normalized);
    result.push(normalized);
  }
  return result;
}

export function isSuggestionReady(title: string, content: string): boolean {
  return title.trim().length >= MIN_TITLE_LENGTH && content.trim().length >= MIN_CONTENT_LENGTH;
}

export function filterSuggestedTags(
  suggestions: readonly string[],
  selected: readonly string[],
  limit: number = TAG_SUGGESTION_LIMIT,
): string[] {
  const selectedSet = new Set(uniqueTags(selected));
  return uniqueTags(suggestions).filter((tag) => !selectedSet.has(tag)).slice(0, Math.max(0, limit));
}

/**
 * Rank ONLY approved/existing tags by relevance to the user's writing.
 * This is a deterministic, lexical baseline (not an AI model).
 */
export function rankExistingTags(
  title: string,
  content: string,
  existingTags: readonly string[],
  interestTags: readonly string[] = [],
  limit: number = TAG_SUGGESTION_LIMIT,
): string[] {
  const titleText = title.toLocaleLowerCase();
  const contentText = content.toLocaleLowerCase();
  const titleTerms = new Set(titleText.match(/[\p{L}\p{N}]+/gu) ?? []);
  const contentTerms = new Set(contentText.match(/[\p{L}\p{N}]+/gu) ?? []);
  const preferred = new Set(uniqueTags(interestTags));

  return uniqueTags(existingTags)
    .map((tag, index) => {
      const words = tag.match(/[\p{L}\p{N}]+/gu) ?? [];
      let score = 0;
      if (titleText.includes(tag)) score += 12;
      if (contentText.includes(tag)) score += 7;
      for (const word of words) {
        if (word.length < 2) continue;
        if (titleTerms.has(word)) score += 4;
        if (contentTerms.has(word)) score += 2;
      }
      if (preferred.has(tag)) score += 1;
      return { tag, score, index };
    })
    .filter((item) => item.score > 0)
    .sort((a, b) => b.score - a.score || a.index - b.index)
    .slice(0, Math.max(0, limit))
    .map((item) => item.tag);
}

/** Accept the backend forms { tags: [...] }, { suggestions: [...] }, or an array. */
export function parseTagSuggestions(payload: unknown): string[] {
  const value = payload && typeof payload === 'object' && !Array.isArray(payload)
    ? (payload as { suggestions?: unknown; tags?: unknown }).suggestions ??
      (payload as { tags?: unknown }).tags
    : payload;
  if (!Array.isArray(value)) throw new Error('Invalid tag suggestions response');
  const names = value.map((item) => {
    if (typeof item === 'string') return item;
    if (item && typeof item === 'object') {
      const name = (item as { name?: unknown; tag?: unknown }).name ?? (item as { tag?: unknown }).tag;
      return typeof name === 'string' ? name : '';
    }
    return '';
  });
  return uniqueTags(names);
}
