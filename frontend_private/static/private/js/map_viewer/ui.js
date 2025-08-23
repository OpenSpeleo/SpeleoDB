"use strict";

export function showNotification(type, message, duration = 3000) {
    const notification = document.createElement('div');
    notification.className = 'notification-toast';

    const icons = { success: '✅', error: '❌', info: 'ℹ️', warning: '⚠️' };
    const colors = { success: '#10b981', error: '#ef4444', info: '#00D8FF', warning: '#f59e0b' };

    notification.innerHTML = `
        <div class="notification-icon">${icons[type] || icons.info}</div>
        <div class="notification-message">${message}</div>
    `;

    notification.style.cssText = `
        position: fixed;
        top: 20px;
        right: 20px;
        background: ${colors[type] || colors.info};
        color: white;
        padding: 16px 24px;
        border-radius: 12px;
        font-size: 14px;
        font-weight: 500;
        display: flex;
        align-items: center;
        gap: 12px;
        z-index: 10050;
        box-shadow: 0 10px 25px rgba(0,0,0,0.35);
        opacity: 0;
        transform: translateY(-8px);
        transition: opacity .2s ease, transform .2s ease;
    `;

    const iconEl = notification.querySelector('.notification-icon');
    if (iconEl) {
        iconEl.style.cssText = `
            font-size: 16px;
        `;
    }
    const msgEl = notification.querySelector('.notification-message');
    if (msgEl) {
        msgEl.style.cssText = `
            line-height: 1.4;
        `;
    }

    document.body.appendChild(notification);
    requestAnimationFrame(() => {
        notification.style.opacity = '1';
        notification.style.transform = 'translateY(0)';
    });

    const timeout = Math.max(1000, Number(duration) || 3000);
    setTimeout(() => {
        notification.style.opacity = '0';
        notification.style.transform = 'translateY(-8px)';
        setTimeout(() => notification.remove(), 200);
    }, timeout);
}

export function initializeTabs() {
    // Placeholder: when migrating, wire tab buttons to show/hide panels
}

// Photo lightbox and video modal utilities (call from HTML)
export function openPhotoLightbox(url, title) {
    const lightbox = document.getElementById('photo-lightbox');
    const img = document.getElementById('lightbox-image');
    if (!lightbox || !img) return;
    img.src = url;
    img.alt = title || 'Photo';
    lightbox.style.display = 'flex';
    document.body.style.overflow = 'hidden';
}

export function closePhotoLightbox(event) {
    if (event && event.target && event.target.id && event.target.id !== 'photo-lightbox' && !event.target.closest('.photo-lightbox-close')) return;
    const lightbox = document.getElementById('photo-lightbox');
    if (lightbox) lightbox.style.display = 'none';
    document.body.style.overflow = '';
}

export function downloadPhoto() {
    const img = document.getElementById('lightbox-image');
    if (!img || !img.src) return;
    const a = document.createElement('a');
    a.href = img.src;
    a.download = (img.alt || 'photo').replace(/\s+/g, '_');
    document.body.appendChild(a);
    a.click();
    a.remove();
}

export function openPhotoInNewTab() {
    const img = document.getElementById('lightbox-image');
    if (img && img.src) window.open(img.src, '_blank');
}

export function openVideoModal(url, title) {
    const modal = document.createElement('div');
    modal.className = 'fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/90';
    modal.onclick = (e) => { if (e.target === modal) closeVideoModal(); };
    const container = document.createElement('div');
    container.className = 'relative w-full max-w-4xl bg-slate-800 rounded-lg overflow-hidden';
    const header = document.createElement('div');
    header.className = 'flex justify-between items-center p-4 border-b border-slate-700';
    header.innerHTML = `
            <h3 class="text-lg font-medium text-white">${title || 'Video'}</h3>
            <button onclick="window.uiCloseVideoModal()" class="text-slate-400 hover:text-white">
                <svg class="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"></path>
                </svg>
            </button>`;
    const body = document.createElement('div');
    body.className = 'p-4';
    body.innerHTML = `<video src="${url}" controls class="w-full h-auto"></video>`;
    container.appendChild(header);
    container.appendChild(body);
    modal.appendChild(container);
    document.body.appendChild(modal);
}

export function closeVideoModal() {
    const modals = document.querySelectorAll('.fixed.inset-0.z-50');
    modals.forEach(m => m.remove());
}

