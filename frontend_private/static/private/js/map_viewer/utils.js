import { Notification } from './components/notification.js';

export const Utils = {
    getCSRFToken: function() {
        const cookieValue = document.cookie
            .split('; ')
            .find(row => row.startsWith('csrftoken='))
            ?.split('=')[1];
        return cookieValue || (window.MAPVIEWER_CONTEXT ? window.MAPVIEWER_CONTEXT.csrfToken : '');
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

    escapeHtml: function(text) {
        if (!text) return '';
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
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
        overlay.innerHTML = `
            <div class="bg-slate-800 rounded-xl p-6 text-center">
                <div class="loading-spinner mx-auto mb-4"></div>
                <p class="text-slate-300">${message}</p>
            </div>
        `;
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
