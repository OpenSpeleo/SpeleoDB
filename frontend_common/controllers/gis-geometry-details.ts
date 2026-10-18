import { v2GisGeometriesPartialUpdateWithJson } from '@speleodb/api';
import { apiData, ApiRequestError, webApiOptions } from '../api/client.ts';
import { isGeometryAliasValid } from '@speleodb/map-core';
import type { GISGeometryDetailsContext, ParsedGeometryText } from '../../ts-types/controllers/gis-geometry-details.ts';
import type { EditableGeometry } from '../../ts-types/domain/geometry-editor.ts';
import { afterWindowLoad } from '../readiness.ts';
import { _hexBodyRe, initColorPicker } from '../../frontend_private/static/private/ts/color-picker.ts';
import { attachEntityCrudForm } from '../../frontend_private/static/private/ts/forms/entity_crud_form.ts';
import { DEFAULTS } from '../../frontend_private/static/private/ts/map_viewer/config.ts';
import { validateGeometry } from '../../frontend_private/static/private/ts/map_viewer/geometry_editor/geometry.ts';

export function parseGeometryText(text: string): ParsedGeometryText {
    let geometry: unknown;
    try {
        geometry = JSON.parse(text);
    } catch {
        return { valid: false, error: 'Enter valid JSON. Your changes have not been saved.' };
    }
    // Preserve the parsed value, including invalid shapes, without normalizing it.
    return { ...validateGeometry(geometry), geometry: geometry as EditableGeometry };
}

function responseError(xhr: unknown) {
    if (!(xhr instanceof ApiRequestError)) return 'Unable to save. Your changes are still here. Check your connection and try again.';
    const response = xhr.data as { error?: unknown; errors?: unknown } | undefined;
    if (xhr.status === 409) {
        return 'This geometry changed while you were editing. Your changes have not been saved. Copy your GeoJSON before reloading to review the latest version.';
    }
    if (xhr.status === 403) {
        return 'You no longer have permission to edit this geometry. Your changes have not been saved.';
    }
    if (typeof response?.error === 'string') return response.error;
    const errors = response?.errors || response;
    if (errors && typeof errors === 'object') {
        for (const value of Object.values(errors)) {
            if (Array.isArray(value) && value.length) return String(value[0]);
            if (typeof value === 'string') return value;
        }
    }
    return 'Unable to save. Your changes are still here. Check your connection and try again.';
}

