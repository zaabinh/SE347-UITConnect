'use client';

import { useRef, useState } from 'react';
import Image from 'next/image';
import Button from '@/components/ui/Button';
import Input from '@/components/ui/Input';
import Tag from '@/components/ui/Tag';
import type { EditorPostDraft } from '@/lib/types';
import SmartTagPicker from './SmartTagPicker';

type Props = {
  mode: 'create' | 'edit';
  initialValue?: EditorPostDraft;
  onSubmit: (draft: EditorPostDraft) => Promise<void> | void;
  onDelete?: () => void;
};

const EMPTY_DRAFT: EditorPostDraft = { title: '', content: '', tags: [], image: '' };

/** Add-only counterpart of the repository's PostEditor; keeps payload semantics. */
export default function SmartPostEditor({ mode, initialValue = EMPTY_DRAFT, onSubmit, onDelete }: Props) {
  const [draft, setDraft] = useState<EditorPostDraft>(initialValue);
  const [submitting, setSubmitting] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const titleError = draft.title.trim().length > 0 && draft.title.trim().length < 5
    ? 'Title must be at least 5 characters.' : '';

  const submit = async () => {
    if (submitting || draft.title.trim().length < 5 || !draft.content.trim()) return;
    setSubmitting(true);
    try { await onSubmit(draft); }
    finally { setSubmitting(false); }
  };

  return (
    <div className="grid gap-6 xl:grid-cols-[minmax(0,1fr)_380px]">
      <section className="card-surface p-6">
        <div className="space-y-5">
          <Input id="post-title" label="Title" value={draft.title}
            onChange={(event) => setDraft((prev) => ({ ...prev, title: event.target.value }))}
            placeholder="Write a strong headline" />
          {titleError && <p className="text-xs font-medium text-rose-600">{titleError}</p>}
          <label className="block space-y-2">
            <span className="text-sm font-medium text-slate-700">Content</span>
            <textarea
              value={draft.content}
              onChange={(event) => setDraft((prev) => ({ ...prev, content: event.target.value }))}
              placeholder="Share the problem, the decisions you made, and what others can learn from it."
              className="min-h-[320px] w-full rounded-2xl border border-slate-200 px-4 py-3 text-sm leading-7 text-slate-700 outline-none transition-all duration-200 focus:border-forum-primary"
            />
          </label>
          <div className="space-y-3">
            <span className="text-sm font-medium text-slate-700">Cover image</span>
            <div className="flex flex-wrap items-center gap-3">
              <Button type="button" variant="outline" onClick={() => fileInputRef.current?.click()}>Upload image</Button>
              <input
                ref={fileInputRef} type="file" accept="image/*" className="hidden" aria-label="Upload cover image"
                onChange={(event) => {
                  const file = event.target.files?.[0];
                  if (!file) return;
                  const reader = new FileReader();
                  reader.onload = () => {
                    if (typeof reader.result === 'string') {
                      setDraft((prev) => ({ ...prev, image: reader.result as string }));
                    }
                  };
                  reader.readAsDataURL(file);
                }}
              />
              <span className="text-xs text-slate-500">{draft.image ? 'Image ready' : 'Use a local file for preview'}</span>
            </div>
          </div>
          <SmartTagPicker
            title={draft.title} content={draft.content} selectedTags={draft.tags}
            onChange={(tags) => setDraft((prev) => ({ ...prev, tags }))}
          />
        </div>
        <div className="mt-6 flex flex-wrap justify-end gap-3 border-t border-slate-200 pt-5">
          {mode === 'edit' && onDelete ? (
            <Button type="button" variant="outline" className="border-rose-200 text-rose-500 hover:border-rose-300 hover:text-rose-600" onClick={onDelete}>
              Delete post
            </Button>
          ) : null}
          <Button type="button" onClick={() => void submit()} disabled={submitting || draft.title.trim().length < 5 || !draft.content.trim()}>
            {submitting ? 'Saving…' : mode === 'create' ? 'Publish post' : 'Save changes'}
          </Button>
        </div>
      </section>
      <aside className="card-surface p-6">
        <div className="flex items-center justify-between gap-3">
          <div>
            <h3 className="text-lg font-semibold text-slate-900">Preview post</h3>
            <p className="text-sm text-slate-500">Check the final reading experience before publishing.</p>
          </div>
          <span className="rounded-full bg-slate-100 px-3 py-1 text-xs font-semibold text-slate-600">Preview</span>
        </div>
        <div className="mt-5 space-y-4">
          <div className="flex flex-wrap gap-2">
            {draft.tags.length ? draft.tags.map((tag) => <Tag key={tag} label={tag} />)
              : <span className="text-sm text-slate-400">No tags yet</span>}
          </div>
          <h4 className="text-2xl font-bold leading-tight text-slate-900">{draft.title || 'Your post title will appear here'}</h4>
          {draft.image ? (
            <div className="relative h-52 overflow-hidden rounded-3xl border border-slate-200">
              <Image src={draft.image} alt="Preview" fill className="object-cover" />
            </div>
          ) : (
            <div className="flex h-52 items-center justify-center rounded-3xl border border-dashed border-slate-300 bg-slate-50 text-sm text-slate-400">
              Upload an image to preview it here
            </div>
          )}
          <div className="space-y-4 text-sm leading-7 text-slate-600">
            {(draft.content || 'Your content preview will appear here.').split('\n\n').map((paragraph, index) => (
              <p key={`${index}-${paragraph.slice(0, 20)}`}>{paragraph}</p>
            ))}
          </div>
        </div>
      </aside>
    </div>
  );
}