// Note viewer helpers
export function openNoteViewer(noteData) {
    const modal = document.getElementById('note-viewer-modal');
    if (!modal) return;
    const titleEl = document.getElementById('note-viewer-title');
    const authorEl = document.getElementById('note-viewer-author');
    const dateEl = document.getElementById('note-viewer-date');
    const descEl = document.getElementById('note-viewer-description');
    const contentEl = document.getElementById('note-viewer-content');
    const countEl = document.getElementById('note-viewer-char-count');
    if (titleEl) titleEl.textContent = noteData.title;
    if (authorEl) authorEl.textContent = `By ${noteData.author}`;
    if (dateEl) dateEl.textContent = new Date(noteData.date).toLocaleDateString();
    if (descEl) {
        if (noteData.description) { descEl.textContent = noteData.description; descEl.style.display = 'block'; }
        else { descEl.style.display = 'none'; }
    }
    if (contentEl) contentEl.innerHTML = formatNoteContent(noteData.content);
    if (countEl) countEl.textContent = String((noteData.content || '').length);
    modal.style.display = 'flex';
    document.body.style.overflow = 'hidden';
    window.__mv = window.__mv || {}; window.__mv.currentNoteContent = noteData.content;
}

export function formatNoteContent(content) {
    const escaped = String(content || '')
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;');
    const paragraphs = escaped.split(/\n\n+/).filter(p => p.trim());
    return paragraphs.map(paragraph => {
        const formatted = paragraph.replace(/\n/g, '<br>');
        return `<p class="mb-4 text-slate-300 leading-relaxed">${formatted}</p>`;
    }).join('');
}

export function closeNoteViewer() {
    const modal = document.getElementById('note-viewer-modal');
    if (modal) modal.style.display = 'none';
    document.body.style.overflow = '';
    if (window.__mv) window.__mv.currentNoteContent = null;
}

export function copyNoteToClipboard(event) {
    const text = window.__mv && window.__mv.currentNoteContent;
    if (!text) return;
    navigator.clipboard.writeText(text).then(() => {
        const button = event && event.target ? event.target.closest('button') : null;
        if (!button) return;
        const originalHTML = button.innerHTML;
        button.innerHTML = `
                <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7"></path>
                </svg>
                Copied!
            `;
        button.classList.add('bg-green-600', 'hover:bg-green-700');
        setTimeout(() => {
            button.innerHTML = originalHTML;
            button.classList.remove('bg-green-600', 'hover:bg-green-700');
        }, 2000);
    }).catch(err => {
        console.error('Failed to copy to clipboard:', err);
        showNotification('error', 'Failed to copy to clipboard');
    });
}

// Context menu handlers
export function bindMapContextMenu(map) {
    if (!map || typeof map.on !== 'function') return;
    const showHandler = function (point, lngLat, ev) {
        try { if (ev && typeof ev.preventDefault === 'function') ev.preventDefault(); } catch (_) { }
        try { if (typeof window.hideContextMenu === 'function') window.hideContextMenu(); } catch (_) { }
        try { if (typeof window.showContextMenu === 'function') window.showContextMenu(point, lngLat, null); } catch (_) { }
    };
    try {
        map.on('contextmenu', function (e) {
            try { showHandler(e.point, e.lngLat, e.originalEvent || e); } catch (_) { }
        });
    } catch (_) { }
    try {
        const canvas = typeof map.getCanvas === 'function' ? map.getCanvas() : null;
        if (canvas) {
            canvas.addEventListener('contextmenu', function (ev) {
                try {
                    ev.preventDefault();
                    const rect = canvas.getBoundingClientRect();
                    const x = ev.clientX - rect.left;
                    const y = ev.clientY - rect.top;
                    const point = { x, y };
                    const lngLat = typeof map.unproject === 'function' ? map.unproject([x, y]) : null;
                    showHandler(point, lngLat, ev);
                } catch (_) { }
            }, { passive: false });
        }
    } catch (_) { }
    try {
        map.on('click', function () { try { if (typeof window.hideContextMenu === 'function') window.hideContextMenu(); } catch (_) { } });
        map.on('dragstart', function () { try { if (typeof window.hideContextMenu === 'function') window.hideContextMenu(); } catch (_) { } });
    } catch (_) { }
}


