import type { GISListRecord, GISListPresentation, GISDetailsRoute } from '../../ts-types/controllers/gis-lists.ts';
import type { EntityId } from '../../ts-types/domain/identifiers.ts';
import { escapeHtml, safeCssColor, sanitizeUrl } from '../../frontend_private/static/private/ts/xss-helpers.ts';

const FALLBACK_COLOR = '#94a3b8';
export const SUPPORTED_FORMATS_LABEL = 'KML, KMZ, GeoJSON, TopoJSON, or a zipped Shapefile';

function formatDate(dateString: string | undefined) {
    const date = new Date(dateString as string);
    if (Number.isNaN(date.getTime())) return 'Unknown';
    return date.toLocaleDateString('en-US', {
        year: 'numeric', month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit',
    });
}

function routeUrl(routeName: 'api:v2:gis-layer-source' | GISDetailsRoute, layerId: EntityId) {
    const route = globalThis.Urls?.[routeName];
    return typeof route === 'function' ? sanitizeUrl(route(layerId)) : '';
}

function normalizedPermissionLabel(label: string | null | undefined) {
    if (!label) return 'Unknown';
    return String(label).toLowerCase().split('_')
        .map(word => word.charAt(0).toUpperCase() + word.slice(1)).join(' ');
}

function permissionPillClass(label: string | null | undefined) {
    return ({
        READ_ONLY: 'bg-pastel-beige',
        READ_AND_WRITE: 'bg-pastel-navy',
        ADMIN: 'bg-pastel-orange',
    })[label as 'READ_ONLY' | 'READ_AND_WRITE' | 'ADMIN'] || 'bg-slate-700 text-slate-300';
}

function renderDesktopActions(layer: GISListRecord, openIconUrl: string, options: GISListPresentation) {
    const sourceUrl = escapeHtml(routeUrl('api:v2:gis-layer-source', layer.id));
    const detailsUrl = escapeHtml(routeUrl(options.detailsRoute, layer.id));
    const iconUrl = escapeHtml(sanitizeUrl(openIconUrl));
    return `
        ${options.showSource ? `<a class="inline-flex cursor-pointer" href="${sourceUrl}" title="Download original source" aria-label="Download GIS Layer source">
            <svg class="h-6 w-6 stroke-current text-cyan-500 hover:text-cyan-400" viewBox="0 0 24 24" stroke-width="1.5" fill="none" stroke-linecap="round" stroke-linejoin="round">
                <path d="M12 3v12"></path><path d="M8 11l4 4 4-4"></path><path d="M5 21h14"></path>
            </svg>
        </a>` : ''}
        <div class="w-10 aspect-square min-w-0 shrink bg-slate-700 rounded-full">
            <a class="flex items-center justify-center w-full h-full" href="${detailsUrl}" title="${options.showSource ? 'Open layer settings' : 'Open geometry settings'}" aria-label="Open ${escapeHtml(options.entityLabel)} settings">
                <img class="w-5 h-5" src="${iconUrl}" alt="Icon Open">
            </a>
        </div>`;
}

function renderMobileActions(layer: GISListRecord, openIconUrl: string, options: GISListPresentation) {
    const sourceUrl = escapeHtml(routeUrl('api:v2:gis-layer-source', layer.id));
    const detailsUrl = escapeHtml(routeUrl(options.detailsRoute, layer.id));
    const iconUrl = escapeHtml(sanitizeUrl(openIconUrl));
    return `
        ${options.showSource ? `<a class="w-10 h-10 shrink-0 flex items-center justify-center bg-cyan-600 hover:bg-cyan-500 rounded-full transition" href="${sourceUrl}" aria-label="Download GIS Layer source">
            <svg class="h-5 w-5 text-white" viewBox="0 0 24 24" stroke-width="1.5" fill="none" stroke="currentColor"><path d="M12 3v12"></path><path d="M8 11l4 4 4-4"></path><path d="M5 21h14"></path></svg>
        </a>` : ''}
        <a class="w-10 h-10 shrink-0 flex items-center justify-center bg-indigo-600 hover:bg-indigo-500 rounded-full transition" href="${detailsUrl}" aria-label="Open ${escapeHtml(options.entityLabel)} settings">
            <img class="ml-1" src="${iconUrl}" width="20" height="20" alt="View">
        </a>`;
}

