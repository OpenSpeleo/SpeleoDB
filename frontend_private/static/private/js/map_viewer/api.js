"use strict";

export function getCSRFToken() {
    const match = document.cookie.match(/csrftoken=([^;]+)/);
    return match ? decodeURIComponent(match[1]) : '';
}

// Low-level helper: mirror fetch but inject explicit CSRF token
export function csrfFetch(path, init = {}, csrfToken) {
    const headers = Object.assign({
        'X-Requested-With': 'XMLHttpRequest'
    }, init.headers || {});

    // If caller provided a token argument, prefer it. Otherwise fall back to cookie.
    const token = typeof csrfToken === 'string' && csrfToken.length >= 8 ? csrfToken : getCSRFToken();
    if (token) {
        headers['X-CSRFToken'] = token;
        headers['X-CSRF-Token'] = token;
    }

    const finalInit = Object.assign({}, init, { headers });
    // If body is a plain object and no FormData provided, encode as JSON
    if (finalInit.body && typeof finalInit.body === 'object' && !(finalInit.body instanceof FormData) && !headers['Content-Type']) {
        headers['Content-Type'] = 'application/json';
        finalInit.body = JSON.stringify(finalInit.body);
    }

    return fetch(path, finalInit);
}

export async function apiFetch(path, { method = 'GET', headers = {}, body, formData } = {}) {
    const init = { method, headers: { 'X-CSRFToken': getCSRFToken(), ...headers } };

    if (formData) {
        init.body = formData;
    } else if (body && typeof body === 'object') {
        init.headers['Content-Type'] = 'application/json';
        init.body = JSON.stringify(body);
    } else if (body) {
        init.body = body;
    }

    const resp = await fetch(path, init);
    if (!resp.ok) {
        let details = '';
        try { details = await resp.text(); } catch (_) { }
        throw new Error(`API ${method} ${path} failed: ${resp.status} ${details}`);
    }
    const contentType = resp.headers.get('content-type') || '';
    if (contentType.includes('application/json')) return resp.json();
    return resp.text();
}

export const api = { getCSRFToken, apiFetch };
export const fetchWithCSRF = csrfFetch;


