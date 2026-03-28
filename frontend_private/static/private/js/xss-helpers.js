/**
 * Shared XSS helper functions.
 *
 * Loaded as a regular <script> in base_private.html so every page has
 * access without re-defining these per-template.  ES-module code in
 * the map viewer should use Utils.escapeHtml (which delegates here).
 */

/* exported escapeHtml, isValidCssColor, safeCssColor, sanitizeUrl */

function escapeHtml(text) {
    if (text === null || text === undefined) return '';
    var str = String(text);
    if (!str) return '';
    var div = document.createElement('div');
    div.textContent = str;
    return div.innerHTML.replace(/"/g, '&quot;').replace(/'/g, '&#39;');
}

function isValidCssColor(color) {
    if (!color || typeof color !== 'string') return false;
    return /^#([0-9A-Fa-f]{3}|[0-9A-Fa-f]{6})$/.test(color);
}

function safeCssColor(color, fallback) {
    return isValidCssColor(color) ? color : (fallback || '#94a3b8');
}

function sanitizeUrl(url) {
    if (!url || typeof url !== 'string') return '';
    var trimmed = url.trim();
    if (trimmed === '') return '';
    try {
        var parsed = new URL(trimmed, window.location.origin);
        if (parsed.protocol === 'http:' || parsed.protocol === 'https:') {
            return trimmed;
        }
    } catch (_) {
        if (!/^[a-zA-Z][a-zA-Z0-9+\-.]*:/.test(trimmed)) {
            return trimmed;
        }
    }
    return '';
}
