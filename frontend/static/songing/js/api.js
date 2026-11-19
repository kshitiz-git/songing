// Thin fetch wrapper for /api/. Handles JSON, CSRF header, error shapes, pagination URLs.

export class ApiError extends Error {
  constructor(status, data, message) {
    super(message || messageFrom(status, data));
    this.name = 'ApiError';
    this.status = status;
    this.data = data;
  }
  /** {field: "first message"}; non-field problems land under "_form". */
  get fields() {
    return fieldErrors(this.data);
  }
}

function first(v) {
  return Array.isArray(v) ? String(v[0] ?? '') : typeof v === 'string' ? v : v && typeof v === 'object' ? first(Object.values(v)[0]) : '';
}

function fieldErrors(data) {
  const out = {};
  if (data && typeof data === 'object' && !Array.isArray(data)) {
    for (const [k, v] of Object.entries(data)) {
      const key = k === 'detail' || k === 'non_field_errors' ? '_form' : k;
      const msg = first(v);
      if (msg && !out[key]) out[key] = msg;
    }
  }
  return out;
}

function messageFrom(status, data) {
  if (status === 0) return 'Could not reach the server. Check your connection and try again.';
  const f = fieldErrors(data);
  if (f._form) return f._form;
  const firstKey = Object.keys(f)[0];
  if (firstKey) return `${firstKey}: ${f[firstKey]}`;
  if (status === 429) return 'Too many attempts. Wait a minute and try again.';
  if (status === 401 || status === 403) return 'You need to log in to do that.';
  if (status === 404) return 'Not found.';
  return `Something went wrong (${status}).`;
}

export function cookie(name) {
  for (const part of document.cookie.split(';')) {
    const [k, ...v] = part.trim().split('=');
    if (k === name) return decodeURIComponent(v.join('='));
  }
  return '';
}

async function parse(res) {
  if (res.status === 204) return null;
  const type = res.headers.get('content-type') || '';
  if (type.includes('json')) {
    try {
      return await res.json();
    } catch {
      return null;
    }
  }
  return null;
}

/**
 * api('/api/home/')  ->  parsed JSON (null for 204)
 * api(url, {method, body, signal, full:true})  ->  {status, data}
 * body: plain object -> JSON. Throws ApiError (status 0 = network).
 */
export async function api(path, { method = 'GET', body, signal, full = false } = {}) {
  const headers = { Accept: 'application/json' };
  const init = { method, headers, credentials: 'same-origin', signal };
  if (method !== 'GET' && method !== 'HEAD') headers['X-CSRFToken'] = cookie('csrftoken');
  if (body !== undefined) {
    headers['Content-Type'] = 'application/json';
    init.body = JSON.stringify(body);
  }
  let res;
  try {
    res = await fetch(path, init);
  } catch (err) {
    if (err && err.name === 'AbortError') throw err;
    throw new ApiError(0, null);
  }
  const data = await parse(res);
  if (!res.ok) throw new ApiError(res.status, data);
  return full ? { status: res.status, data } : data;
}

/** Multipart upload with progress. Returns {promise, abort}. onProgress(fraction 0..1). */
export function uploadForm(path, formData, onProgress) {
  const xhr = new XMLHttpRequest();
  const promise = new Promise((resolve, reject) => {
    xhr.open('POST', path);
    xhr.withCredentials = true;
    xhr.setRequestHeader('X-CSRFToken', cookie('csrftoken'));
    xhr.setRequestHeader('Accept', 'application/json');
    xhr.upload.onprogress = (e) => {
      if (e.lengthComputable && onProgress) onProgress(e.loaded / e.total);
    };
    xhr.onload = () => {
      let data = null;
      try {
        data = JSON.parse(xhr.responseText);
      } catch {
        /* non-JSON error page */
      }
      if (xhr.status >= 200 && xhr.status < 300) resolve(data);
      else reject(new ApiError(xhr.status, data));
    };
    xhr.onerror = () => reject(new ApiError(0, null));
    xhr.onabort = () => reject(Object.assign(new Error('Upload cancelled'), { name: 'AbortError' }));
    xhr.send(formData);
  });
  return { promise, abort: () => xhr.abort() };
}

/** DRF "next" is an absolute URL: keep only path + query so it stays same-origin. */
export function relativeUrl(next) {
  try {
    const u = new URL(next, location.origin);
    return u.pathname + u.search;
  } catch {
    return null;
  }
}
