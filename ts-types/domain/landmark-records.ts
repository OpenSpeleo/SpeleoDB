import type { EntityId } from './identifiers.ts';
import type { RecordDates } from './station-records.ts';
export interface LandmarkWrite {
    name?: string;
    description?: string;
    latitude?: number | string;
    longitude?: number | string;
    collection?: EntityId | null;
}
export interface LandmarkRecord extends LandmarkWrite, RecordDates {
    id: EntityId;
    collection_name?: string;
    collection_color?: string;
    can_write?: boolean;
    can_delete?: boolean;
}
export interface LandmarkCollectionRecord extends RecordDates {
    id: EntityId;
    name: string;
    description: string;
    color: string;
    collection_type: string;
    is_personal?: boolean;
    user_permission_level?: number;
    user_permission_level_label?: string;
}
