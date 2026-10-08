import { escapeHtml as escapeHtmlValue } from '../../../../../frontend_common/security/html.ts';
import { isValidCssColor as isValidColorValue } from '../../../../../frontend_common/security/color.ts';
import { sanitizeUrl as sanitizeUrlValue } from '../../../../../frontend_common/security/url.ts';
import { getMapOverlayHost } from './components/overlay_host.ts';
import { Notification } from './components/notification.ts';
import { DEFAULTS } from './defaults.ts';
import { getMapCSRFToken } from './csrf.ts';

const RAW_HTML = Symbol('RAW_HTML');

export const Utils = {
    raw: function(htmlString: unknown) {
        return { [RAW_HTML]: true, value: String(htmlString) };
    },

    mapActionAttributes: function(action: string, ...args: unknown[]) {
        if (!/^[a-z][a-z0-9-]*\.[A-Za-z][A-Za-z0-9]*$/.test(action)) {
            throw new Error(`Invalid map action: ${action}`);
        }
        const safeAction = Utils.escapeHtml(action);
        const safeArgs = Utils.escapeHtml(JSON.stringify(args));
        return `data-map-action="${safeAction}" data-map-args="${safeArgs}"`;
    },

    safeHtml: function(strings: TemplateStringsArray, ...values: unknown[]) {
        return strings.reduce((result, str, i) => {
            if (i < values.length) {
                const val = values[i];
                if (val && typeof val === 'object' && (val as { [RAW_HTML]?: boolean })[RAW_HTML]) {
                    return result + str + (val as { value: string }).value;
                }
                return result + str + Utils.escapeHtml(val);
            }
            return result + str;
        }, '');
    },

    getCSRFToken: function() {
        return getMapCSRFToken();
    },

    formatDateString: function(dateStr: string | null | undefined) {
        if (!dateStr) return 'N/A';
        return new Date(dateStr).toLocaleDateString(undefined, {
            year: 'numeric',
            month: 'short',
            day: 'numeric',
            hour: '2-digit',
            minute: '2-digit'
        });
    },

    formatJournalDate: function(isoString: string | null | undefined) {
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

    formatExpiracyDate: function(dateStr: string | null | undefined) {
        if (!dateStr) return 'N/A';
        const date = new Date(dateStr);
        const now = new Date();
        const diffTime = (date as unknown as number) - (now as unknown as number);
        const diffDays = Math.ceil(diffTime / (1000 * 60 * 60 * 24));

        let colorClass = 'text-emerald-400';
        if (diffDays < 0) colorClass = 'text-red-400';
        else if (diffDays < 7) colorClass = 'text-amber-400';

        return `<span class="${colorClass}">${date.toLocaleDateString()} (${diffDays > 0 ? 'in ' : ''}${Math.abs(diffDays)} days${diffDays < 0 ? ' ago' : ''})</span>`;
    },

    filenameFromUrl: function(url: string | null | undefined) {
        if (!url) return '';
        try {
            const parts = url.split('/');
            return decodeURIComponent(parts[parts.length - 1]!.split('?')[0]!);
        } catch (e) {
            return url;
        }
    },

    getFileName: function(url: string | null | undefined) {
        if (!url) return '';
        const parts = url.split('/');
        return decodeURIComponent(parts[parts.length - 1]!);
    },

    getFileAccept: function(type: string) {
        switch (type) {
            case 'image': return 'image/*';
            case 'video': return 'video/*';
            case 'document': return '.pdf,.doc,.docx,.txt,.csv,.xlsx,.xls';
            default: return '*/*';
        }
    },

    ensureAltitudeZero: function(coordinates: number[]) {
        if (coordinates.length > 2) {
            return [coordinates[0]!, coordinates[1]!];
        }
        return coordinates;
    },

    debounce: function<Args extends unknown[]>(func: (...args: Args) => unknown, wait: number) {
        let timeout: ReturnType<typeof setTimeout> | undefined;
        return function executedFunction(...args: Args) {
            const later = () => {
                clearTimeout(timeout);
                func(...args);
            };
            clearTimeout(timeout);
            timeout = setTimeout(later, wait);
        };
    },

    copyToClipboard: async function(text: string) {
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

    showNotification: function(type: string, message: string, duration?: number) {
        Notification.show(type, message, duration);
    },

    isValidCssColor: function(this: void, color: unknown): color is string {
        return isValidColorValue(color);
    },

    safeCssColor: function(color: unknown, fallback: string = DEFAULTS.COLORS.FALLBACK) {
        return this.isValidCssColor(color) ? color : fallback;
    },

    sanitizeUrl: function(url: unknown) {
        return sanitizeUrlValue(url);
    },

    countryFlag: function(code: unknown) {
        if (!code || typeof code !== 'string' || code.length !== 2) return '';
        const upper = code.toUpperCase();
        if (!/^[A-Z]{2}$/.test(upper)) return '';
        return String.fromCodePoint(
            upper.charCodeAt(0) - 0x41 + 0x1F1E6,
            upper.charCodeAt(1) - 0x41 + 0x1F1E6
        );
    },

    escapeHtml: function(text: unknown) {
        return escapeHtmlValue(text);
    },

    /**
     * Show loading overlay (full-screen with blurred backdrop)
     * @param {string} message - Loading message to display
     * @returns {HTMLElement} - The overlay element (pass to hideLoadingOverlay to remove)
     */
    showLoadingOverlay: function(message: string) {
        const overlay = document.createElement('div');
        overlay.id = 'station-loading-overlay';
        overlay.className = 'fixed inset-0 bg-srgb-black-50 backdrop-blur-xs z-50 flex items-center justify-center';

        const inner = document.createElement('div');
        inner.className = 'bg-slate-800 rounded-xl p-6 text-center';

        const spinner = document.createElement('div');
        spinner.className = 'loading-spinner center-x mb-4';

        const msgEl = document.createElement('p');
        msgEl.className = 'text-slate-300';
        msgEl.textContent = message;

        inner.appendChild(spinner);
        inner.appendChild(msgEl);
        overlay.appendChild(inner);
        getMapOverlayHost().appendChild(overlay);
        return overlay;
    },

    /**
     * Hide loading overlay
     * @param {HTMLElement} overlay - The overlay element returned from showLoadingOverlay
     */
    hideLoadingOverlay: function(overlay: HTMLElement | null | undefined) {
        if (overlay && overlay.parentNode) {
            overlay.remove();
        }
    }
};
