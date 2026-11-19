'use client';

import { api } from '@/lib/axios';

export type ApiAuthor = {
  id: string;
  username: string | null;
  full_name: string;
  avatar_url: string | null;
  bio: string | null;
  role: string;
};

export type ApiPost = {
  id: number;
  user_id: string;
  title: string;
  content: string;
  cover_image: string | null;
  status: string | null;
  requested_new_tags?: string[];
  tags: string[];
  created_at: string;
  updated_at?: string | null;
  author: ApiAuthor;
  likes_count: number;
  comments_count: number;
  views_count: number;
  shares_count: number;
  trending_score: number;
  is_liked: boolean;
  is_bookmarked: boolean;
};

export type ApiComment = {
  id: number;
  post_id: number;
  user_id: string;
  parent_id: number | null;
  content: string;
  created_at: string;
  author: ApiAuthor;
  replies: ApiComment[];
};

export type FeedResponse = {
  items: ApiPost[];
  meta: {
    page: number;
    page_size: number;
    total: number;
    total_pages: number;
  };
};

export type SimilarPost = {
  post: ApiPost;
  similarity_score: number;
  similarity_reason: string;
};

export type SimilarPostsResponse = {
  items: SimilarPost[];
  meta: {
    page: number;
    page_size: number;
    total: number;
    total_pages: number;
  };
};

export type CollaborativePost = {
  post: ApiPost;
  cf_score: number;
  cf_reason: string;
  similar_user_count: number;
};

export type CollaborativePostsResponse = {
  items: CollaborativePost[];
  meta: {
    page: number;
    page_size: number;
    total: number;
    total_pages: number;
  };
};

export type ProfileBasedPost = {
  post: ApiPost;
  profile_score: number;
  recommendation_reason: string;
};

export type ProfileBasedPostsResponse = {
  items: ProfileBasedPost[];
  meta: {
    page: number;
    page_size: number;
    total: number;
    total_pages: number;
  };
};

export type UserProfileSummary = {
  interest_tags: string[];
  major: string;
  academic_year: string;
  career_goal: string;
  profile_strength: number;
  recommendations_count: number;
  profile_completeness: Record<string, boolean>;
};

export type ProfileAnalysis = {
  user_id: string;
  profile_summary: UserProfileSummary;
  recommendation_message: string;
};

export async function getFeed(params: {
  page?: number;
  pageSize?: number;
  search?: string;
  tag?: string | null;
  mode?: 'for-you' | 'following' | 'trending';
  sort?: 'latest' | 'trending' | 'most-liked' | 'most-commented';
}) {
  const response = await api.get<FeedResponse>('/feed', {
    params: {
      page: params.page ?? 1,
      page_size: params.pageSize ?? 10,
      search: params.search || undefined,
      tag: params.tag || undefined,
      mode: params.mode ?? 'for-you',
      sort: params.sort ?? 'latest',
    },
  });
  return response.data;
}

export async function getPost(postId: number) {
  const response = await api.get<ApiPost>(`/posts/${postId}`);
  return response.data;
}

export async function createPost(payload: {
  title: string;
  content: string;
  cover_image?: string;
  tags: string[];
}) {
  const response = await api.post<ApiPost>('/posts', payload);
  return response.data;
}

export async function updatePost(
  postId: number,
  payload: Partial<{
    title: string;
    content: string;
    cover_image: string | null;
    tags: string[];
  }>
) {
  const response = await api.patch<ApiPost>(`/posts/${postId}`, payload);
  return response.data;
}

export async function deletePost(postId: number) {
  await api.delete<void>(`/posts/${postId}`);
}

export async function togglePostLike(postId: number, liked: boolean) {
  if (liked) {
    await api.put(`/posts/${postId}/likes/me`);
  } else {
    await api.delete<void>(`/posts/${postId}/likes/me`);
  }
}