export function buildGISOverlayListMarkup(layers: GISListRecord[], openIconUrl = '', configuration: Partial<GISListPresentation> = {}) {
    const options: GISListPresentation = {
        entityLabel: 'GIS Layer',
        pluralLabel: 'GIS Layers',
        detailsRoute: 'private:gis_layer_details',
        showSource: true,
        emptyHint: `Upload ${SUPPORTED_FORMATS_LABEL} to add your first layer`,
        ...configuration,
    };
    const columnCount = options.showSource ? 7 : 6;
    if (!Array.isArray(layers) || layers.length === 0) {
        const emptyStateHtml = `
            <svg class="w-16 h-16 center-x mb-4 text-slate-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 7l8-4 8 4-8 4-8-4zm0 5l8 4 8-4M4 17l8 4 8-4"></path>
            </svg>
            <p class="text-lg font-medium">No ${escapeHtml(options.pluralLabel)} yet</p>
            <p class="text-sm mt-1">${escapeHtml(options.emptyHint)}</p>`;
        return {
            tableHtml: `<tr><td colspan="${columnCount}" class="px-2 py-8 text-center text-slate-400">${emptyStateHtml}</td></tr>`,
            cardsHtml: `<div class="text-center py-12 text-slate-400">${emptyStateHtml}</div>`,
        };
    }

    const sortedLayers = [...layers].sort((a, b) => String(a.name).localeCompare(String(b.name), undefined, { sensitivity: 'base' }));
    const tableHtml = sortedLayers.map((layer, index) => {
        const permissionLabel = normalizedPermissionLabel(layer.user_permission_level_label);
        return `
            <tr>
                <td class="px-2 first:pl-5 last:pr-5 py-3"><div class="text-center font-medium text-slate-100">${index + 1}</div></td>
                <td class="px-2 first:pl-5 last:pr-5 py-3">
                    <div class="flex items-start gap-3">
                        <div class="w-3 h-3 mt-1 rounded-full shrink-0" style="background-color: ${safeCssColor(layer.color, FALLBACK_COLOR)}"></div>
                        <div class="min-w-0"><div class="font-medium text-slate-100 break-words">${escapeHtml(layer.name)}</div>${layer.description ? `<div class="text-xs text-slate-400 mt-1 break-words">${escapeHtml(layer.description)}</div>` : ''}</div>
                    </div>
                </td>
                <td class="px-2 first:pl-5 last:pr-5 py-3"><div class="text-center text-slate-300 text-sm break-words">${escapeHtml(layer.created_by || '—')}</div></td>
                <td class="px-2 first:pl-5 last:pr-5 py-3"><div class="text-center"><span class="inline-flex font-medium ${permissionPillClass(layer.user_permission_level_label)} rounded-full px-2.5 py-0.5">${escapeHtml(permissionLabel)}</span></div></td>
                ${options.showSource ? `<td class="px-2 first:pl-5 last:pr-5 py-3"><div class="text-center text-sm uppercase text-slate-300">${escapeHtml(layer.source_format || '—')}</div></td>` : ''}
                <td class="px-2 first:pl-5 last:pr-5 py-3"><div class="text-center text-slate-400 text-sm">${escapeHtml(formatDate(layer.creation_date))}</div></td>
                <td class="px-2 first:pl-5 last:pr-5 py-3"><div class="flex items-center justify-center gap-2">${renderDesktopActions(layer, openIconUrl, options)}</div></td>
            </tr>`;
    }).join('');

    const cardsHtml = sortedLayers.map(layer => {
        const permissionLabel = normalizedPermissionLabel(layer.user_permission_level_label);
        return `
            <div class="track-card gis-layer-card">
                <div class="track-card-header">
                    <div class="track-card-title flex items-start gap-3">
                        <div class="w-4 h-4 mt-1 rounded-full shrink-0" style="background-color: ${safeCssColor(layer.color, FALLBACK_COLOR)}"></div>
                        <div class="min-w-0"><div class="text-lg font-semibold text-slate-100 break-words">${escapeHtml(layer.name)}</div>${layer.description ? `<div class="text-xs text-slate-400 mt-1 break-words">${escapeHtml(layer.description)}</div>` : ''}</div>
                    </div>
                    <div class="track-card-actions">${renderMobileActions(layer, openIconUrl, options)}</div>
                </div>
                <div class="track-card-body">
                    <div class="track-card-row"><span class="track-card-label">Creator</span><span class="track-card-value">${escapeHtml(layer.created_by || '—')}</span></div>
                    <div class="track-card-row"><span class="track-card-label">Access</span><span class="inline-flex font-medium ${permissionPillClass(layer.user_permission_level_label)} rounded-full px-2.5 py-0.5">${escapeHtml(permissionLabel)}</span></div>
                    ${options.showSource ? `<div class="track-card-row"><span class="track-card-label">Source</span><span class="track-card-value uppercase">${escapeHtml(layer.source_format || '—')}</span></div>` : ''}
                    <div class="track-card-row"><span class="track-card-label">Created</span><span class="track-card-value">${escapeHtml(formatDate(layer.creation_date))}</span></div>
                </div>
            </div>`;
    }).join('');
    return { tableHtml, cardsHtml };
}

export function buildGISLayerListMarkup(layers: GISListRecord[], openIconUrl = '') {
    return buildGISOverlayListMarkup(layers, openIconUrl);
}

export function buildGISGeometryListMarkup(geometries: GISListRecord[], openIconUrl = '') {
    return buildGISOverlayListMarkup(geometries, openIconUrl, {
        entityLabel: 'GIS Geometry',
        pluralLabel: 'GIS Geometries',
        detailsRoute: 'private:gis_geometry_details',
        showSource: false,
        emptyHint: 'Create a line or polygon on the survey map to get started.',
    });
}
