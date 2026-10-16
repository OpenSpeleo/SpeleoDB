import type { EntityId } from '../../../../../../ts-types/domain/identifiers.ts';
import { LANDMARK_ICON_OPTIONS, normalizeLandmarkIcon } from '@speleodb/map-core';
import { LANDMARK_ICON_URLS } from '@speleodb/map-viewer/landmark-icons';
import type { ViewerLandmark } from '../../../../../../ts-types/domain/map-entities.ts';
import type { LandmarkFormCollection, LandmarkFormCollections, LandmarkRenderOptions } from '../../../../../../ts-types/domain/landmark-forms.ts';
import { Utils } from '../utils.ts';
import { getCollectionLabel, findCollection, listCollections, compareCollections } from './form_model.ts';

const COLLECTION_FALLBACK_COLOR = '#94a3b8';

// ---------- HTML renderers (pure, exported for tests) ----------

export function getCollectionColor(collection: LandmarkFormCollection | null) {
    return Utils.safeCssColor(collection?.color || COLLECTION_FALLBACK_COLOR);
}

export function getWritableCollectionOptions(collections: LandmarkFormCollections, selectedId: EntityId | null | undefined, excludeId: EntityId | null = null) {
    const writable = listCollections(collections)
        .filter(c => c.can_write)
        .filter(c => excludeId == null || String(c.id) !== String(excludeId))
        .sort(compareCollections);

    return writable
        .map(c => Utils.safeHtml`
            <option value="${String(c.id)}" ${String(c.id) === String(selectedId) ? 'selected' : ''}>
                ${getCollectionLabel(c)}
            </option>`)
        .join('');
}

export function renderCollectionField({ id, collections, selectedId, lockedCollection }: { id: string; collections: LandmarkFormCollections; selectedId: EntityId | null | undefined; lockedCollection: LandmarkFormCollection | null }) {
    if (lockedCollection) {
        const swatch = getCollectionColor(lockedCollection);
        return Utils.safeHtml`
            <div>
                <label class="block text-sm font-medium text-slate-300 mb-2">Collection</label>
                <div class="flex items-center gap-2 bg-srgb-slate-700-40 border border-slate-600 rounded-sm px-3 py-2 text-slate-200 text-sm">
                    <span class="inline-block w-3 h-3 rounded-full border border-slate-500 shrink-0" style="background-color: ${Utils.raw(swatch)}"></span>
                    <span class="truncate">${getCollectionLabel(lockedCollection)}</span>
                </div>
                <input type="hidden" id="${id}" value="${String(lockedCollection.id)}">
            </div>`;
    }

    const writable = listCollections(collections).filter(c => c.can_write);
    const personal = writable.find(c => c.is_personal) || null;
    const effectiveSelected = selectedId || personal?.id || null;
    const options = getWritableCollectionOptions(collections, effectiveSelected);
    const fallbackPersonalOption = personal
        ? ''
        : '<option value="">Personal Landmarks</option>';
    return Utils.safeHtml`
        <div>
            <label class="block text-sm font-medium text-slate-300 mb-2">Collection</label>
            <select id="${id}" class="form-input">
                ${Utils.raw(fallbackPersonalOption)}
                ${Utils.raw(options)}
            </select>
        </div>`;
}

