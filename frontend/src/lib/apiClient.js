import { supabase } from './supabaseClient';

/**
 * Call the FastAPI surface with the current Supabase access token.
 * The API is intentionally not callable as an anonymous browser endpoint.
 */
export async function authenticatedFetch(url, options = {}) {
  const { data: { session } } = await supabase.auth.getSession();
  if (!session?.access_token) {
    throw new Error('Authentication is required to call the EDU-VLE API.');
  }

  const headers = new Headers(options.headers || {});
  headers.set('Authorization', `Bearer ${session.access_token}`);
  if (options.body && !headers.has('Content-Type')) {
    headers.set('Content-Type', 'application/json');
  }

  return fetch(url, { ...options, headers });
}
