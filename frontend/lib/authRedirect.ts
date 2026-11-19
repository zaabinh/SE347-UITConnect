export function getLocalRedirectPath(value: string | null) {
  if (!value) return '/feed';
  try {
    const decoded = decodeURIComponent(value);
    if (decoded.startsWith('/') && !decoded.startsWith('//') && !/[\\\u0000-\u0020]/.test(decoded)) {
      return value;
    }
  } catch {
    // Malformed URL escapes are not valid navigation targets.
  }
  return '/feed';
}