export async function init(context: GISGeometryDetailsContext) {
    await afterWindowLoad();
    const form = document.getElementById(context.formId);
    const textarea = document.getElementById('geometry-geojson') as HTMLTextAreaElement;
    if (!form || !textarea) return;
    const name = form.querySelector<HTMLInputElement>('[name="name"]')!;
    const alias = form.querySelector<HTMLInputElement>('[name="alias"]')!;
    const description = form.querySelector<HTMLTextAreaElement>('[name="description"]')!;
    const color = form.querySelector<HTMLInputElement>('[name="color"]')!;
    const colorHex = document.getElementById('color-hex-input') as HTMLInputElement | null;
    const submit = document.getElementById('btn_submit') as HTMLButtonElement;
    const error = document.getElementById('geometry-error')!;
    const summary = document.getElementById('geometry-summary')!;
    const jsonStatus = document.getElementById('geometry-json-status')!;
    const saved = document.getElementById('geometry-saved')!;
    let revision = context.revision;
    let pending = false;
    let permissionLost = false;
    let baseline = { name: name.value, alias: alias.value, description: description.value, color: color.value, text: textarea.value };

    function changed() {
        return name.value !== baseline.name || alias.value !== baseline.alias || description.value !== baseline.description || color.value !== baseline.color || textarea.value !== baseline.text;
    }

    function showError(message: string) {
        error.textContent = message || '';
        error.hidden = !message;
    }

    function invalidColor() {
        return colorHex && !_hexBodyRe.test(colorHex.value);
    }

    function refresh() {
        const validation = parseGeometryText(textarea.value);
        textarea.setAttribute('aria-invalid', String(!validation.valid));
        const area = validation.areaKm2;
        const warning = validation.areaM2! > DEFAULTS.GIS_GEOMETRY.WARNING_AREA_M2;
        const maximumArea = DEFAULTS.GIS_GEOMETRY.MAX_AREA_M2 / DEFAULTS.GIS_GEOMETRY.SQUARE_METRES_PER_SQUARE_KILOMETRE;
        const warningText = warning ? (validation.valid ? ` · Area warning (${maximumArea.toLocaleString()} km² maximum)` : ' · Cannot save') : '';
        summary.classList.toggle('geometry-details__summary--invalid', !validation.valid);
        summary.classList.toggle('geometry-details__summary--warning', validation.valid && warning);
        summary.textContent = Number.isFinite(area)
            ? `${validation.geometry?.type || 'Invalid geometry'} · ${validation.vertexCount} / ${DEFAULTS.GIS_GEOMETRY.MAX_VERTICES} vertices · Bounding-box area: ${area!.toLocaleString(undefined, { maximumFractionDigits: 6 })} km²${warningText}`
            : 'Check the GeoJSON below to complete this geometry.';
        jsonStatus.textContent = !validation.valid ? '— Needs attention' : textarea.value !== baseline.text ? '— Unsaved changes' : '';
        if (submit) submit.disabled = (pending || permissionLost || !validation.valid || invalidColor() || !name.value.trim() || !isGeometryAliasValid(alias.value) || !changed());
        return validation;
    }

    refresh();
    if (!context.canWrite) return;

    const setColor = initColorPicker({
        preview: '#color-preview', hiddenInput: '#color-value',
        nativePicker: '#color-picker', pickerBtn: '#color-picker-btn',
        hexInput: '#color-hex-input', presets: '.color-preset',
    });

    form.addEventListener('input', () => {
        saved.hidden = true;
        const validation = refresh();
        showError(!validation.valid ? validation.error : invalidColor() ? 'Enter a six-digit hex color.' : !isGeometryAliasValid(alias.value) ? `Alias must be at most ${DEFAULTS.GIS_GEOMETRY.ALIAS_MAX_LENGTH} characters.` : '');
    });
    form.addEventListener('change', refresh);
    // Color presets update their hidden input synchronously without a DOM change event.
    form.addEventListener('click', event => {
        if ((event.target as Element).closest('.color-preset')) refresh();
    });
    const beforeUnload = (event: BeforeUnloadEvent) => {
        if (!changed()) return;
        event.preventDefault();
        event.returnValue = '';
    };
    window.addEventListener('beforeunload', beforeUnload);

    attachEntityCrudForm({
        formId: context.formId,
        submit: () => apiData(v2GisGeometriesPartialUpdateWithJson(context.geometryId, {
            name: name.value.trim(), alias: alias.value.trim(), description: description.value.trim(), color: color.value,
            expected_revision: revision,
            ...(textarea.value !== baseline.text ? { geojson: parseGeometryText(textarea.value).geometry } : {}),
        }, webApiOptions())),
        submitOnForm: true,
        showSuccessModal: false,
        beforeSubmit(payload) {
            const validation = refresh();
            if (pending || permissionLost || !validation.valid || invalidColor() || !name.value.trim() || !isGeometryAliasValid(alias.value) || !changed()) {
                showError(validation.error || (invalidColor() ? 'Enter a six-digit hex color.' : !name.value.trim() ? 'Enter a geometry name.' : !isGeometryAliasValid(alias.value) ? `Alias must be at most ${DEFAULTS.GIS_GEOMETRY.ALIAS_MAX_LENGTH} characters.` : ''));
                return false;
            }
            delete payload.csrfmiddlewaretoken;
            payload.name = name.value.trim();
            payload.alias = alias.value.trim();
            payload.description = description.value.trim();
            payload.color = color.value;
            payload.expected_revision = revision;
            if (textarea.value !== baseline.text) payload.geojson = validation.geometry;
            showError('');
            saved.hidden = true;
            return true;
        },
        onPendingChange(value) {
            pending = value;
            form.setAttribute('aria-busy', String(value));
            // Do not let edits made during a request be overwritten by its response.
            name.readOnly = value;
            textarea.readOnly = value;
            const metadataFields = form.querySelector('fieldset');
            if (metadataFields) metadataFields.disabled = value;
            submit.textContent = value ? 'Saving…' : 'Save Changes';
            refresh();
        },
        onSuccess(response) {
            revision = response.revision;
            name.value = response.name;
            alias.value = response.alias;
            description.value = response.description;
            setColor(response.color);
            textarea.value = JSON.stringify(response.geojson, null, 2);
            baseline = { name: name.value, alias: alias.value, description: description.value, color: color.value, text: textarea.value };
            showError('');
            saved.hidden = false;
            refresh();
        },
        onError(xhr) {
            if (xhr instanceof ApiRequestError && xhr.status === 403) permissionLost = true;
            showError(responseError(xhr));
        },
    });
    return () => window.removeEventListener('beforeunload', beforeUnload);
}
