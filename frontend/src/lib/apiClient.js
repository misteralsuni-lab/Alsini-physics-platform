import { supabase } from './supabaseClient';

// Normalized backend API base URL — sourced from Vite env, falls back to localhost:8000 for dev.
const rawApiBase = (import.meta.env.VITE_API_URL || 'http://localhost:8000').trim();
export const API_BASE = rawApiBase.replace(/\/+$/, '');

const DEFAULT_TIMEOUT_MS = 70_000;
const DEFAULT_SLOW_THRESHOLD_MS = 8_000;
const DEFAULT_MAX_RETRIES = 1;
const DEFAULT_RETRY_DELAY_MS = 2_000;
const MAX_ERROR_DETAIL_LENGTH = 220;

const STACK_TRACE_MARKERS = [
  /traceback\s*\(most recent call last\)/i,
  /^\s*file\s+["'][^"']+["'],\s+line\s+\d+/im,
  /\bat\s+[A-Za-z0-9_$.]+\s*\([^)]+:\d+:\d+\)/,
  /<(html|head|body|title|!doctype)\b/i,
];

/**
 * Structured error representing API, auth, timeout, or network failures.
 */
export class ApiError extends Error {
  constructor(
    message,
    {
      status = null,
      code = 'API_ERROR',
      detail = null,
      isTimeout = false,
      isNetworkError = false,
      isAbort = false,
    } = {}
  ) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
    this.code = code;
    this.detail = detail;
    this.isTimeout = isTimeout;
    this.isNetworkError = isNetworkError;
    this.isAbort = isAbort;
  }
}

/**
 * Redact token-like fragments and strip HTML/stack traces before rendering any
 * server-supplied error detail into React JSX text interpolation.
 */
export function sanitizeErrorDetail(rawDetail) {
  if (typeof rawDetail !== 'string') return '';
  const trimmed = rawDetail.replace(/\s+/g, ' ').trim();
  if (!trimmed) return '';

  if (STACK_TRACE_MARKERS.some((pattern) => pattern.test(trimmed))) {
    return '';
  }

  const redacted = trimmed
    .replace(/(Bearer\s+)[A-Za-z0-9._-]+/gi, '$1[redacted]')
    .replace(/([?&](?:key|token|apikey|secret)=)[^&\s]+/gi, '$1[redacted]')
    .replace(/\beyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\b/g, '[redacted]')
    .replace(/\b(?:sk|nvapi|AIza)[A-Za-z0-9_-]{8,}\b/g, '[redacted]');

  return redacted.length > MAX_ERROR_DETAIL_LENGTH
    ? `${redacted.slice(0, MAX_ERROR_DETAIL_LENGTH - 1)}…`
    : redacted;
}

function extractFastApiDetail(payload) {
  if (!payload || typeof payload !== 'object') return '';
  const { detail } = payload;
  if (typeof detail === 'string') return detail;
  if (Array.isArray(detail) && detail.length > 0) {
    const first = detail[0];
    if (typeof first === 'string') return first;
    if (first && typeof first.msg === 'string') return first.msg;
  }
  if (typeof payload.message === 'string') return payload.message;
  return '';
}

function buildStatusErrorMessage(status, safeDetail) {
  switch (status) {
    case 400:
    case 422:
      return safeDetail
        ? `Invalid request (${status}): ${safeDetail}`
        : `Invalid request (${status}). Please check your input and try again.`;
    case 401:
      return 'Session expired or sign-in required (401). Please sign in again to continue.';
    case 403:
      return safeDetail
        ? `Access denied (403): ${safeDetail}`
        : 'Access denied (403): You do not have permission to perform this action.';
    case 429:
      return safeDetail
        ? `Rate limit reached (429): ${safeDetail}`
        : 'Rate limit reached (429): Too many requests right now. Please wait a moment and try again.';
    case 500:
      return safeDetail
        ? `Server error (500): ${safeDetail}`
        : 'Server error (500): The backend encountered an internal error. Please try again shortly.';
    case 502:
      return safeDetail
        ? `Service error (502): ${safeDetail}`
        : 'Service error (502): The upstream AI or database service is temporarily unavailable. Please try again.';
    case 503:
      return safeDetail
        ? `Service unavailable (503): ${safeDetail}`
        : 'Service unavailable (503): The server is starting up or temporarily unavailable. Please try again in a few seconds.';
    case 504:
      return 'Gateway timeout (504): The server took too long to wake up or respond. Please try again.';
    default:
      if (status >= 500) {
        return safeDetail
          ? `Server error (${status}): ${safeDetail}`
          : `Server error (${status}): An unexpected backend error occurred. Please try again.`;
      }
      return safeDetail
        ? `Request failed (${status}): ${safeDetail}`
        : `Request failed (${status}). Please try again.`;
  }
}

