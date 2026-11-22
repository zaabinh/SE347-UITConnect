'use client';

import { useRouter } from 'next/navigation';
import { useState } from 'react';
import Sidebar from '@/components/layout/Sidebar';
import Topbar from '@/components/layout/Topbar';
import { useToast } from '@/components/ui/Toast';
import SmartPostEditor from '@/features/smart-tags/SmartPostEditor';
import { toPostWritePayload } from '@/features/smart-tags/postFlow';
import { createPost } from '@/lib/forumApi';
import { useAuthGuard } from '@/lib/useAuthGuard';
import { useResponsiveSidebar } from '@/lib/useResponsiveSidebar';

/** Same createPost payload + navigation as the original /create page. */
export default function NaCreatePostPage() {
  const router = useRouter();
  const { pushToast } = useToast();
  const { isCheckingAuth, userEmail } = useAuthGuard();
  const { isSidebarCollapsed, isMobileSidebarOpen, setIsSidebarCollapsed, setIsMobileSidebarOpen } = useResponsiveSidebar();
  const [searchQuery, setSearchQuery] = useState('');

  if (isCheckingAuth) {
    return (
      <main className="flex min-h-screen items-center justify-center bg-slate-100">
        <div className="rounded-2xl bg-white px-5 py-4 text-sm text-slate-700 shadow-card">Loading editor...</div>
      </main>
    );
  }
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
            <h1 className="text-3xl font-bold text-slate-900">Create post</h1>
            <p className="mt-2 text-sm text-slate-600">Draft a developer-focused post with image, tags, and preview.</p>
          </div>
          <SmartPostEditor mode="create" onSubmit={async (draft) => {
            try {
              const newPost = await createPost(toPostWritePayload(draft));
              pushToast(newPost.status === 'pending' ? 'Post submitted for moderation' : 'Post published');
              router.push(`/post/${newPost.id}`);
            } catch {
              pushToast('Failed to publish post');
            }
          }} />
        </div>
      </div>
    </main>
  );
}
