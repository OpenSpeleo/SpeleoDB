import type { EntityId } from '../../../../../../ts-types/domain/identifiers.ts';
import type { LandmarkFormCollection, LandmarkFormCollections, LandmarkFormPayload } from '../../../../../../ts-types/domain/landmark-forms.ts';

export function getCollectionLabel(collection: LandmarkFormCollection | null) {
    if (!collection) return 'Personal Landmarks';
    if (collection.is_personal) {
        return `${collection.name || 'Personal Landmarks'} (Private)`;
    }
    return collection.name || 'Unnamed Collection';
}

export function findCollection(collections: LandmarkFormCollections | null | undefined, id: EntityId | null | undefined) {
    if (!collections || id == null) return null;
    const needle = String(id);
    if (collections instanceof Map) {
        return collections.get(needle) || null;
    }
    return collections.find(c => String(c.id) === needle) || null;
}

export function listCollections(collections: LandmarkFormCollections | null | undefined) {
    if (!collections) return [];
    if (collections instanceof Map) return Array.from(collections.values());
    return [...collections];
}

export function compareCollections(a: LandmarkFormCollection, b: LandmarkFormCollection) {
    if (a.is_personal !== b.is_personal) return a.is_personal ? -1 : 1;
    return (a.name || '').localeCompare(b.name || '');
}

export function getSelectedCollection(id: string, lockedCollectionId: EntityId | null | undefined) {
    if (lockedCollectionId) return String(lockedCollectionId);
    const select = document.getElementById(id) as HTMLSelectElement | HTMLInputElement | null;
    if (!select || !select.value) return null;
    return select.value;
}

export function readLandmarkFormPayload(formId: string, lockedCollectionId?: EntityId | null): LandmarkFormPayload {
    const name = (document.getElementById(`${formId}-name`) as HTMLInputElement).value.trim();
    const description = (document.getElementById(`${formId}-description`) as HTMLInputElement).value.trim();
    const latStr = (document.getElementById(`${formId}-latitude`) as HTMLInputElement).value;
    const lonStr = (document.getElementById(`${formId}-longitude`) as HTMLInputElement).value;
    return {
        name,
        description,
        collection: getSelectedCollection(`${formId}-collection`, lockedCollectionId),
        latitude: parseFloat(latStr),
        longitude: parseFloat(lonStr),
    };
}

export function validateLandmarkFormPayload(payload: Pick<LandmarkFormPayload, 'name' | 'latitude' | 'longitude'>) {
    if (!payload.name) return 'Please enter a landmark name.';
    if (Number.isNaN(payload.latitude) || payload.latitude < -90 || payload.latitude > 90) {
        return 'Latitude must be a number between -90 and 90.';
    }
    if (Number.isNaN(payload.longitude) || payload.longitude < -180 || payload.longitude > 180) {
        return 'Longitude must be a number between -180 and 180.';
    }
    return null;
}