export async function toggleBookmark(postId: number, bookmarked: boolean) {
  if (bookmarked) {
    await api.put(`/posts/${postId}/bookmarks/me`);
  } else {
    await api.delete<void>(`/posts/${postId}/bookmarks/me`);
  }
}

export async function recordPostView(postId: number) {
  await api.post<void>(`/posts/${postId}/views`);
}

export type SharePostResponse = { post_id: number; original_post_id: number };

export async function sharePost(postId: number) {
  const response = await api.post<SharePostResponse>(`/posts/${postId}/shares`);
  return response.data;
}

export async function sharePostWithEdit(
  postId: number,
  payload: {
    caption?: string;
  }
) {
  const response = await api.post<SharePostResponse>(`/posts/${postId}/shares`, payload);
  return response.data;
}

export async function getComments(postId: number) {
  const response = await api.get<ApiComment[]>(`/posts/${postId}/comments`);
  return response.data;
}

export async function createComment(postId: number, payload: { content: string; parent_id?: number | null }) {
  const response = await api.post<ApiComment>(`/posts/${postId}/comments`, payload);
  return response.data;
}

export type ReportReason = 'spam' | 'harassment' | 'hate_speech' | 'violence' | 'misinformation' | 'other';

export type ReportResponse = {
  id: number;
  reporter_id: string | null;
  post_id: number | null;
  comment_id: number | null;
  reason: ReportReason | string;
  details: string | null;
  status: 'pending' | 'reviewed' | 'dismissed' | 'resolved';
  reviewed_by: string | null;
  reviewed_at: string | null;
  created_at: string;
};

export async function reportPost(postId: number, payload: { reason: ReportReason; details?: string | null }) {
  const response = await api.post<ReportResponse>(`/posts/${postId}/reports`, {
    reason: payload.reason,
    details: payload.details || null,
  });
  return response.data;
}

export async function reportComment(postId: number, commentId: number, payload: { reason: ReportReason; details?: string | null }) {
  const response = await api.post<ReportResponse>(`/posts/${postId}/comments/${commentId}/reports`, {
    reason: payload.reason,
    details: payload.details || null,
  });
  return response.data;
}

export async function getTags() {
  const response = await api.get<Array<{ id: number; name: string; slug: string }>>('/tags');
  return response.data;
}

export async function getSimilarPosts(postId: number, params?: {
  limit?: number;
  min_similarity?: number;
}) {
  const response = await api.get<SimilarPostsResponse>(`/recommendations/posts/${postId}/similar`, {
    params: {
      limit: params?.limit ?? 5,
      min_similarity: params?.min_similarity ?? 0.1,
    },
  });
  return response.data;
}

export async function getCollaborativeRecommendations(params?: {
  page?: number;
  pageSize?: number;
  min_similarity?: number;
  daysBack?: number;
}) {
  const response = await api.get<CollaborativePostsResponse>('/recommendations/collaborative', {
    params: {
      page: params?.page ?? 1,
      page_size: params?.pageSize ?? 10,
      min_similarity: params?.min_similarity ?? 0.2,
      days_back: params?.daysBack ?? 30,
    },
  });
  return response.data;
}

export async function getProfileBasedRecommendations(params?: {
  page?: number;
  pageSize?: number;
  min_score?: number;
  daysBack?: number;
}) {
  const response = await api.get<ProfileBasedPostsResponse>('/recommendations/profile', {
    params: {
      page: params?.page ?? 1,
      page_size: params?.pageSize ?? 10,
      min_score: params?.min_score ?? 0.1,
      days_back: params?.daysBack ?? 30,
    },
  });
  return response.data;
}

export async function getUserProfileSummary() {
  const response = await api.get<UserProfileSummary>('/recommendations/profile-summary');
  return response.data;
}

export async function getProfileAnalysis() {
  const response = await api.get<ProfileAnalysis>('/recommendations/profile-analysis');
  return response.data;
}
