import type { ViewerLandmark } from './map-entities.ts';
import type { LandmarkFormCollection } from './landmark-forms.ts';

export interface LandmarkCollectionContext {
    id: string | number;
    name: string;
    color: string;
    is_personal: boolean;
}
export interface LandmarkCollectionDetailsState {
    canWrite: boolean;
    sourceCollection: LandmarkFormCollection | null;
    landmarksById: Map<string, ViewerLandmark>;
    collections: LandmarkFormCollection[];
    selection: Set<string | undefined>;
    table: DataTableApi | null;
}
export interface LandmarkBulkResult {
    target_collection?: { name?: string };
    transferred?: number;
    deleted?: number;
}
