import { NextRequest, NextResponse } from 'next/server';

/**
 * Add-only integration point for Na's Smart Post Editor.
 * Original /create, /post/create, and /edit/[id] route files are untouched.
 * Coordinate this file with FE-01 if a central middleware is added later.
 */
export function middleware(request: NextRequest) {
  const path = request.nextUrl.pathname;
  const destination = request.nextUrl.clone();

  if (path === '/create' || path === '/post/create') {
    destination.pathname = '/na-post-editor/create';
  } else {
    const match = /^\/edit\/(\d+)\/?$/.exec(path);
    if (!match) return NextResponse.next();
    destination.pathname = `/na-post-editor/edit/${match[1]}`;
  }

  return NextResponse.rewrite(destination);
}

export const config = {
  matcher: ['/create', '/post/create', '/edit/:path*'],
};
