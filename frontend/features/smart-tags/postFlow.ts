import type { ApiPost } from '@/lib/forumApi';
import type { EditorPostDraft } from '@/lib/types';

/** Preserve the original Create / Edit request payload and moderation semantics. */
export function toPostWritePayload(draft: EditorPostDraft) {
  return {
    title: draft.title,
    content: draft.content,
    cover_image: draft.image,
    tags: draft.tags,
  };
}

/** Restore both approved and pending new tags to avoid removing a request on edit. */
export function toEditDraft(post: Pick<ApiPost, 'title' | 'content' | 'tags' | 'requested_new_tags' | 'cover_image'>): EditorPostDraft {
  return {
    title: post.title,
    content: post.content,
    tags: Array.from(new Set(
      [...post.tags, ...(post.requested_new_tags ?? [])]
        .map((tag) => tag.trim().replace(/^#+/, '').trim().toLocaleLowerCase())
        .filter(Boolean),
    )),
    image: post.cover_image || '',
  };
}