/**
 * Parse a non-OK Fetch Response into a sanitized, status-aware ApiError.
 */
export async function parseApiErrorResponse(response) {
  const status = response.status;
  const contentType = (response.headers?.get('content-type') || '').toLowerCase();
  let rawDetail = '';

  try {
    if (contentType.includes('application/json')) {
      const payload = await response.json();
      rawDetail = extractFastApiDetail(payload);
    } else {
      const text = await response.text();
      if (!contentType.includes('text/html')) {
        rawDetail = text;
      }
    }
  } catch {
    rawDetail = '';
  }

  const safeDetail = sanitizeErrorDetail(rawDetail);
  const message = buildStatusErrorMessage(status, safeDetail);
  return new ApiError(message, {
    status,
    code: status === 401 ? 'AUTH_REQUIRED' : `HTTP_${status}`,
    detail: safeDetail || null,
  });
}

/**
 * Convert any thrown API/network/timeout error into a safe UI-friendly object.
 */
export function formatApiError(error) {
  if (error instanceof ApiError) {
    return {
      message: error.message,
      status: error.status,
      code: error.code,
      isAuthError: error.status === 401 || error.code === 'AUTH_REQUIRED',
      isTimeout: error.isTimeout,
      isNetworkError: error.isNetworkError,
      isAbort: error.isAbort,
    };
  }

  if (error?.name === 'AbortError' || error?.name === 'TimeoutError') {
    return {
      message:
        'Request timed out: The backend server took too long to respond (cold starts can take ~30–60s). Please try again.',
      status: null,
      code: 'TIMEOUT',
      isAuthError: false,
      isTimeout: true,
      isNetworkError: false,
      isAbort: false,
    };
  }

  if (error instanceof TypeError) {
    return {
      message:
        'Network error: Could not reach the backend server. It may be waking up or your connection was interrupted—please try again.',
      status: null,
      code: 'NETWORK_ERROR',
      isAuthError: false,
      isTimeout: false,
      isNetworkError: true,
      isAbort: false,
    };
  }

  const safeMsg = sanitizeErrorDetail(error?.message || '');
  return {
    message: safeMsg || 'An unexpected error occurred while contacting the server. Please try again.',
    status: null,
    code: 'UNKNOWN_ERROR',
    isAuthError: false,
    isTimeout: false,
    isNetworkError: false,
    isAbort: false,
  };
}

async function getFreshAccessToken() {
  const { data: { session }, error } = await supabase.auth.getSession();
  if (error || !session?.access_token) {
    throw new ApiError(
      'Session expired or sign-in required (401). Please sign in again to continue.',
      { status: 401, code: 'AUTH_REQUIRED' }
    );
  }

  const nowSeconds = Math.floor(Date.now() / 1000);
  if (session.expires_at && session.expires_at <= nowSeconds + 30) {
    const { data: refreshed, error: refreshError } = await supabase.auth.refreshSession();
    if (!refreshError && refreshed?.session?.access_token) {
      return refreshed.session.access_token;
    }
    if (session.expires_at <= nowSeconds) {
      throw new ApiError(
        'Your session has expired (401). Please sign in again to continue.',
        { status: 401, code: 'AUTH_REQUIRED' }
      );
    }
  }

  return session.access_token;
}

function abortableDelay(ms, externalSignal) {
  return new Promise((resolve, reject) => {
    if (externalSignal?.aborted) {
      reject(new ApiError('Request cancelled.', { code: 'ABORTED', isAbort: true }));
      return;
    }
    const timer = setTimeout(() => {
      if (externalSignal) {
        externalSignal.removeEventListener('abort', onAbort);
      }
      resolve();
    }, ms);

    const onAbort = () => {
      clearTimeout(timer);
      reject(new ApiError('Request cancelled.', { code: 'ABORTED', isAbort: true }));
    };
    if (externalSignal) {
      externalSignal.addEventListener('abort', onAbort, { once: true });
    }
  });
}

