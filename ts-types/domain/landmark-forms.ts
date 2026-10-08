import type { EntityId } from './identifiers.ts';
import type { ViewerLandmark } from './map-entities.ts';

export interface LandmarkFormCollection {
    id: EntityId;
    name?: string;
    color?: string | null;
    is_personal?: boolean;
    can_write?: boolean;
}
export type LandmarkFormCollections = Map<EntityId, LandmarkFormCollection> | LandmarkFormCollection[];
export interface LandmarkFormPayload {
    name: string;
    description: string;
    collection: string | null;
    latitude: number;
    longitude: number;
}
export interface LandmarkCoordinates { latitude?: number | string; longitude?: number | string }
export interface LandmarkCreateOptions {
    collections?: LandmarkFormCollections;
    lockedCollectionId?: EntityId | null;
    coordinateDefaults?: LandmarkCoordinates | null;
    onSuccess?: ((response: unknown) => unknown) | null;
}
export interface LandmarkEditOptions extends LandmarkCreateOptions {
    landmark?: ViewerLandmark | null;
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
export interface LandmarkBulkOptions {
    landmarks?: ViewerLandmark[];
    sourceCollection?: LandmarkFormCollection | EntityId | null;
    collections?: LandmarkFormCollections;
    onSuccess?: ((response: unknown) => unknown) | null;
}
export interface LandmarkBulkPayload { landmark_ids: EntityId[]; target_collection?: EntityId }
export interface LandmarkErrorData {
    error?: unknown;
    detail?: unknown;
    errors?: Record<string, unknown>;
}
