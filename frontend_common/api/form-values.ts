import { StationResourceRequestResourceType, PatchedStationResourceRequestResourceType, PatchedSensorInstallRequestStatus } from '@speleodb/api';
import type { StationLogEntryRequest, V2StationsResourcesCreateBodyThree, PatchedStationResourceRequest, PatchedSensorInstallRequest, V2ImportGpxUpdateBody } from '@speleodb/api';

/** HTML form values become typed SDK inputs before the generator serializes them. */
export function formText(data: FormData, key: string): string {
    const value = data.get(key);
    return typeof value === 'string' ? value : '';
}

export function formFile(data: FormData, key: string): File | undefined {
    const value = data.get(key);
    return value instanceof File && value.size > 0 ? value : undefined;
}

export function logBody(data: FormData): StationLogEntryRequest {
    const attachment = formFile(data, 'attachment');
    return { title: formText(data, 'title'), notes: formText(data, 'notes'), ...(attachment ? { attachment } : {}) };
}

export function resourceBody(data: FormData): V2StationsResourcesCreateBodyThree {
    const resourceType = Object.values(StationResourceRequestResourceType).find(value => value === formText(data, 'resource_type'));
    if (!resourceType) throw new Error('Choose a resource type.');
    const file = formFile(data, 'file');
    const miniature = formFile(data, 'miniature');
    const content = {
        title: formText(data, 'title'),
        description: formText(data, 'description'),
        text_content: formText(data, 'text_content'),
    };
    if (resourceType === 'note') {
        if (!content.text_content.trim()) throw new Error('Enter text for the note.');
        if (file || miniature) throw new Error('Notes cannot contain uploaded files.');
        return { ...content, resource_type: resourceType };
    }
    if (!file) throw new Error('Choose a resource file.');
    return { ...content, resource_type: resourceType, file, ...(miniature ? { miniature } : {}) };
}

/** Disabled edit controls are absent from FormData and must stay absent in PATCH. */
export function resourceUpdateBody(data: FormData): PatchedStationResourceRequest {
    const body: PatchedStationResourceRequest = {};
    for (const field of ['title', 'description', 'text_content'] as const) {
        if (data.has(field)) body[field] = formText(data, field);
    }
    if (data.has('resource_type')) {
        const resourceType = Object.values(PatchedStationResourceRequestResourceType).find(value => value === formText(data, 'resource_type'));
        if (!resourceType) throw new Error('Choose a resource type.');
        body.resource_type = resourceType;
    }
    for (const field of ['file', 'miniature'] as const) {
        const file = formFile(data, field);
        if (file) body[field] = file;
    }
    return body;
}

export function sensorBody(data: FormData): PatchedSensorInstallRequest {
    const body: PatchedSensorInstallRequest = {};
    for (const field of ['sensor', 'install_date', 'install_user'] as const) {
        if (data.has(field)) body[field] = formText(data, field);
    }
    for (const field of ['expiracy_memory_date', 'expiracy_battery_date', 'uninstall_date', 'uninstall_user'] as const) {
        if (!data.has(field)) continue;
        const value = formText(data, field);
        body[field] = value && value !== 'null' ? value : null;
    }
    if (data.has('status')) {
        const status = Object.values(PatchedSensorInstallRequestStatus).find(value => value === formText(data, 'status'));
        if (!status) throw new Error('Choose a sensor installation status.');
        body.status = status;
    }
    return body;
}

export function gpxBody(data: FormData): V2ImportGpxUpdateBody {
    const file = formFile(data, 'file');
    if (!file) throw new Error('Choose a GPX file.');
    const collection = formText(data, 'collection');
    return { file, ...(collection ? { collection } : {}) };
}
