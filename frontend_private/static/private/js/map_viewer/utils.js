import { Notification } from './components/notification.js';
import { DEFAULTS } from './config.js';

const RAW_HTML = Symbol('RAW_HTML');

function isValidCSRFToken(token) {
    const pattern = new RegExp(
        `^[A-Za-z0-9]{${DEFAULTS.CSRF.SECRET_LENGTH}}$|^[A-Za-z0-9]{${DEFAULTS.CSRF.TOKEN_LENGTH}}$`
    );
    return pattern.test(token);
}

function normalizeCSRFToken(token) {
    if (typeof token !== 'string') return '';
    const trimmed = token.trim();
    return isValidCSRFToken(trimmed) ? trimmed : '';
}

function getCSRFTokenFromInput() {
    const input = document.querySelector('input[name="csrfmiddlewaretoken"]');
    return normalizeCSRFToken(input?.value);
}

function getCSRFTokenFromCookie() {
    const cookieValue = document.cookie
        .split('; ')
        .find(row => row.startsWith('csrftoken='))
        ?.slice('csrftoken='.length);
    if (!cookieValue) return '';
    try {
        return normalizeCSRFToken(decodeURIComponent(cookieValue));
    } catch {
        return normalizeCSRFToken(cookieValue);
    }
}

export const Utils = {
    raw: function(htmlString) {
        return { [RAW_HTML]: true, value: String(htmlString) };
    },

    safeHtml: function(strings, ...values) {
        return strings.reduce((result, str, i) => {
            if (i < values.length) {
                const val = values[i];
                if (val && typeof val === 'object' && val[RAW_HTML]) {
                    return result + str + val.value;
                }
                return result + str + Utils.escapeHtml(val);
            }
            return result + str;
        }, '');
    },

    getCSRFToken: function() {
        return getCSRFTokenFromInput()
            || getCSRFTokenFromCookie()
            || normalizeCSRFToken(window.MAPVIEWER_CONTEXT?.csrfToken);
    },

    formatDateString: function(dateStr) {
        if (!dateStr) return 'N/A';
        return new Date(dateStr).toLocaleDateString(undefined, {
            year: 'numeric',
            month: 'short',
            day: 'numeric',
            hour: '2-digit',
            minute: '2-digit'
        });
    },

    formatJournalDate: function(isoString) {
        if (!isoString) return '';
        const date = new Date(isoString);
        return date.toLocaleDateString(undefined, {
            weekday: 'short',
            year: 'numeric',
            month: 'short',
            day: 'numeric',
            hour: '2-digit',
            minute: '2-digit'
        });
    },

    formatExpiracyDate: function(dateStr) {
        if (!dateStr) return 'N/A';
        const date = new Date(dateStr);
        const now = new Date();
        const diffTime = date - now;
        const diffDays = Math.ceil(diffTime / (1000 * 60 * 60 * 24));
        
        let colorClass = 'text-emerald-400';
        if (diffDays < 0) colorClass = 'text-red-400';
        else if (diffDays < 7) colorClass = 'text-amber-400';
        
        return `<span class="${colorClass}">${date.toLocaleDateString()} (${diffDays > 0 ? 'in ' : ''}${Math.abs(diffDays)} days${diffDays < 0 ? ' ago' : ''})</span>`;
    },

    filenameFromUrl: function(url) {
        if (!url) return '';
        try {
            const parts = url.split('/');
            return decodeURIComponent(parts[parts.length - 1].split('?')[0]);
        } catch (e) {
            return url;
        }
    },

    getFileName: function(url) {
        if (!url) return '';
        const parts = url.split('/');
        return decodeURIComponent(parts[parts.length - 1]);
    },

    getFileAccept: function(type) {
        switch (type) {
            case 'image': return 'image/*';
            case 'video': return 'video/*';
            case 'document': return '.pdf,.doc,.docx,.txt,.csv,.xlsx,.xls';
            default: return '*/*';
        }
    },

    ensureAltitudeZero: function(coordinates) {
        if (coordinates.length > 2) {
            return [coordinates[0], coordinates[1]];
        }
        return coordinates;
    },

    debounce: function(func, wait) {
        let timeout;
        return function executedFunction(...args) {
            const later = () => {
                clearTimeout(timeout);
                func(...args);
            };
            clearTimeout(timeout);
            timeout = setTimeout(later, wait);
        };
    },

    copyToClipboard: async function(text) {
        try {
            await navigator.clipboard.writeText(text);
            this.showNotification('success', 'Copied to clipboard');
            return true;
        } catch (err) {
            console.error('Failed to copy text: ', err);
            this.showNotification('error', 'Failed to copy');
            return false;
        }
    },

    showNotification: function(type, message, duration) {
        Notification.show(type, message, duration);
    },

    isValidCssColor: function(color) {
        if (!color || typeof color !== 'string') return false;
        return /^#([0-9A-Fa-f]{3}|[0-9A-Fa-f]{6})$/.test(color);
    },

    safeCssColor: function(color, fallback = DEFAULTS.COLORS.FALLBACK) {
        return this.isValidCssColor(color) ? color : fallback;
    },

    sanitizeUrl: function(url) {
        if (!url || typeof url !== 'string') return '';
        const trimmed = url.trim();
        if (trimmed === '') return '';
        try {
            const parsed = new URL(trimmed, window.location.origin);
            if (parsed.protocol === 'http:' || parsed.protocol === 'https:') {
                return trimmed;
            }
        } catch (_) {
            if (!/^[a-zA-Z][a-zA-Z0-9+\-.]*:/.test(trimmed)) {
                return trimmed;
            }
        }
        return '';
    },

    countryFlag: function(code) {
        if (!code || typeof code !== 'string' || code.length !== 2) return '';
        const upper = code.toUpperCase();
        if (!/^[A-Z]{2}$/.test(upper)) return '';
        return String.fromCodePoint(
            upper.charCodeAt(0) - 0x41 + 0x1F1E6,
            upper.charCodeAt(1) - 0x41 + 0x1F1E6
        );
    },

    escapeHtml: function(text) {
        if (text === null || text === undefined) return '';
        const str = String(text);
        if (!str) return '';
        const div = document.createElement('div');
        div.textContent = str;
        return div.innerHTML.replace(/"/g, '&quot;').replace(/'/g, '&#39;');
    },

    /**
     * Show loading overlay (full-screen with blur backdrop)
     * @param {string} message - Loading message to display
     * @returns {HTMLElement} - The overlay element (pass to hideLoadingOverlay to remove)
     */
    showLoadingOverlay: function(message) {
        const overlay = document.createElement('div');
        overlay.id = 'station-loading-overlay';
        overlay.className = 'fixed inset-0 bg-black/50 backdrop-blur-sm z-50 flex items-center justify-center';

        const inner = document.createElement('div');
        inner.className = 'bg-slate-800 rounded-xl p-6 text-center';

        const spinner = document.createElement('div');
        spinner.className = 'loading-spinner mx-auto mb-4';

        const msgEl = document.createElement('p');
        msgEl.className = 'text-slate-300';
        msgEl.textContent = message;

        inner.appendChild(spinner);
        inner.appendChild(msgEl);
        overlay.appendChild(inner);
        document.body.appendChild(overlay);
        return overlay;
    },

    /**
     * Hide loading overlay
     * @param {HTMLElement} overlay - The overlay element returned from showLoadingOverlay
     */
    hideLoadingOverlay: function(overlay) {
        if (overlay && overlay.parentNode) {
            overlay.remove();
        }
    }
};