export function renderLandmarkFormHtml({
    mode,
    landmark = null,
    collections = [],
    lockedCollectionId = null,
    formId,
    errorElId,
    coordinateDefaults = null,
}: LandmarkRenderOptions) {
    const isEdit = mode === 'edit';
    const lockedCollection = lockedCollectionId
        ? findCollection(collections, lockedCollectionId)
        : null;

    const name = isEdit ? (landmark?.name ?? '') : '';
    const description = isEdit ? (landmark?.description ?? '') : '';
    const lat = isEdit
        ? Number(landmark?.latitude ?? 0).toFixed(7)
        : (coordinateDefaults?.latitude != null
            ? String(coordinateDefaults.latitude)
            : '');
    const lon = isEdit
        ? Number(landmark?.longitude ?? 0).toFixed(7)
        : (coordinateDefaults?.longitude != null
            ? String(coordinateDefaults.longitude)
            : '');
    const selectedCollectionId = isEdit ? landmark?.collection : null;


    return Utils.safeHtml`
        <form id="${formId}" class="flow-y-4" novalidate>
            <div>
                <label class="block text-sm font-medium text-slate-300 mb-2">Name *</label>
                <input type="text" id="${formId}-name" required value="${name}" class="form-input" placeholder="Landmark name">
            </div>
            <div>
                <label class="block text-sm font-medium text-slate-300 mb-2">Description</label>
                <textarea id="${formId}-description" rows="3" class="form-input form-textarea" placeholder="Optional description">${description}</textarea>
            </div>
            ${Utils.raw(renderCollectionField({
                id: `${formId}-collection`,
                collections,
                selectedId: selectedCollectionId,
                lockedCollection,
            }))}
            ${Utils.raw(renderLandmarkIconPicker(landmark?.icon))}
            <div class="grid grid-cols-2 gap-4">
                <div>
                    <label class="block text-sm font-medium text-slate-300 mb-2">Latitude * <span class="text-xs text-slate-500">(-90 to 90)</span></label>
                    <input type="number" id="${formId}-latitude" required step="any" min="-90" max="90" value="${lat}" class="form-input" placeholder="Latitude">
                </div>
                <div>
                    <label class="block text-sm font-medium text-slate-300 mb-2">Longitude * <span class="text-xs text-slate-500">(-180 to 180)</span></label>
                    <input type="number" id="${formId}-longitude" required step="any" min="-180" max="180" value="${lon}" class="form-input" placeholder="Longitude">
                </div>
            </div>
            <div id="${errorElId}" class="hidden text-red-400 text-sm p-2 bg-srgb-red-500-10 rounded-lg"></div>
        </form>`;
}

/** Shared by map creation/editing and collection detail forms. */
export function renderLandmarkIconPicker(value?: unknown) {
    const icon = normalizeLandmarkIcon(value);
    const iconChoices = LANDMARK_ICON_OPTIONS.map(option => {
        // JSON quotes keep CSS data URLs valid when Vite inlines SVG apostrophes.
        // safeHtml then escapes the complete CSS value for the HTML attribute.
        const iconUrl = `url(${JSON.stringify(LANDMARK_ICON_URLS[option.value])})`;
        return Utils.safeHtml`
            <label class="landmark-icon-choice">
                <input type="radio" name="icon" value="${option.value}" ${option.value === icon ? 'checked' : ''}>
                <span class="landmark-icon-choice__preview" aria-hidden="true" style="mask-image: ${iconUrl}; -webkit-mask-image: ${iconUrl}"></span>
                <span>${option.label}</span>
            </label>`;
    }).join('');
    return Utils.safeHtml`
        <fieldset class="landmark-icon-picker">
            <legend class="block text-sm font-medium text-slate-300 mb-2">Icon</legend>
            <div class="landmark-icon-picker__choices">${Utils.raw(iconChoices)}</div>
            <p class="text-xs text-slate-400 mt-2">Icons use the collection color.</p>
        </fieldset>`;
}

/** Native radio inputs keep the shared map/table picker keyboard accessible. */
export function initializeLandmarkIconPicker(form: HTMLElement, collections: LandmarkFormCollections, lockedCollectionId?: EntityId | null) {
    const collectionSelect = form.querySelector<HTMLSelectElement | HTMLInputElement>('select, input[type="hidden"][id$="-collection"]');
    const refresh = () => {
        const id = lockedCollectionId || collectionSelect?.value;
        const collection = findCollection(collections, id)
            || listCollections(collections).find(item => item.is_personal) || null;
        form.querySelector<HTMLElement>('.landmark-icon-picker__choices')!.style.color = getCollectionColor(collection);
    };
    collectionSelect?.addEventListener('change', refresh);
    refresh();
}

export function renderSelectedLandmarksList(landmarks: ViewerLandmark[]) {
    const visible = landmarks.slice(0, 10);
    const overflow = landmarks.length - visible.length;
    const items = visible
        .map(lm => Utils.safeHtml`<li class="truncate">${lm.name || 'Unnamed Landmark'}</li>`)
        .join('');
    const overflowHtml = overflow > 0
        ? Utils.safeHtml`<li class="text-slate-400 italic">... and ${String(overflow)} more</li>`
        : '';
    return Utils.safeHtml`
        <ul class="list-disc pl-5 text-sm text-slate-300 flow-y-0.5 max-h-40 overflow-y-auto">
            ${Utils.raw(items)}
            ${Utils.raw(overflowHtml)}
        </ul>`;
}
