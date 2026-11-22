'use client';

import { useEffect, useMemo, useState } from 'react';
import Tag from '@/components/ui/Tag';
import Button from '@/components/ui/Button';
import { getStoredUser } from '@/lib/axios';
import { getTags } from '@/lib/forumApi';
import {
  filterSuggestedTags,
  isSuggestionReady,
  normalizeTag,
  uniqueTags,
} from './tagLogic';
import { useSmartTagSuggestions } from './useSmartTagSuggestions';

type Props = {
  title: string;
  content: string;
  selectedTags: string[];
  onChange: (tags: string[]) => void;
};

export default function SmartTagPicker({ title, content, selectedTags, onChange }: Props) {
  const [search, setSearch] = useState('');
  const [dbTags, setDbTags] = useState<string[]>([]);
  const [catalogStatus, setCatalogStatus] = useState<'loading' | 'ready' | 'error'>('loading');
  const [interests] = useState<string[]>(() =>
    typeof window === 'undefined' ? [] : uniqueTags(getStoredUser()?.interest_tags ?? []));

  useEffect(() => {
    let alive = true;
    getTags()
      .then((items) => {
        if (!alive) return;
        setDbTags(uniqueTags(items.map((tag) => tag.name)));
        setCatalogStatus('ready');
      })
      .catch(() => {
        if (!alive) return;
        setCatalogStatus('error');
      });
    return () => { alive = false; };
  }, []);

  const suggestion = useSmartTagSuggestions(title, content, dbTags, interests);
  const selected = useMemo(() => uniqueTags(selectedTags), [selectedTags]);
  const suggested = useMemo(
    () => filterSuggestedTags(suggestion.tags, selected),
    [suggestion.tags, selected],
  );
  const existingMatches = useMemo(() => {
    const query = normalizeTag(search);
    const selectedSet = new Set(selected);
    const interestSet = new Set(interests);
    return dbTags
      .filter((tag) => !selectedSet.has(tag) && (!query || tag.includes(query)))
      .sort((a, b) => Number(interestSet.has(b)) - Number(interestSet.has(a)) || a.localeCompare(b))
      .slice(0, 10);
  }, [dbTags, search, selected, interests]);

  const addTag = (tag: string) => {
    const normalized = normalizeTag(tag);
    if (!normalized || selected.includes(normalized)) return;
    onChange([...selected, normalized]);
    setSearch('');
  };
  const removeTag = (tag: string) => onChange(selected.filter((item) => item !== tag));
  const query = normalizeTag(search);
  const isNewTag = !!query && !dbTags.includes(query) && !selected.includes(query);

  return (
    <div className="space-y-4" aria-label="Post tags">
      <div>
        <p className="text-sm font-semibold text-slate-700">Selected tags</p>
        <div className="mt-2 flex flex-wrap gap-2" aria-live="polite">
          {selected.length ? selected.map((tag) => (
            <button key={tag} type="button" onClick={() => removeTag(tag)}
              aria-label={`Remove tag ${tag}`}
              className="rounded-full border border-uit-200 bg-uit-50 px-3 py-1.5 text-xs font-semibold text-uit-700 hover:bg-uit-100">
              #{tag} <span aria-hidden="true">×</span>
            </button>
          )) : <span className="text-sm text-slate-400">No tags selected. Recommendations are optional.</span>}
        </div>
      </div>

      <div className="rounded-[24px] border border-sky-200 bg-sky-50/60 p-4">
        <div className="flex flex-wrap items-start justify-between gap-2">
          <div>
            <p className="text-xs font-semibold uppercase tracking-[0.15em] text-sky-800">Suggested for this post</p>
            <p className="mt-1 text-xs text-slate-500">Based on your title and content. Click to add; nothing is attached automatically.</p>
          </div>
          {suggestion.status === 'error' || suggestion.status === 'fallback' ? (
            <Button type="button" variant="outline" onClick={suggestion.retry}>Retry</Button>
          ) : null}
        </div>
        <div className="mt-3 flex flex-wrap gap-2" aria-live="polite" aria-busy={suggestion.status === 'loading'}>
          {!isSuggestionReady(title, content) && <span className="text-sm text-slate-500">Enter a title (5+ characters) and content (20+ characters) to see suggestions.</span>}
          {suggestion.status === 'waiting' && <span className="text-sm text-slate-500">Preparing suggestions…</span>}
          {suggestion.status === 'loading' && <span role="status" className="text-sm text-slate-600">Loading suggestions…</span>}
          {(suggestion.status === 'ready' || suggestion.status === 'fallback') && (
            suggested.length
              ? suggested.map((tag) => <Tag key={`suggested-${tag}`} label={tag} onClick={() => addTag(tag)} />)
              : <span className="text-sm text-slate-500">All suggestions are selected. You can search for more below.</span>
          )}
          {suggestion.status === 'empty' && <span className="text-sm text-slate-500">No relevant existing tags were found.</span>}
          {suggestion.status === 'error' && <span role="alert" className="text-sm text-rose-700">{suggestion.message}</span>}
        </div>
        {suggestion.status === 'fallback' && <p role="status" className="mt-2 text-xs text-amber-700">{suggestion.message}</p>}
      </div>

      <div className="rounded-[24px] border border-slate-200 bg-slate-50/80 p-4">
        <p className="text-xs font-semibold uppercase tracking-[0.15em] text-slate-700">Search existing tags</p>
        <p className="mt-1 text-xs text-slate-500">Search approved tags or manually request a new tag for moderation.</p>
        <div className="mt-3 flex gap-2">
          <input
            value={search} onChange={(event) => setSearch(event.target.value)}
            onKeyDown={(event) => { if (event.key === 'Enter') { event.preventDefault(); addTag(search); } }}
            placeholder="Search or type a new tag"
            aria-label="Search or enter a tag"
            className="min-w-0 flex-1 rounded-2xl border border-slate-200 px-3 py-2.5 text-sm outline-none focus:border-forum-primary"
          />
          <Button type="button" variant="outline" onClick={() => addTag(search)} disabled={!query || selected.includes(query)}>
            Add tag
          </Button>
        </div>
        <div className="mt-3 flex flex-wrap gap-2" aria-live="polite">
          {existingMatches.map((tag) => <Tag key={`existing-${tag}`} label={tag} onClick={() => addTag(tag)} />)}
        </div>
        {catalogStatus === 'loading' && <p role="status" className="mt-2 text-xs text-slate-500">Loading available tags…</p>}
        {catalogStatus === 'error' && <p role="status" className="mt-2 text-xs text-amber-700">Existing tags could not be loaded. Manual tag entry still works.</p>}
        {catalogStatus === 'ready' && !existingMatches.length && (
          <p className="mt-2 text-xs text-slate-500">No matching approved tags. You may propose a new tag instead.</p>
        )}
        {catalogStatus === 'ready' && isNewTag && <p className="mt-2 text-xs text-amber-700">#{query} is not in the loaded tag catalog. If submitted as a new tag, it requires admin approval.</p>}
      </div>
    </div>
  );
}
