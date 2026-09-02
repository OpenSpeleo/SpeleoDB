import { attachTaggedEntityList } from '../../frontend_private/static/private/js/forms/tagged_entity_list.js';
import { GPXImport } from '../../frontend_private/static/private/js/gpx_import.js';
import {
    escapeHtml,
    safeCssColor,
    sanitizeUrl,
} from '../../frontend_private/static/private/js/xss-helpers.js';

const FALLBACK_COLOR = '#94a3b8';

function formatDate(dateString) {
    const date = new Date(dateString);
    if (Number.isNaN(date.getTime())) return 'Unknown';
    return date.toLocaleDateString('en-US', {
        year: 'numeric',
        month: 'short',
        day: 'numeric',
        hour: '2-digit',
        minute: '2-digit',
    });
}

function routeUrl(routeName, trackId) {
    const route = globalThis.Urls?.[routeName];
    if (typeof route !== 'function') return '';
    return sanitizeUrl(route(trackId));
}

function normalizedPermissionLabel(label) {
    if (!label) return 'Unknown';
    return String(label)
        .toLowerCase()
        .split('_')
        .map(word => word.charAt(0).toUpperCase() + word.slice(1))
        .join(' ');
}

function permissionPillClass(label) {
    const classes = {
        READ_ONLY: 'bg-pastel-beige',
        READ_AND_WRITE: 'bg-pastel-navy',
        ADMIN: 'bg-pastel-orange',
    };
    return classes[label] || 'bg-slate-700 text-slate-300';
}

function renderDesktopActions(track, openIconUrl) {
    const exportUrl = escapeHtml(routeUrl('api:v2:gps-track-export-gpx', track.id));
    const detailsUrl = escapeHtml(routeUrl('private:gps_track_details', track.id));
    const iconUrl = escapeHtml(sanitizeUrl(openIconUrl));
    return `
        <a class="inline-flex cursor-pointer" href="${exportUrl}" title="Export track as GPX" aria-label="Export GPS track as GPX">
            <svg class="h-6 w-6 stroke-current text-cyan-500 hover:text-cyan-400" viewBox="0 0 24 24" stroke-width="1.5" fill="none" stroke-linecap="round" stroke-linejoin="round">
                <path d="M12 3v12"></path><path d="M8 11l4 4 4-4"></path><path d="M5 21h14"></path>
            </svg>
        </a>
        <div class="w-10 aspect-square min-w-0 shrink bg-slate-700 rounded-full">
            <a class="flex items-center justify-center w-full h-full" href="${detailsUrl}" title="Open track settings" aria-label="Open GPS track settings">
                <img class="w-5 h-5" src="${iconUrl}" alt="Icon Open">
            </a>
        </div>`;
}

function renderMobileActions(track, openIconUrl) {
    const exportUrl = escapeHtml(routeUrl('api:v2:gps-track-export-gpx', track.id));
    const detailsUrl = escapeHtml(routeUrl('private:gps_track_details', track.id));
    const iconUrl = escapeHtml(sanitizeUrl(openIconUrl));
    return `
        <a class="w-10 h-10 shrink-0 flex items-center justify-center bg-cyan-600 hover:bg-cyan-500 rounded-full transition" href="${exportUrl}" aria-label="Export GPS track as GPX">
            <svg class="h-5 w-5 text-white" viewBox="0 0 24 24" stroke-width="1.5" fill="none" stroke="currentColor"><path d="M12 3v12"></path><path d="M8 11l4 4 4-4"></path><path d="M5 21h14"></path></svg>
        </a>
        <a class="w-10 h-10 shrink-0 flex items-center justify-center bg-indigo-600 hover:bg-indigo-500 rounded-full transition" href="${detailsUrl}" aria-label="Open GPS track settings">
            <img class="ml-1" src="${iconUrl}" width="20" height="20" alt="View">
        </a>`;
}

