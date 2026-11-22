'use client';

import { useParams, useRouter } from 'next/navigation';
import { useEffect, useState } from 'react';
import Sidebar from '@/components/layout/Sidebar';
import Topbar from '@/components/layout/Topbar';
import Modal from '@/components/ui/Modal';
import { useToast } from '@/components/ui/Toast';
import SmartPostEditor from '@/features/smart-tags/SmartPostEditor';
import { toEditDraft, toPostWritePayload } from '@/features/smart-tags/postFlow';
import { fetchCurrentUser } from '@/lib/axios';
import { deletePost, getPost, updatePost } from '@/lib/forumApi';
import type { EditorPostDraft } from '@/lib/types';
import { useAuthGuard } from '@/lib/useAuthGuard';
import { useResponsiveSidebar } from '@/lib/useResponsiveSidebar';

/** Same edit/delete/owner restrictions; retains tags pending moderation on edit. */
export default function NaEditPostPage() {
  const params = useParams<{ id: string }>();
  const router = useRouter();
  const { pushToast } = useToast();
  const { isCheckingAuth, userEmail } = useAuthGuard();
  const { isSidebarCollapsed, isMobileSidebarOpen, setIsSidebarCollapsed, setIsMobileSidebarOpen } = useResponsiveSidebar();
  const [searchQuery, setSearchQuery] = useState('');
  const [isDeleteOpen, setIsDeleteOpen] = useState(false);
  const [loading, setLoading] = useState(true);
  const [post, setPost] = useState<EditorPostDraft | null>(null);
  const [postId, setPostId] = useState<number | null>(null);

  useEffect(() => {
    let mounted = true;
    const load = async () => {
      setLoading(true);
      try {
        const id = Number(params.id);
        if (!Number.isSafeInteger(id) || id < 1) throw new Error('Invalid post ID');
        const [postData, currentUser] = await Promise.all([getPost(id), fetchCurrentUser()]);
        if (!mounted) return;
        if (postData.user_id !== currentUser.id) {
          router.replace('/feed');
          return;
        }
        setPostId(postData.id);
        setPost(toEditDraft(postData));
      } catch {
        if (mounted) router.replace('/feed');
      } finally {
        if (mounted) setLoading(false);
      }
    };
    void load();
    return () => { mounted = false; };
  }, [params.id, router]);

  if (isCheckingAuth || loading) {
    return (
      <main className="flex min-h-screen items-center justify-center bg-slate-100">
        <div className="rounded-2xl bg-white px-5 py-4 text-sm text-slate-700 shadow-card">Loading editor...</div>
      </main>
    );
  }
  if (!post || postId === null) return null;
  const sidebarOffsetClass = isSidebarCollapsed ? 'md:ml-16' : 'md:ml-60';
  return (
    <main className="min-h-screen bg-slate-100">
      <Sidebar isCollapsed={isSidebarCollapsed} isMobileOpen={isMobileSidebarOpen}
        onCloseMobile={() => setIsMobileSidebarOpen(false)}
        onToggleCollapse={() => setIsSidebarCollapsed((prev) => !prev)} />
      <Topbar isSidebarCollapsed={isSidebarCollapsed} onOpenMobileSidebar={() => setIsMobileSidebarOpen(true)}
        userEmail={userEmail} searchQuery={searchQuery} onSearchChange={setSearchQuery} />
      <div className={`px-4 py-6 transition-all duration-200 ${sidebarOffsetClass}`}>
        <div className="mx-auto max-w-[1500px] space-y-5">
          <div>
            <h1 className="text-3xl font-bold text-slate-900">Edit post</h1>
            <p className="mt-2 text-sm text-slate-600">Update your content, tags, and cover image.</p>
          </div>
          <SmartPostEditor mode="edit" initialValue={post}
            onSubmit={async (draft) => {
              try {
                await updatePost(postId, toPostWritePayload(draft));
                pushToast('Post updated');
                router.push(`/post/${postId}`);
              } catch {
                pushToast('Failed to update post');
              }
            }} onDelete={() => setIsDeleteOpen(true)} />
        </div>
      </div>
      <Modal open={isDeleteOpen} title="Delete this post?"
        description="This removes the post from the forum." confirmLabel="Delete post"
        onCancel={() => setIsDeleteOpen(false)}
        onConfirm={async () => {
          try {
            await deletePost(postId);
            pushToast('Post deleted');
            router.push('/feed');
          } catch {
            pushToast('Failed to delete post');
          }
        }} />
    </main>
  );
}
