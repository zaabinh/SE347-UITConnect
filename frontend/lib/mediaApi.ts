'use client';

import { api } from '@/lib/axios';

export async function uploadImage(file: File) {
  if (file.size > 5 * 1024 * 1024) throw new Error('Image must be 5 MiB or smaller.');
  if (!['image/jpeg', 'image/png'].includes(file.type)) throw new Error('Choose a JPEG or PNG image.');
  const form = new FormData();
  form.append('file', file);
  const response = await api.post<{ url: string }>('/media/images', form, {
    headers: { 'Content-Type': undefined },
  });
  return response.data.url;
}
