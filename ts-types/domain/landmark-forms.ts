import type { EntityId } from './identifiers.ts';
import type { Landmark, LandmarkCollectionWithPerm, LandmarkRequest, LandmarkUpdateResponse } from '@speleodb/api';
import type { ViewerLandmark } from './map-entities.ts';

/** Partial cached collection values displayed in the form picker. */
export type LandmarkFormCollection = Partial<Pick<LandmarkCollectionWithPerm, 'name' | 'is_personal'>> & {
    id: EntityId;
    can_write?: boolean;
    color?: LandmarkCollectionWithPerm['color'] | null;
};
export type LandmarkFormCollections = Map<EntityId, LandmarkFormCollection> | LandmarkFormCollection[];
/** The DOM parser produces numbers and fills every editable form field. */
export type LandmarkFormPayload = Required<Pick<LandmarkRequest, 'icon' | 'name' | 'description' | 'collection'>> & {
    latitude: number;
    longitude: number;
};
export interface LandmarkCoordinates { latitude?: number | string; longitude?: number | string }
export interface LandmarkCreateOptions {
    collections?: LandmarkFormCollections;
    lockedCollectionId?: EntityId | null;
    coordinateDefaults?: LandmarkCoordinates | null;
    onSuccess?: ((response: Landmark) => unknown) | null;
}
export interface LandmarkEditOptions extends Omit<LandmarkCreateOptions, 'onSuccess'> {
    landmark?: ViewerLandmark | null;
    onSuccess?: ((response: LandmarkUpdateResponse) => unknown) | null;
}
export interface LandmarkRenderOptions extends Omit<LandmarkCreateOptions, 'onSuccess'> {
    mode: 'create' | 'edit';
    landmark?: Partial<ViewerLandmark> | null;
    formId: string;
    errorElId: string;
}
export interface LandmarkDeleteOptions {
    landmark?: ViewerLandmark | null;
    onSuccess?: ((id: EntityId) => unknown) | null;
}
export interface LandmarkBulkOptions<Response> {
    landmarks?: ViewerLandmark[];
    sourceCollection?: LandmarkFormCollection | EntityId | null;
    collections?: LandmarkFormCollections;
    onSuccess?: ((response: Response) => unknown) | null;
}
/** Selection state uses local entity identities; the operation converts them to UUID strings. */
export interface LandmarkBulkPayload { landmark_ids: EntityId[]; target_collection?: EntityId }
export interface LandmarkErrorData {
    error?: unknown;
    detail?: unknown;
    errors?: Record<string, unknown>;
}
