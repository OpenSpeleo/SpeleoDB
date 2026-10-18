import type { GISLayer, LandmarkCollectionWithPerm, V2ImportGpxUpdate200, V2ImportKmlKmzUpdate200, V2ImportKmlKmzInspectCreate200 } from '@speleodb/api';
import type { EntityId } from './identifiers.ts';
import type { CameraBounds } from './map-geometry.ts';
import type { ImportedMapResult } from './map-import.ts';

export type ImportTab = 'gpx' | 'kml';
export type ImportMode = 'places' | 'overlay';
/** Review presentation accepts partial counts; submission additionally validates eligibility. */
export type ImportReview = Partial<Omit<V2ImportKmlKmzInspectCreate200, 'places' | 'overlay'>> & {
    places: Partial<NonNullable<V2ImportKmlKmzInspectCreate200['places']>>;
    overlay: Partial<NonNullable<V2ImportKmlKmzInspectCreate200['overlay']>>;
};
export interface ImportEligibility {
    file?: File | null;
    report?: ImportReview | null;
    mode?: ImportMode | null;
    collectionId?: string;
    layerName?: string;
    busy?: boolean;
    uncertain?: boolean;
}
export type ImportCollection = Pick<LandmarkCollectionWithPerm, 'name'> &
    Partial<Pick<LandmarkCollectionWithPerm, 'is_personal'>> & { id: EntityId; can_write?: boolean };
/** Shared display projection across overlay, GPX, and places import results. */
export type ImportResultFields = Partial<Pick<GISLayer, 'id' | 'name'> & V2ImportGpxUpdate200 & V2ImportKmlKmzUpdate200>;
export interface ImportResult extends Omit<ImportedMapResult, 'layerId' | 'bounds'> {
    layerId: EntityId | undefined;
    collectionId: EntityId | undefined;
    bounds: CameraBounds | null | undefined;
    landmarksSkipped: number;
    duplicatesInFile: number;
    name: string;
}
export interface ImportSession {
    tab: ImportTab;
    gpxFile: File | null;
    kmlFile: File | null;
    mode: ImportMode | null;
    report: ImportReview | null;
    inspecting: boolean;
    busy: boolean;
    uncertain: boolean;
    errors: Record<ImportTab, string>;
    layerNameEdited: boolean;
    result: ImportResult | null;
    refreshing: boolean;
    refreshed: boolean;
    refreshError: string;
    showing: boolean;
    collectionsReady: boolean;
    collectionsLoading: boolean;
    collectionsError: string;
    progress: number | null;
    progressText: string;
}

export interface ImportPresentationHost {
    element: <T extends HTMLElement = HTMLElement>(id: string) => T;
    query: <T extends HTMLElement = HTMLElement>(selector: string) => T;
    eligible: () => boolean;
    interactionLocked: () => boolean;
    renderProgress: () => void;
}
