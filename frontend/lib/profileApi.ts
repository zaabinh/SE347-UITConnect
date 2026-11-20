'use client';

import { api, AuthUser, fetchCurrentUser, saveStoredUser } from '@/lib/axios';

export type CompleteProfilePayload = {
  username: string;
  full_name: string;
  avatar_url?: string | null;
  bio?: string | null;
  major?: string | null;
  academic_year?: string | null;
  career_goal?: string | null;
  interest_tags?: string[];
};

export async function completeProfile(payload: CompleteProfilePayload) {
  const response = await api.put<AuthUser>('/users/me/profile-completion', payload);
  saveStoredUser(response.data);
  return response.data;
}

export type ProfileSummary = {
  id: string;
  username: string | null;
  full_name: string;
  avatar_url: string | null;
  bio: string | null;
  major?: string | null;
  academic_year?: string | null;
  career_goal?: string | null;
  interest_tags?: string[];
  followers_count: number;
  following_count: number;
  posts_count: number;
  is_following: boolean;
  is_current_user: boolean;
};

export type CurrentProfile = ProfileSummary & {
  id: string;
  email: string;
  role: string;
  status: string;
  created_at: string;
};

export type ProfilePost = {
  id: number;
  title: string;
  content: string;
  cover_image: string | null;
  status?: 'pending' | 'active' | 'rejected' | string | null;
  created_at: string;
};

export type ProfileComment = {
  id: number;
  post_id: number;
  post_title: string | null;
  content: string;
  created_at: string;
};

export type NotificationItem = {
  id: number;
  user_id: string;
  actor_id: string | null;
  type: string;
  title: string;
  message: string | null;
  is_read: boolean;
  post_id: number | null;
  comment_id: number | null;
  report_id: number | null;
  created_at: string;
};

export type UpdateProfilePayload = Partial<{
  full_name: string;
  bio: string | null;
  avatar_url: string | null;
  major?: string | null;
  academic_year?: string | null;
  career_goal?: string | null;
  interest_tags?: string[];
}>;

export async function getMyProfile() {
  const response = await api.get<CurrentProfile>('/users/me');
  return response.data;
}

export async function getUserProfile(username: string) {
  const response = await api.get<ProfileSummary>(`/users/by-username/${encodeURIComponent(username)}`);
  return response.data;
}

export async function getUserPosts(username: string) {
  const response = await api.get<ProfilePost[]>(`/users/by-username/${encodeURIComponent(username)}/posts`);
  return response.data;
}

export async function getUserComments(username: string) {
  const response = await api.get<ProfileComment[]>(`/users/by-username/${encodeURIComponent(username)}/comments`);
  return response.data;
}

export async function getUserBookmarks() {
  const response = await api.get<ProfilePost[]>('/users/me/bookmarks');
  return response.data;
}

export async function getMyNotifications(unreadOnly = false) {
  const response = await api.get<NotificationItem[]>('/notifications', {
    params: { unread_only: unreadOnly },
  });
  return response.data;
}

export async function markNotificationRead(notificationId: number) {
  const response = await api.put<NotificationItem>(`/notifications/${notificationId}/read`);
  return response.data;
}

export async function deleteReadNotification(notificationId: number) {
  await api.delete<void>(`/notifications/${notificationId}`);
}

export async function updateMyProfile(payload: UpdateProfilePayload) {
  const response = await api.patch<CurrentProfile>('/users/me', payload);
  const currentUser = await fetchCurrentUser();
  saveStoredUser(currentUser);
  return response.data;
}

export async function followUser(userId: string) {
  const response = await api.put<{ following: boolean }>(`/users/${userId}/followers/me`);
  return response.data;
}

export async function unfollowUser(userId: string) {
  await api.delete<void>(`/users/${userId}/followers/me`);
}