export function buildTrackListMarkup(tracks, openIconUrl = '') {
    if (tracks.length === 0) {
        const emptyStateHtml = `
            <svg class="w-16 h-16 center-x mb-4 text-slate-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 20l-5.447-2.724A1 1 0 013 16.382V5.618a1 1 0 011.447-.894L9 7m0 13l6-3m-6 3V7m6 10l4.553 2.276A1 1 0 0021 18.382V7.618a1 1 0 00-.553-.894L15 4m0 13V4m0 0L9 7"></path>
            </svg>
            <p class="text-lg font-medium">No GPS tracks yet</p>
            <p class="text-sm mt-1">Import a GPX file to add your first GPS track</p>`;
        return {
            tableHtml: `<tr><td colspan="6" class="px-2 py-8 text-center text-slate-400">${emptyStateHtml}</td></tr>`,
            cardsHtml: `<div class="text-center py-12 text-slate-400">${emptyStateHtml}</div>`,
        };
    }

    const tableHtml = tracks.map((track, index) => {
        const permissionLabel = normalizedPermissionLabel(track.user_permission_level_label);
        return `
            <tr>
                <td class="px-2 first:pl-5 last:pr-5 py-3"><div class="text-center font-medium text-slate-100">${index + 1}</div></td>
                <td class="px-2 first:pl-5 last:pr-5 py-3">
                    <div class="flex items-center gap-3">
                        <div class="w-3 h-3 rounded-full shrink-0" style="background-color: ${safeCssColor(track.color, FALLBACK_COLOR)}"></div>
                        <div class="font-medium text-slate-100">${escapeHtml(track.name)}</div>
                    </div>
                </td>
                <td class="px-2 first:pl-5 last:pr-5 py-3"><div class="text-center text-slate-300 text-sm">${escapeHtml(track.created_by)}</div></td>
                <td class="px-2 first:pl-5 last:pr-5 py-3"><div class="text-center"><span class="inline-flex font-medium ${permissionPillClass(track.user_permission_level_label)} rounded-full px-2.5 py-0.5">${escapeHtml(permissionLabel)}</span></div></td>
                <td class="px-2 first:pl-5 last:pr-5 py-3"><div class="text-center text-slate-400 text-sm">${escapeHtml(formatDate(track.creation_date))}</div></td>
                <td class="px-2 first:pl-5 last:pr-5 py-3"><div class="flex items-center justify-center gap-2">${renderDesktopActions(track, openIconUrl)}</div></td>
            </tr>`;
    }).join('');

    const cardsHtml = tracks.map(track => {
        const permissionLabel = normalizedPermissionLabel(track.user_permission_level_label);
        return `
            <div class="track-card">
                <div class="track-card-header">
                    <div class="track-card-title flex items-center gap-3">
                        <div class="w-4 h-4 rounded-full shrink-0" style="background-color: ${safeCssColor(track.color, FALLBACK_COLOR)}"></div>
                        <div class="text-lg font-semibold text-slate-100">${escapeHtml(track.name)}</div>
                    </div>
                    <div class="track-card-actions">${renderMobileActions(track, openIconUrl)}</div>
                </div>
                <div class="track-card-body">
                    <div class="track-card-row"><span class="track-card-label">Creator</span><span class="track-card-value">${escapeHtml(track.created_by)}</span></div>
                    <div class="track-card-row"><span class="track-card-label">Access</span><span class="inline-flex font-medium ${permissionPillClass(track.user_permission_level_label)} rounded-full px-2.5 py-0.5">${escapeHtml(permissionLabel)}</span></div>
                    <div class="track-card-row"><span class="track-card-label">Created</span><span class="track-card-value">${escapeHtml(formatDate(track.creation_date))}</span></div>
                </div>
            </div>`;
    }).join('');
    return { tableHtml, cardsHtml };
}

export function init(context) {
    GPXImport.init(context.csrfToken);
    $('#import-gpx-button').on('click', () => GPXImport.showModal());
    $(document).on('click', '[data-gpx-action]', function () {
        const actions = {
            browse: () => document.getElementById('gpx-file-input').click(),
            clear: () => GPXImport.clearFile(),
            hide: () => GPXImport.hideModal(),
            upload: () => GPXImport.upload(),
            'hide-warning': () => GPXImport.hideWarningModal(),
        };
        actions[$(this).data('gpx-action')]?.();
    });

    function renderTracks(tracks) {
        const tableBody = $('#tracks-table-body');
        const cardsContainer = $('#tracks-cards-container');
        const { tableHtml, cardsHtml } = buildTrackListMarkup(tracks, context.openIconUrl);
        tableBody.html(tableHtml);
        cardsContainer.html(cardsHtml);
    }

    const listApi = attachTaggedEntityList({
        listEndpoint: context.listEndpoint,
        renderList: renderTracks,
        entityLabel: 'GPS track',
        loadFailedMessage: 'Error loading GPS tracks',
    });

    window.addEventListener('speleo:refresh-gps-tracks', () => listApi.reload());
}