async function fetchAttempt(url, fetchInit, timeoutMs, externalSignal, slowThresholdMs, onSlow) {
  if (externalSignal?.aborted) {
    throw new ApiError('Request cancelled.', { code: 'ABORTED', isAbort: true });
  }

  const attemptController = new AbortController();
  let timedOut = false;
  let callerAborted = false;

  const onExternalAbort = () => {
    callerAborted = true;
    attemptController.abort();
  };
  if (externalSignal) {
    externalSignal.addEventListener('abort', onExternalAbort, { once: true });
  }

  const timeoutId = setTimeout(() => {
    timedOut = true;
    attemptController.abort();
  }, timeoutMs);

  const slowId =
    onSlow && slowThresholdMs > 0
      ? setTimeout(() => {
          if (!attemptController.signal.aborted) {
            onSlow();
          }
        }, slowThresholdMs)
      : null;

  try {
    return await fetch(url, { ...fetchInit, signal: attemptController.signal });
  } catch (err) {
    if (callerAborted || externalSignal?.aborted) {
      throw new ApiError('Request cancelled.', { code: 'ABORTED', isAbort: true });
    }
    if (timedOut || err?.name === 'TimeoutError' || err?.name === 'AbortError') {
      throw new ApiError(
        'Request timed out: The backend server took too long to respond (Render free-tier cold starts can take 30–60s). Please try again.',
        { code: 'TIMEOUT', isTimeout: true }
      );
    }
    throw new ApiError(
      'Network error: Could not reach the backend server. It may be waking up or your connection was interrupted—please try again.',
      { code: 'NETWORK_ERROR', isNetworkError: true }
    );
  } finally {
    clearTimeout(timeoutId);
    if (slowId) clearTimeout(slowId);
    if (externalSignal) {
      externalSignal.removeEventListener('abort', onExternalAbort);
    }
  }
}

async function shouldRetryTransientResponse(response) {
  if (response.status === 504) return true;
  if (response.status !== 502 && response.status !== 503) return false;

  const contentType = (response.headers?.get('content-type') || '').toLowerCase();
  if (!contentType.includes('application/json')) {
    return true;
  }

  try {
    const cloned = response.clone();
    const payload = await cloned.json();
    const detail = extractFastApiDetail(payload).toLowerCase();
    // Permanent config failures or exhausted multi-tier AI fallback should surface immediately.
    if (
      detail.includes('not configured') ||
      detail.includes('configuration error') ||
      detail.includes('ai service is temporarily unavailable')
    ) {
      return false;
    }
  } catch {
    return true;
  }

  return true;
}

/**
 * Call the FastAPI surface with the current Supabase access token, generous
 * cold-start timeout handling, single token-refresh on 401, and a bounded
 * single retry on transient Render spin-up / gateway failures.
 */
export async function authenticatedFetch(url, options = {}) {
  const {
    timeoutMs = DEFAULT_TIMEOUT_MS,
    maxRetries = DEFAULT_MAX_RETRIES,
    retryDelayMs = DEFAULT_RETRY_DELAY_MS,
    slowThresholdMs = DEFAULT_SLOW_THRESHOLD_MS,
    onStatusChange,
    signal: externalSignal,
    ...fetchOptions
  } = options;

  let token = await getFreshAccessToken();
  let didRefreshOn401 = false;
  let transientRetries = 0;
  const boundedMaxRetries = Math.max(0, Math.min(Number(maxRetries) || 0, 1));

  while (true) {
    const headers = new Headers(fetchOptions.headers || {});
    headers.set('Authorization', `Bearer ${token}`);
    if (
      fetchOptions.body &&
      !(typeof FormData !== 'undefined' && fetchOptions.body instanceof FormData) &&
      !headers.has('Content-Type')
    ) {
      headers.set('Content-Type', 'application/json');
    }

    try {
      const response = await fetchAttempt(
        url,
        { ...fetchOptions, headers },
        timeoutMs,
        externalSignal,
        slowThresholdMs,
        () => onStatusChange?.('waking')
      );

      // Single refresh attempt if the server rejected a stale/revoked token.
      if (response.status === 401 && !didRefreshOn401) {
        didRefreshOn401 = true;
        const { data: refreshed, error: refreshError } = await supabase.auth.refreshSession();
        const refreshedToken = refreshed?.session?.access_token;
        if (!refreshError && refreshedToken && refreshedToken !== token) {
          token = refreshedToken;
          continue;
        }
      }

      if (transientRetries < boundedMaxRetries && (await shouldRetryTransientResponse(response))) {
        transientRetries += 1;
        onStatusChange?.('retrying');
        await abortableDelay(retryDelayMs, externalSignal);
        continue;
      }

      return response;
    } catch (err) {
      if (err instanceof ApiError && err.isAbort) {
        throw err;
      }

      const isTransient = err instanceof ApiError && (err.isTimeout || err.isNetworkError);
      if (transientRetries < boundedMaxRetries && isTransient && !externalSignal?.aborted) {
        transientRetries += 1;
        onStatusChange?.('retrying');
        await abortableDelay(retryDelayMs, externalSignal);
        continue;
      }

      throw err;
    }
  }
}
