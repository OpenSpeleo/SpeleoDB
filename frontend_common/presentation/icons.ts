import { escapeHtml } from '../../frontend_private/static/private/ts/xss-helpers.ts';

/** The existing station-tag/permission pencil, shared by client-rendered actions. */
export function renderPencilIcon(className = '') {
    return `<svg class="${escapeHtml(className)}" viewBox="0 0 24 24" stroke="currentColor" stroke-width="1.5" fill="none" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
        <path d="M4 20h4l10.5 -10.5a2.828 2.828 0 1 0 -4 -4l-10.5 10.5v4"></path>
        <path d="M13.5 6.5l4 4"></path>
    </svg>`;
}
