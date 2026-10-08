import type { ViewerLandmark } from './map-entities.ts';
export interface LandmarkCollectionGroup {
    id: string;
    label: string;
    color: string | null;
    isPersonal: boolean;
    canWrite: boolean;
    landmarks: ViewerLandmark[];
}
